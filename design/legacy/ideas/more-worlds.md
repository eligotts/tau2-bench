# More Worlds: Calendar Scheduling + Spreadsheet Agent


## World 7: Calendar Scheduling Agent
**Pattern:** Agent reads multiple subgraphs, computes constraints, creates new nodes
**Actors:** Agent (scheduling assistant), User (meeting organizer)

This is a good stress test because the task isn't "fix something" or
"traverse to find something" — it's CONSTRAINT SATISFACTION.  The agent
has to gather information from multiple independent subgraphs, compute
an intersection, and create something new.

### Graph
```
User (Organizer) ──────────────────────────────────
  props: name, email, timezone, preferences

MeetingRequest
  title: "Q1 Planning Review"
  duration: 60min
  required_attendees: [Person.P001, Person.P002, Person.P003]
  optional_attendees: [Person.P004]
  room_required: true
  priority: "high"
  deadline: "must be scheduled by Friday"
  constraints: ["no Mondays for P001", "P002 unavailable before 10am"]

Person ──[1:1]──▶ Calendar ──[1:N]──▶ Event
  person_id            owner             event_id
  name                 timezone          title
  email                visibility        start_time
  role                 share_status      end_time
  timezone                               attendees
  preferences                            recurring
  assistant                              status
  out_of_office                          location

Room ──[1:N]──▶ RoomBooking
  room_id          booking_id
  name             room_id
  capacity         start_time
  location         end_time
  equipment        booked_by
  available

ConferenceLink
  provider: "zoom"
  capacity: 100
  requires_license: true
```

### Gates
```
Person → Calendar:      calendar.share_status == "shared_with_agent"
                        OR User requested access                      [actor + property]
Calendar → Event:       calendar.visibility != "private"
                        (private events show as "busy" only, no details)  [property gate]
Room → RoomBooking:     room.available == true                        [property gate]
MeetingRequest → constraints:  (ungated — always visible)
Person → preferences:   person.role != "executive"
                        OR User.role == "executive_assistant"         [property gate]
```

### Tools
```
Agent READ:  get_meeting_request, get_person, get_calendar, get_events_in_range,
             check_availability(person_id, date_range) → free slots,
             search_rooms(capacity, date_range, equipment) → available rooms,
             get_room_bookings(room_id, date_range)
Agent WRITE: create_event(attendees, time, room, title),
             send_invite(event_id, attendees),
             book_room(room_id, time),
             request_calendar_access(person_id),
             propose_time(attendees, time) → sends proposal,
             update_meeting_request(status)
User READ:   view_proposed_times, view_my_calendar
User WRITE:  approve_time, reject_time, share_calendar, add_constraint
```

### Key: Computed Operations

Unlike previous worlds, the critical tool here isn't a simple property
read — it's `check_availability`, which COMPUTES free slots from events.
This is a derived/computed operation over the graph: scan all events for
a person in a date range, find gaps >= meeting duration.

This means the tool layer includes COMPUTATION, not just CRUD.
The graph holds raw data (events); the tool computes derived info (free slots).

Similarly, finding a compatible slot requires INTERSECTION across
multiple `check_availability` results + applying constraints from
MeetingRequest.  The agent has to:
1. Gather: read each attendee's calendar
2. Compute: find common free slots
3. Filter: apply constraints ("no Mondays", "after 10am")
4. Rank: apply preferences (timezone proximity, priority attendees)
5. Act: book room + create event + send invites

### Example Task (multi-calendar coordination)
```
Generator does:
  1. Create MeetingRequest with 3 required + 1 optional attendee
  2. Populate calendars with events such that there are exactly
     2 valid slots this week (Tuesday 2pm, Thursday 10am)
  3. Add constraint: Person P001 has "no meetings on Tuesday"
     → only Thursday 10am works
  4. Set Person P002's calendar to share_status = "not_shared"
  5. Set one suitable Room to available, others booked

Agent must:
  1. Read meeting request → identify attendees + constraints
  2. Try to check P002's calendar → blocked (not shared)
  3. Request calendar access from P002 (or ask organizer to request)
  4. Once shared: check all calendars for availability
  5. Compute compatible slots → Tuesday 2pm and Thursday 10am
  6. Apply P001's constraint → only Thursday 10am
  7. Search for available room → find Room R3
  8. Book Room R3 for Thursday 10am
  9. Create event with all attendees
  10. Send invites

Goal: Event exists with:
        attendees includes [P001, P002, P003]
        time == Thursday 10am
        room == R3
      AND Room R3 has booking at Thursday 10am
      AND MeetingRequest.status == "scheduled"
```

### Diversity of Generated Tasks
By varying the seed data (calendar events), the generator produces
very different tasks:
- **Easy:** All calendars shared, many compatible slots, no constraints
- **Medium:** One calendar not shared (actor gate), few compatible slots
- **Hard:** Multiple calendars not shared, conflicting constraints,
  only one possible slot, room contention
- **Impossible-by-design:** No compatible slot exists → agent must
  report this to user and propose alternatives (partial attendance,
  split into two meetings, etc.)

