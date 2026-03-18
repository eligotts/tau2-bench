# Domain Scope: Daily Planner — AI Personal Assistant

## 1. Pilot Domain

**Concept:** An AI personal assistant helping a person manage a day where multiple concurrent
obligations are falling apart. The agent manages the digital/logistical side (calendar,
bookings, orders, payments, messaging) while the user is physically in the world (commuting,
in meetings, at locations, confirming things). The user could be anyone — a working parent,
a freelancer juggling clients, a college student with overlapping deadlines, an elderly person
managing appointments — the system is a general-purpose daily logistics assistant.

**Operational slice:** One day's logistics for a single user. The user has 4-7 concurrent
objectives across life domains (work/school calendar, dependent care, errands, finance,
household, transport). Not every user has every lane active — a student won't have dependent care,
an elderly user won't have work meetings. Complications cascade — a meeting running late
blocks an errand window, which forces rebooking transport, which affects pickup timing.

**What makes this a good agentic domain:**
- Genuine collaboration: agent proposes, user reacts with real-world constraints, agent adapts
- Information asymmetry: agent sees digital systems, user sees physical world
- Time pressure: objectives have deadlines, and the user can only be in one place
- Cascading dependencies: rescheduling one thing ripples across everything

**Target complexity tier:** Tier 3 (Advanced), aiming for 80-150+ unique tasks.

## 2. Agent DB Schema Sketch

### Calendar
| Field | Type | Notes |
|-------|------|-------|
| calendar_id | str | |
| meetings | dict[meeting_id, Meeting] | |

### Meeting
| Field | Type | Notes |
|-------|------|-------|
| meeting_id | str | |
| title | str | |
| start_time | str | HH:MM |
| end_time | str | HH:MM |
| status | enum: scheduled, rescheduled, cancelled, completed | gate-relevant |
| participants | list[str] | |
| location | str | |
| priority | enum: critical, normal, flexible | gate-relevant |
| reschedule_window | str | nullable, new time if rescheduled |

### Errands
| Field | Type | Notes |
|-------|------|-------|
| errand_id | str | |
| type | enum: prescription, grocery, package_pickup, dry_cleaning, auto_service | |
| status | enum: pending, arranged, in_progress, completed, cancelled | gate-relevant |
| location | str | |
| deadline | str | HH:MM |
| requires_user_present | bool | |
| delivery_available | bool | |
| delivery_status | enum: not_requested, requested, in_transit, delivered, failed | |

### Transport
| Field | Type | Notes |
|-------|------|-------|
| transport_id | str | |
| type | enum: personal_car, rideshare, public_transit | |
| status | enum: available, unavailable, booked, in_transit, arrived | gate-relevant |
| car_issue | enum: none, flat_tire, in_shop, low_fuel | gate-relevant for personal_car |
| rideshare_eta | str | nullable |
| booked_destination | str | nullable |

### Finance
| Field | Type | Notes |
|-------|------|-------|
| account_id | str | |
| checking_balance | float | |
| savings_balance | float | |
| pending_bills | list[Bill] | |
| transfer_status | enum: none, pending, completed, failed | gate-relevant |
| transfer_amount | float | nullable |

### Bill
| Field | Type | Notes |
|-------|------|-------|
| bill_id | str | |
| amount | float | |
| due_date | str | |
| status | enum: unpaid, paid, overdue, scheduled | gate-relevant |
| auto_pay | bool | |

### Messaging
| Field | Type | Notes |
|-------|------|-------|
| thread_id | str | |
| contact | str | |
| last_message | str | |
| reply_status | enum: no_reply, replied, awaiting | |
| reply_content | str | nullable |

### DependentCare
| Field | Type | Notes |
|-------|------|-------|
| care_type | enum: child_school, child_daycare, elder_appointment, pet_vet | what kind of pickup/care |
| pickup_status | enum: unassigned, user_assigned, delegate_assigned, completed | gate-relevant |
| pickup_time | str | HH:MM deadline |
| delegate_contact | str | nullable |
| delegate_availability | enum: unknown, available, unavailable | gate-relevant |
| facility_notified | bool | school/daycare/clinic notified of plan change |
| extended_care_status | enum: not_needed, requested, confirmed, unavailable | aftercare/extended hours |

### Household
| Field | Type | Notes |
|-------|------|-------|
| maintenance_id | str | |
| issue_type | enum: plumber, electrician, appliance_repair, locksmith | |
| status | enum: reported, scheduled, technician_dispatched, in_progress, completed | gate-relevant |
| technician_eta | str | nullable |
| requires_user_home | bool | |
| access_arranged | bool | |

## 3. User DB Schema Sketch

### UserContext
| Field | Type | Notes |
|-------|------|-------|
| current_location | enum: home, work, commuting, errand_location, school_area | |
| available_until | str | HH:MM, when user must leave current location |
| physical_observation | str | last thing user checked |

### UserErrandStatus
| Field | Type | Notes |
|-------|------|-------|
| errand_id | str | |
| user_confirmed_complete | bool | user physically did/picked up the item |
| user_observed_issue | str | nullable, e.g. "pharmacy says prescription not ready" |

### UserTransportStatus
| Field | Type | Notes |
|-------|------|-------|
| car_inspected | bool | user physically checked car situation |
| car_observation | str | nullable |
| rideshare_arrived | bool | user confirms ride is here |

### UserDependentCareStatus
| Field | Type | Notes |
|-------|------|-------|
| user_at_school | bool | |
| dependent_picked_up | bool | |
| delegate_confirmed_pickup | bool | |

### UserHomeStatus
| Field | Type | Notes |
|-------|------|-------|
| user_at_home | bool | |
| technician_arrived | bool | |
| repair_verified | bool | |

## 4. Field Projection Table

| field_path | owner_db | type_or_domain | projected_for_solver | update_source | notes |
|---|---|---|---|---|---|
| agent.calendar.meetings.{id}.status | agent | enum | yes | assistant_tool | gate for downstream scheduling |
| agent.calendar.meetings.{id}.priority | agent | enum | yes | init_only | determines reschedule flexibility |
| agent.errands.{id}.status | agent | enum | yes | assistant_tool, sync | main errand tracking |
| agent.errands.{id}.deadline | agent | str | no | init_only | used by runtime, not solver |
| agent.errands.{id}.delivery_status | agent | enum | yes | assistant_tool | alternative to user pickup |
| agent.transport.status | agent | enum | yes | assistant_tool, sync | gates errand feasibility |
| agent.transport.car_issue | agent | enum | yes | init_only, sync | value-gates transport resolution |
| agent.finance.checking_balance | agent | float | no | assistant_tool | runtime only |
| agent.finance.transfer_status | agent | enum | yes | assistant_tool | gates bill payment |
| agent.finance.bills.{id}.status | agent | enum | yes | assistant_tool | terminal requirement |
| agent.dependent_care.pickup_status | agent | enum | yes | assistant_tool, sync | critical deadline gate |
| agent.dependent_care.delegate_availability | agent | enum | yes | assistant_tool | value-gates delegation path |
| agent.dependent_care.aftercare_status | agent | enum | yes | assistant_tool | fallback path |
| agent.dependent_care.school_notified | agent | bool | yes | assistant_tool | required for delegation |
| agent.household.status | agent | enum | yes | assistant_tool, sync | if maintenance is active |
| agent.household.access_arranged | agent | bool | yes | assistant_tool | required if user not home |
| agent.messaging.{id}.reply_status | agent | enum | yes | sync | reflects user/contact replies |
| user.location | user | enum | yes | user_tool | gates physical errands |
| user.errand.{id}.confirmed_complete | user | bool | yes | user_tool | proves errand done |
| user.errand.{id}.observed_issue | user | str | no | user_tool | runtime narrative only |
| user.transport.car_inspected | user | bool | yes | user_tool | binding: car situation |
| user.dependent_care.dependent_picked_up | user | bool | yes | user_tool | terminal for dependent care |
| user.dependent_care.delegate_confirmed | user | bool | yes | user_tool | proves delegation worked |
| user.home.technician_arrived | user | bool | yes | user_tool | gates repair progress |
| user.home.repair_verified | user | bool | yes | user_tool | terminal for household |

## 5. Context Slots

- `active_user`: The user whose day is being managed (single user per task)
- `active_day`: The day's schedule context (meetings, errands, obligations)

All world paths are scoped through these slots. Each task instance populates a different
combination of active obligations and complications.

## 6. Projected World Paths

Causal paths used by the solver:

**Calendar lane:**
- `agent.calendar.meetings.{id}.status` — scheduled → rescheduled / cancelled / completed
- Meeting status gates downstream errand/transport windows

**Transport lane:**
- `agent.transport.status` — available / unavailable / booked / in_transit / arrived
- `agent.transport.car_issue` — none / flat_tire / in_shop / low_fuel
- Transport availability gates all physical errands and dependent care pickup

**Errand lane (per errand):**
- `agent.errands.{id}.status` — pending → arranged → in_progress → completed
- `agent.errands.{id}.delivery_status` — not_requested → requested → in_transit → delivered
- Two paths to completion: user picks up (requires transport + user present) or delivery