### Skills Tested
- Constraint satisfaction (find intersection of availability)
- Information gathering from multiple independent sources
- Handling access restrictions (actor gates on calendars)
- Computation (not just lookup — must compute free slots)
- Fallback reasoning (what if no slot works?)
- Multi-step execution (check → compute → book → invite)


---


## World 8: Spreadsheet Agent
**Pattern:** Agent operates on a 2D grid where cells reference each other
**Actors:** Agent only (or Agent + User for approval)

This is the hardest stress test because the "world" isn't a typical
entity-relationship graph.  It's a grid.  But it maps.

### The Insight: Cells ARE Nodes

A spreadsheet is a graph where:
- Nodes = cells (each with a value and optionally a formula)
- Edges = formula references (A1 references B2 means edge B2 → A1)
- Sheets = subgraphs
- Named ranges = node groups
- Charts = derived views over node groups

The formula dependency graph IS the graph structure.  If cell D5
has formula `=SUM(B2:B4)`, that's three edges: B2→D5, B3→D5, B4→D5.
Changing B2 propagates to D5.  That's dynamics.

### Graph
```
Workbook ──[1:N]──▶ Sheet ──[1:N]──▶ Row ──[1:N]──▶ Cell
  name                name              index          address (e.g. "B5")
  author              index                            value
                      column_headers                   formula
                      row_count                        format
                      frozen_rows                      data_type
                                                       is_locked

Sheet ──[1:N]──▶ NamedRange
                   name
                   range (e.g. "B2:B50")
                   description

Sheet ──[1:N]──▶ Chart
                   type (bar, line, pie)
                   title
                   data_range
                   x_axis, y_axis

Cell ──[refs]──▶ Cell  (formula dependencies)

Sheet ──[refs]──▶ Sheet  (cross-sheet references like Sheet2!A1)
```

### But: Flatten for Practical Modeling

Modeling every individual cell as a node would be huge.  Instead,
model at a HIGHER LEVEL of abstraction:

```
Workbook ──[1:N]──▶ Sheet
  name                name
  author              purpose (e.g. "raw sales data", "summary", "dashboard")
                      row_count, col_count
                      headers: list[str]
                      data: list[list[Any]]  ← the actual grid
                      named_ranges: dict[str, Range]
                      charts: list[Chart]
                      formulas: dict[CellRef, str]  ← formula cells

DataSource ──[refs]──▶ Sheet  (which sheet holds source data)
  name
  type: "csv_import" | "api_pull" | "manual"
  last_updated
  schema: dict[str, type]

Summary ──[refs]──▶ Sheet  (which sheet has derived summaries)
  name
  methodology
  groupby_columns
  aggregate_functions
```

The tools then operate at the right abstraction level — not individual
cells but ranges, columns, and operations.

### Gates
```
Sheet → data:           sheet.is_locked == false OR agent.has_edit_permission
                                                                  [property gate]
Sheet → formulas:       (ungated — can always read formulas)
Summary → methodology:  summary.methodology != ""
                        (can't update summary until method is set) [property gate]
DataSource → sheet:     source.last_updated is recent
                        (stale data → need to refresh first)      [property gate]
```

### Tools
```
Agent READ:  get_sheet, get_cell_range, get_headers, get_named_range,
             get_formula, search_sheets(keyword), get_chart,
             compute_column_stats(sheet, column) → min/max/avg/sum/count,
             find_duplicates(sheet, columns),
             get_data_source_info
Agent WRITE: set_cell(sheet, cell, value),
             set_cell_formula(sheet, cell, formula),
             set_range(sheet, range, values),
             insert_row(sheet, index, values),
             delete_rows(sheet, condition),
             create_named_range(sheet, name, range),
             sort_sheet(sheet, column, order),
             filter_sheet(sheet, conditions) → filtered view,
             create_chart(sheet, type, data_range, title),
             create_sheet(name),
             copy_range(source, destination),
             apply_format(sheet, range, format),
             create_pivot(source_range, rows, cols, values, agg_func),
             refresh_data_source(source_id)
```

### Example Task A: Data Cleanup (transformation)
```
Setup:
  Sheet "RawSales" has 200 rows of sales data with problems:
  - 15 duplicate rows (same order_id)
  - Column "Region" has inconsistent values ("NA", "N.America", "North America")
  - Column "Revenue" has 3 cells with text "N/A" instead of numbers
  - Date column has mixed formats ("2025-01-15", "01/15/2025", "Jan 15 2025")

Agent must:
  1. Get sheet → examine headers and sample data
  2. Find duplicates by order_id → delete them
  3. Find inconsistent Region values → standardize to consistent set
  4. Find non-numeric Revenue cells → fix or flag
  5. Standardize date format

Goal: find_duplicates("RawSales", ["order_id"]) returns empty
      AND unique(column("Region")) == {"North America", "Europe", "Asia Pacific"}
      AND all cells in "Revenue" column are numeric
      AND all cells in "Date" column match format "YYYY-MM-DD"
```