**Finance lane:**
- `agent.finance.transfer_status` — none → pending → completed
- `agent.finance.bills.{id}.status` — unpaid → paid / scheduled
- Transfer must complete before bill payment if balance insufficient

**Dependent care lane:**
- `agent.dependent_care.pickup_status` — unassigned → user_assigned / delegate_assigned → completed
- `agent.dependent_care.delegate_availability` — unknown → available / unavailable
- `agent.dependent_care.aftercare_status` — not_needed → requested → confirmed / unavailable
- Three resolution paths: user picks up, delegate picks up, aftercare extension

**Household lane:**
- `agent.household.status` — reported → scheduled → technician_dispatched → in_progress → completed
- `agent.household.access_arranged` — false → true (required if user not home)

**User physical state:**
- `user.location` — gates which physical actions are possible
- `user.transport.car_inspected` — binding for car situation
- `user.dependent_care.dependent_picked_up` / `user.dependent_care.delegate_confirmed` — terminal proofs
- `user.errand.{id}.confirmed_complete` — terminal proofs
- `user.home.repair_verified` — terminal proof

## 7. Assistant Toolset (rough)

**Calendar management:**
- `check_calendar(date)` → READ — returns day's meetings with times/status/priority
- `reschedule_meeting(meeting_id, new_time)` → WRITE — reschedule if participants available
- `cancel_meeting(meeting_id)` → WRITE — cancel a flexible meeting
- `check_participant_availability(meeting_id, proposed_time)` → READ — check if reschedule is feasible

**Errand management:**
- `check_errand_status(errand_id)` → READ — current status, deadline, options
- `arrange_delivery(errand_id)` → WRITE — request delivery instead of pickup (if available)
- `reschedule_errand(errand_id, new_time)` → WRITE — push to different time window
- `cancel_errand(errand_id)` → WRITE — cancel if non-essential

**Transport management:**
- `check_transport_options()` → READ — car status, rideshare availability, transit options
- `book_rideshare(destination)` → WRITE — book a ride
- `cancel_rideshare()` → WRITE — cancel booked ride
- `schedule_roadside_assistance()` → WRITE — for car issues (flat tire, low fuel)
- `schedule_auto_pickup(service_location)` → WRITE — for car in shop

**Finance management:**
- `check_account_balances()` → READ — checking + savings balances
- `check_pending_bills()` → READ — bills due today with amounts
- `initiate_transfer(from_account, to_account, amount)` → WRITE — savings→checking transfer
- `pay_bill(bill_id)` → WRITE — pay bill (requires sufficient checking balance)
- `schedule_bill_payment(bill_id, date)` → WRITE — defer payment to later date

**Dependent care management:**
- `check_dependent_care_status()` → READ — pickup time, current assignment, options
- `assign_user_pickup()` → WRITE — assign user as pickup person
- `contact_delegate(contact_name)` → WRITE — reach out to backup pickup person
- `request_extended_care()` → WRITE — request aftercare / extended hours at facility
- `notify_facility(message)` → WRITE — inform school/daycare/clinic of plan change

**Household management:**
- `check_maintenance_status()` → READ — technician ETA, repair status
- `schedule_maintenance(issue_type, preferred_time)` → WRITE — book technician
- `arrange_building_access(method)` → WRITE — leave key/code for technician
- `reschedule_maintenance(new_time)` → WRITE — move appointment

**Messaging:**
- `send_message(contact, content)` → WRITE — send text/email to a contact
- `check_messages(contact)` → READ — check for replies from a contact

## 8. User Toolset (rough)

**Location/physical state (causal):**
- `report_location(location)` → WRITE — user reports where they are
- `report_situation(description)` → WRITE — user reports unexpected situation (meeting running late, traffic jam, etc.)

**Transport observation (knowledge-only):**
- `check_car_status()` → READ — user physically inspects car, discovers issue
- `confirm_rideshare_arrived()` → WRITE — user confirms ride is at pickup point

**Errand completion (causal):**
- `confirm_errand_complete(errand_id)` → WRITE — user picked up prescription / groceries / package
- `report_errand_issue(errand_id, issue)` → WRITE — "pharmacy says prescription isn't ready"

**Dependent care (causal, ordered):**
- `confirm_dependent_picked_up()` → WRITE — user picked up dependent (child, pet, etc.)
- `confirm_delegate_pickup()` → WRITE — user confirms delegate did the pickup

**Household (causal, ordered):**
- `confirm_technician_arrived()` → WRITE — user confirms technician is there
- `verify_repair_complete()` → WRITE — user verifies repair is done

**Resolution (stutter-only):**
- `check_resolution_status()` → READ — checks all objectives met, returns unmet items