### Example Task B: Analysis + Reporting (multi-step)
```
Setup:
  Sheet "Sales2025" has clean sales data (500 rows)
    columns: date, region, product, quantity, unit_price, salesperson
  Sheet "Targets" has quarterly targets per region
    columns: quarter, region, target_revenue
  Sheet "Report" exists but is empty

Agent must:
  1. Examine Sales2025 structure
  2. Compute revenue (quantity × unit_price) → add column or compute
  3. Group by region and quarter → create pivot or summary
  4. Compare actuals vs targets → join with Targets sheet
  5. Compute variance (actual - target) per region per quarter
  6. Create summary in Report sheet
  7. Add chart showing actual vs target by region

Goal: Sheet "Report" has:
        row_count > 0
        headers include ["Region", "Quarter", "Actual", "Target", "Variance"]
        data is correct (spot-check: actual for "North America" Q1 == sum of
          matching rows in Sales2025)
      AND Chart exists with type "bar" referencing Report data
```

### Example Task C: Complex Formula Construction (deep reasoning)
```
Setup:
  Sheet "Inventory" with columns: product_id, name, stock, reorder_point,
    supplier, lead_time_days, daily_demand_avg
  Sheet "Orders" with columns: order_id, product_id, quantity, order_date, status
  Sheet "Dashboard" exists but is empty

Agent must:
  1. Read Inventory and Orders schemas
  2. In Dashboard, create a reorder analysis:
     - For each product: current stock, pending orders (status="pending"),
       effective stock = stock + pending_quantity
     - Days until stockout = effective_stock / daily_demand_avg
     - Reorder urgency = "critical" if days < lead_time, "warning" if < 2×lead_time
  3. This requires cross-sheet references and computed columns
  4. Create a conditional formatting or chart showing critical items

Goal: Sheet "Dashboard" has:
        column "days_until_stockout" with correct values
          (spot-check: product P001 = (stock + pending) / daily_demand)
        column "reorder_urgency" with correct classifications
      AND at least one product is marked "critical" (seed data ensures this)
```

### How the Generator Creates Spreadsheet Tasks

The generator works differently here — instead of "breaking" fields,
it SETS UP a scenario and defines what "done" looks like:

```
For data cleanup tasks:
  1. Start with clean data
  2. INJECT problems: duplicate rows, inconsistent values, bad formats
  3. Record what was injected
  4. Goal = all injected problems are fixed
  → Solvable by construction: we know the clean version

For analysis tasks:
  1. Generate realistic data with KNOWN statistical properties
  2. Pre-compute the correct answers (aggregates, joins, variances)
  3. Goal = agent's output matches pre-computed answers
  → Solvable by construction: the correct answer is computable from the data

For formula tasks:
  1. Generate source data
  2. Pre-compute all derived values
  3. Goal = formulas produce correct values (spot-check against pre-computed)
  → Solvable by construction: we computed the answer, formulas should too
```

### Skills Tested
- Data understanding (examining schemas, identifying issues)
- Multi-step data transformation
- Cross-sheet computation
- Formula construction
- Reasoning about data relationships
- Working at the right abstraction level (ranges, not individual cells)


---


## Pattern Summary

Both new worlds extend the model in important ways:

### Calendar: Computation Over Graph
The agent doesn't just READ nodes — it must COMPUTE derived information
(free slots from events, intersections across calendars).  This means
tools can be FUNCTIONS over the graph, not just property accessors.

The graph model handles this: computed tools are just tools whose
implementation traverses multiple nodes and returns derived data.
The tool interface is the same; the implementation is richer.

### Spreadsheet: Grid as Graph
The "natural" structure isn't entity-relationship — it's a 2D grid.
But it maps: cells are nodes, formulas are edges, sheets are subgraphs.

The key adaptation: model at the RIGHT ABSTRACTION LEVEL.  Don't model
individual cells as nodes (too granular).  Model sheets as nodes with
grid data as properties.  Tools operate on ranges, not cells.

### Both: Goals Are Computed, Not Just Property Checks

Previous worlds had goals like `field == value`.  These worlds need
COMPUTED goals:
- Calendar: "an event exists with these attendees at a compatible time"
- Spreadsheet: "the sum of column C equals the pre-computed value"

This means goal predicates need to support:
- Existence checks (∃ node matching criteria)
- Aggregate checks (sum/count/avg of a range)
- Cross-reference checks (value in sheet A matches computation over sheet B)
- Format checks (all values in column match pattern)

These are still mechanically verifiable — they're just richer functions
over the graph state.  No LLM judge needed.


## Updated World Coverage

| World              | Novel challenge for the model               |
|--------------------|----------------------------------------------|
| Customer service   | Progressive disclosure via gates             |
| Personal assistant | Cross-service references                     |
| SRE/Infrastructure | Deep diagnostic chains                       |
| Data pipeline      | Effect-to-cause tracing                      |
| HR onboarding      | Multi-actor coordination                     |
| Research analysis   | Information synthesis, few writes            |
| Calendar scheduling | Constraint satisfaction, computed operations |
| Spreadsheet        | Grid structure, computed goals               |