## 9. World/Sync Logic

**Cascading: meeting overtime → schedule compression**
- When a meeting's actual end time exceeds its slot, all subsequent time-dependent
  objectives lose their window. Errands whose deadline falls within the blocked period
  become "must deliver" or "must reschedule."

**Cascading: transport unavailable → errand blocking**
- When `agent.transport.status = unavailable` and `agent.transport.car_issue != none`,
  all errands with `requires_user_present = true` are blocked until transport is restored
  or delivery is arranged.

**Cascading: dependent care deadline pressure → meeting cancellation**
- If `agent.dependent_care.pickup_status = unassigned` and the pickup deadline is approaching
  and user is in a meeting, the agent must either arrange a delegate or cancel/cut short
  the meeting. This creates a forced tradeoff.

**Sync: user errand confirmation → errand completion**
- When `user.errand.{id}.confirmed_complete = true`, sync sets
  `agent.errands.{id}.status = completed`.

**Sync: user pickup → dependent care completion**
- When `user.dependent_care.dependent_picked_up = true`, sync sets
  `agent.dependent_care.pickup_status = completed`.

**Sync: delegate confirmation → dependent care completion**
- When `user.dependent_care.delegate_confirmed = true`, sync sets
  `agent.dependent_care.pickup_status = completed`.

**Sync: repair verification → household completion**
- When `user.home.repair_verified = true`, sync sets
  `agent.household.status = completed`.

**Sync: transport resolution → transport available**
- When car issue is resolved (roadside assistance completed) or rideshare is booked,
  sync updates `agent.transport.status` accordingly.

**Sync: insufficient funds → bill payment blocked**
- `agent.finance.transfer_status` must be `completed` before `pay_bill` succeeds
  when checking balance < bill amount. This is a tool-level guard, not sync.

**Resolution sync:**
- `incident_resolved` fires when all active objectives reach terminal state
  (all active errands completed/cancelled, dependent care completed, bills paid,
  household completed if active, no meetings in conflict state).

## 10. Dependency Patterns to Support

### Bindings (6 total — Tier 3)

| Binding | Source Tool | Stable/Volatile | Notes |
|---------|-----------|-----------------|-------|
| K.calendar_state | check_calendar | stable | day's meetings, used to identify conflicts |
| K.transport_situation | check_car_status (user) | stable | what's wrong with the car, gates resolution path |
| K.account_balances | check_account_balances | stable | determines if transfer needed before payment |
| K.delegate_response | check_messages(delegate) | volatile | whether delegate can do pickup — may change |
| K.errand_availability | check_errand_status | stable | whether delivery is available, pickup requirements |
| K.maintenance_eta | check_maintenance_status | volatile | technician arrival time, affects user scheduling |

**Tiered prerequisites:**
- K.calendar_state is needed first (determines time windows for everything)
- K.transport_situation is needed to decide errand approach
- K.account_balances is independent
- K.delegate_response requires having sent a message first (contact_delegate)
- K.errand_availability can be gathered per-errand independently

### Value-Dependent Branching

**Transport resolution branch:**
- `car_issue = flat_tire` → schedule_roadside_assistance (quick fix, ~30min)
- `car_issue = in_shop` → book_rideshare or rearrange errands for delivery
- `car_issue = low_fuel` → user can drive to gas station (if nearby) or book rideshare
- `car_issue = none` → transport available, no action needed

**Dependent care resolution branch:**
- `delegate_availability = available` → delegate_assigned path (notify school, confirm)
- `delegate_availability = unavailable` → try aftercare extension
- `aftercare_status = unavailable` → user MUST pick up (may require cancelling meeting)

**Errand resolution branch (per errand):**
- `delivery_available = true` AND transport unavailable → arrange_delivery
- `delivery_available = false` AND transport unavailable → must fix transport first
- Transport available → user picks up in person

**Finance resolution branch:**
- Sufficient balance → pay directly
- Insufficient balance → initiate_transfer → wait → pay after transfer completes

### Cross-Dependencies Between User Actions

User-side actions form a DAG, not a flat basket:
- `check_car_status` must precede transport decisions (binding prerequisite)
- `report_location` gates which physical actions are possible (can't confirm errand pickup if not at errand location)
- `confirm_technician_arrived` must precede `verify_repair_complete`
- `confirm_errand_complete` requires user to have traveled to errand location (transport must be resolved first)
- `confirm_dependent_picked_up` requires user at school_area (if user is doing pickup)

### Early Convergence Points

- **Errand execution** requires BOTH transport resolved AND errand arranged — two upstream lanes must converge before user can go do it
- **Delegate dependent care** requires BOTH delegate contacted AND delegate responded available AND facility notified — three upstream actions converge
- **Bill payment** requires BOTH transfer completed (if needed) AND bill checked — financial lane converges

### Shared Downstream Gates

All active lanes must clear before resolution:
- All active errands: completed or cancelled
- Dependent care: pickup completed (any path)
- Finance: all due bills paid or scheduled
- Household: repair verified (if active)
- Calendar: no unresolved conflicts
- Transport: no longer blocking anything

### Cascading Sync Rules (Tier 3)

1. **Transport failure cascades:** `car_issue != none` → all `requires_user_present` errands
   become blocked → forces delivery-or-reschedule decision per errand
2. **Meeting overtime cascades:** meeting running late → downstream errand windows close →
   must rearrange or delegate
3. **Dependent care deadline pressure:** approaching deadline + unresolved pickup → escalation
   pressure on current activity (may force meeting cancellation)

### Repair Side-Effects

- **Cancelling a meeting** to handle dependent care → may need to send apology message to
  participants, reschedule for tomorrow
- **Arranging delivery** instead of pickup → may cost more, affecting bill payment balance
- **Transfer from savings** → savings account may have minimum balance requirement

## 11. Known Risks

1. **Time modeling:** Real-time deadlines are hard to model in a turn-based system. We
   abstract time as "windows" and "deadlines" rather than real clocks. The solver
   treats deadlines as hard constraints on action ordering, not as real-time pressure.
2. **Location modeling:** User can only be in one place. We model this as a state variable
   that gates which physical actions are possible. Travel between locations is implicit
   in transport booking/usage.
3. **Scope creep:** A "full day" has unlimited complexity. We bound it to 4-7 active
   objectives per task, with only 2-4 having complications.
4. **Ambiguity in prioritization:** Unlike system repair, life logistics involve subjective
   tradeoffs (cancel meeting vs. miss pickup?). The policy must establish clear priority
   rules so the agent's choices are verifiable.

## 12. Stop-Gate Observables (Candidate)

User-observable fields for `check_resolution_status`:

- All active errands in terminal state (completed or cancelled)
- Dependent care pickup completed (if care lane is active)
- All due bills paid or deferred with explicit schedule
- No calendar conflicts remaining
- Household repair verified (if maintenance was active)
- Transport no longer blocking any pending objective

The checker returns `resolved: true` only when ALL active objectives are terminal.
It returns specific `unmet` items when any objective is still pending.

## 13. Persona Strategy (Candidate)

These are genuinely different people who use the same daily planner assistant, not mood
variations of one archetype. Different personas naturally activate different lane
combinations, adding diversity beyond what seeds alone provide.

| Persona | Who They Are | Active Lanes | Behavioral Axes | Best For |
|---------|-------------|--------------|-----------------|----------|
| Working Parent | Mid-career professional with school-age kids. Juggles work meetings, school pickups, household maintenance. | Calendar + Dependent Care + Household + Errands | high urgency, low verbosity, medium tech comfort | Hard tasks (all lanes active, time pressure) |
| Freelance Creative | Self-employed designer/writer. Irregular schedule, multiple client deadlines, unreliable income timing. | Calendar + Finance + Errands + Transport | medium urgency, high verbosity, high tech comfort | Medium tasks (finance lane critical, flexible calendar) |
| College Student | Full course load, part-time job, shared housing. Overlapping deadlines, tight budget, no car. | Calendar + Finance + Errands + Transport | low urgency perception, low verbosity, high tech comfort | Easy-medium tasks (fewer lanes, budget-focused) |
| Elderly Retiree | Lives alone, multiple medical appointments, limited mobility, relies on others for transport. | Errands + Transport + Household + Dependent Care (pet vet appointment) | high urgency, high verbosity, low tech comfort | Medium-hard tasks (transport-dependent, delegation-heavy) |
| Small Business Owner | Runs a shop/restaurant. Work obligations overlap with personal errands, employees to coordinate, vendor deliveries. | Calendar + Finance + Errands + Household + Transport | high urgency, medium verbosity, medium tech comfort | Hard tasks (business + personal obligations interleave) |

## 14. Out of Scope (Pilot)

- Multi-day planning (only same-day logistics)
- Social/relationship management beyond logistics messages
- Health/medical decisions (prescriptions are errands, not medical advice)
- Work task management (meetings are calendar items, not project management)
- Shopping decisions (we handle "pick up groceries" not "what groceries to buy")
- Smart home / IoT control
- Travel planning (flights, hotels)
- Real-time location tracking / GPS integration
- Multi-user coordination (only one user's day, delegates are simple contacts)
