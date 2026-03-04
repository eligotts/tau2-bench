# Diverse Worlds: Proving Generality

Six worlds spanning very different interaction patterns, all modeled
in the same unified framework.  For each: the graph, the gates, the
tools, example tasks, and what skills are tested.


## World 1: Customer Service (tau2 classic)
**Pattern:** Agent + User, fix problems, progressive disclosure
**Actors:** Agent (support rep), User (customer)

### Graph
```
User ─────────────────────────────────────────────┐
  props: name, identity_verified, device_restarted │
                                                   │
Customer ──[1:N]──▶ Order ──[1:N]──▶ OrderItem ──▶ MenuItem
  │  account_status     status          quantity      available
  │  email              total           price
  │
  ├──[1:1]──▶ LoyaltyAccount
  │              points, tier
  │
  └──[1:1]──▶ Subscription
                 status, monthly_charge, plan_type
```

### Gates
```
Customer → Order:         account_status == "active"          [property gate]
Customer → LoyaltyAccount: User.identity_verified == true     [actor gate]
Customer → Subscription:  User.identity_verified == true      [actor gate]
Order → OrderItem:        order.status != "cancelled"         [property gate]
```

### Tools
```
Agent READ:  get_customer, get_order, get_order_items, get_loyalty, get_subscription
Agent WRITE: update_account_status, update_order_status, adjust_points, update_subscription
User READ:   check_my_orders, check_my_loyalty
User WRITE:  verify_identity, restart_device, acknowledge_resolution
```

### Example Task (depth 3)
```
Generator does:
  1. Break OrderItem.quantity = 0 (deep node)
  2. Break Order.status = "cancelled" (gates OrderItem)
  3. Break Customer.account_status = "suspended" (gates Order)

Agent must:
  1. Discover suspended account → fix it
  2. Now can see Order → discover cancelled → fix it
  3. Now can see OrderItems → discover wrong quantity → fix it

Goal: Customer.account_status == "active"
      AND Order.status == "completed"
      AND OrderItem.quantity == 3
```

### Skills Tested
- Progressive disclosure (gated traversal)
- User coordination (identity verification)
- Multi-step problem solving
- Information gathering from user


---


## World 2: Personal Assistant (cross-service orchestration)
**Pattern:** Agent + User, coordinate across multiple independent services
**Actors:** Agent (assistant), User (person being assisted)

### Graph
```
User ──────────────────────────────────────────────────────────────────
  props: name, current_time, preferences, approved_actions

Calendar ──[1:N]──▶ Event ──[N:M]──▶ Contact
  owner               title           name
                      time            email
                      location        phone
                      attendees       relationship
                      status

Email ──[1:N]──▶ Thread ──[1:N]──▶ Message
  owner            subject           from, to
                   labels            body
                   starred           timestamp
                   unread_count      attachments

TaskList ──[1:N]──▶ TaskItem
  owner               title, description
                      due_date, priority
                      status, assigned_to
                      linked_event, linked_thread

                      ▲ cross-refs ▲
Event.attendees ──refs──▶ Contact
Message.from ──refs──▶ Contact
TaskItem.linked_event ──refs──▶ Event
TaskItem.linked_thread ──refs──▶ Thread
```

### Gates
```
Calendar → Event:     User.approved_actions includes "calendar_read"   [actor gate]
Email → Thread:       User.approved_actions includes "email_read"      [actor gate]
Thread → Message:     (ungated — once you have the thread)
TaskItem → Event:     linked_event is not null                         [info gate]
TaskItem → Thread:    linked_thread is not null                        [info gate]
```

### Tools
```
Agent READ:  search_calendar, get_event, search_email, get_thread,
             get_messages, get_contacts, search_tasks, get_task
Agent WRITE: create_event, update_event, send_email, reply_to_thread,
             create_task, update_task, mark_thread_read
User READ:   check_my_schedule, check_my_inbox
User WRITE:  approve_calendar_access, approve_email_access, confirm_action
```

### Example Task (cross-service, depth 2)
```
Generator does:
  1. Create an Event with attendee Contact "Dr. Smith" at 3pm Tuesday
  2. Create a Thread from "Dr. Smith" saying "Can we reschedule to Thursday?"
  3. Create a TaskItem: "Reschedule Dr. Smith meeting"
     linked_event → the Event, linked_thread → the Thread

Agent must:
  1. Get user approval to access calendar and email
  2. Read the task → follow link to thread → read the email
  3. Follow link to event → see current time
  4. Check Dr. Smith's contact for preferences
  5. Update event to Thursday
  6. Reply to email confirming
  7. Update task as completed

Goal: Event.time == "Thursday 3pm"
      AND Thread has reply with "confirmed" or "rescheduled"
      AND TaskItem.status == "completed"
```

### Skills Tested
- Cross-service coordination (calendar + email + tasks)
- Permission management (asking user for access)
- Following cross-references between subgraphs
- Multi-action execution (read, update, reply, complete)


---


## World 3: SRE / Infrastructure Debugging (pure agent, diagnostic)
**Pattern:** Agent alone, diagnose and fix infrastructure across layers
**Actors:** Agent only (SRE on-call)

### Graph
```
Cluster ──[1:N]──▶ Namespace ──[1:N]──▶ Deployment ──[1:N]──▶ Pod
  name                name                name              name
  status              resource_quota      replicas          status
  version             labels              image             restarts
                                          strategy          logs
                                          config_ref ──▶ ConfigMap
                                                           data (key-value)

Namespace ──[1:N]──▶ Service ──[1:1]──▶ Ingress
                       name               host
                       selector            path
                       port                tls_enabled
                       type                certificate_ref ──▶ Secret
                                                                data

Cluster ──[1:1]──▶ MonitoringStack
                     alerts: list[Alert]
                     dashboards: list[Dashboard]

Alert ──refs──▶ Pod or Service or Deployment  (the thing that's alerting)
```

### Gates
```
Cluster → Namespace:    cluster.status == "reachable"         [property gate]
Deployment → Pod:       deployment.replicas > 0               [property gate]
Service → Ingress:      service.type == "LoadBalancer"        [property gate]
Pod → logs:             pod.status != "Pending"               [property gate]
Alert → target:         (ungated — alerts always visible)
```

### Tools
```
Agent READ:  kubectl_get_clusters, kubectl_get_namespaces, kubectl_get_deployments,
             kubectl_get_pods, kubectl_logs, kubectl_describe, kubectl_get_services,
             kubectl_get_ingress, kubectl_get_configmap, kubectl_get_secret,
             get_alerts, get_dashboard
Agent WRITE: kubectl_scale, kubectl_rollout_restart, kubectl_apply_config,
             kubectl_patch, kubectl_delete_pod, update_configmap,
             acknowledge_alert, create_ingress
(No user tools — pure agent)
```

### Example Task (diagnostic chain, depth 4)
```
Generator does:
  1. Break ConfigMap data: wrong DB connection string
  2. This causes Pod to crashloop (break Pod.status = "CrashLoopBackOff")
  3. Break Deployment.replicas = 0 (auto-scaled down due to crashes)
  4. Create Alert pointing to the Deployment

Agent must:
  1. See alert → identifies Deployment
  2. Describe Deployment → sees 0 replicas, scale up
  3. Now pods exist → check pod logs → see DB connection error
  4. Follow config_ref → find ConfigMap → fix the connection string
  5. Restart deployment
  6. Verify pods are running

Goal: ConfigMap.data["DB_HOST"] == "prod-db.internal"
      AND Deployment.replicas >= 2
      AND all Pods.status == "Running"
      AND Alert.acknowledged == true
```

### Skills Tested
- Diagnostic reasoning (follow symptoms to root cause)
- Multi-layer infrastructure understanding
- Reading logs and error messages
- Correct ordering (scale up before you can see logs)
- No user interaction — pure agent competence


---


## World 4: Data Pipeline Operations (pure agent, cross-system)
**Pattern:** Agent alone, manage data flow across multiple systems
**Actors:** Agent only (data engineer)

### Graph
```
SourceDB ──[1:N]──▶ Table ──[1:N]──▶ Column
  host                 name              name
  status               row_count         type
  credentials_ref      last_updated      nullable

Pipeline ──[1:N]──▶ Stage ──[1:1]──▶ StageConfig
  name                 name              query
  schedule             status            transform
  last_run             error_log         destination
  owner                duration

Stage.source ──refs──▶ Table  (which table this stage reads from)
Stage.destination ──refs──▶ Table or Warehouse.Table

Warehouse ──[1:N]──▶ Schema ──[1:N]──▶ Table
  name                  name              name
  status                permissions       row_count
                                          freshness

Dashboard ──[N:M]──▶ Warehouse.Table  (which tables feed this dashboard)
  name
  owner
  refresh_schedule
  status
  last_refresh
```

### Gates
```
SourceDB → Table:       source.status == "connected"          [property gate]
Pipeline → Stage:       pipeline.last_run != "failed"         [property gate]
Stage → StageConfig:    (ungated)
Stage → error_log:      stage.status == "failed"              [property gate - only visible on failure!]
Schema → Table:         schema.permissions includes "read"    [property gate]
Dashboard → Tables:     dashboard.status == "active"          [property gate]
```

### Tools
```
Agent READ:  list_sources, describe_table, preview_data, list_pipelines,
             get_stage_status, get_stage_config, get_error_log,
             list_warehouse_schemas, query_warehouse, get_dashboard_status
Agent WRITE: update_stage_config, retry_stage, restart_pipeline,
             update_source_credentials, grant_schema_permissions,
             refresh_dashboard, pause_pipeline
```

### Example Task (cross-system diagnosis)
```
Generator does:
  1. Break SourceDB.credentials (expired password)
  2. This causes Stage 2 to fail (break status = "failed", set error_log)
  3. Downstream: Warehouse.Table.freshness = "stale" (48hrs old)
  4. Dashboard.status = "data_stale_warning"

Agent must:
  1. See dashboard warning → check which warehouse tables feed it
  2. Check table freshness → stale → trace back to pipeline
  3. Check pipeline stages → stage 2 failed → read error log
  4. Error log says "authentication failed" → trace to source DB
  5. Fix source credentials
  6. Retry failed stage
  7. Refresh dashboard

Goal: SourceDB.status == "connected"
      AND Stage.status == "completed"
      AND Warehouse.Table.freshness < 1hr
      AND Dashboard.status == "active"
```

### Skills Tested
- Tracing data lineage (effect → cause across systems)
- Cross-system reasoning (dashboard → warehouse → pipeline → source)
- Reading error logs for diagnostic information
- Correct fix ordering (fix source before retry, retry before refresh)


---


## World 5: HR / Employee Onboarding (multi-actor workflow)
**Pattern:** Agent coordinates between multiple actors and systems
**Actors:** Agent (HR coordinator), User (new hire), plus simulated
           actors: Manager, IT Admin, Facilities

### Graph
```
User (NewHire) ──────────────────────────────────────────────────
  props: name, start_date, documents_signed, badge_photo_uploaded

Employee ──[N:1]──▶ Department ──[1:1]──▶ Manager
  name                name                  name
  employee_id         budget                approval_given
  start_date          headcount
  status              location

Employee ──[1:1]──▶ ITSetup
                      laptop_ordered
                      accounts_created
                      vpn_configured
                      email_provisioned
                      admin_approved

Employee ──[1:1]──▶ FacilitiesSetup
                      desk_assigned
                      badge_created
                      parking_assigned
                      building_access

Employee ──[1:1]──▶ PayrollRecord
                      bank_account
                      tax_form
                      salary
                      benefits_election

Employee ──[1:N]──▶ OnboardingTask
                      name
                      status
                      assigned_to
                      blocked_by ──refs──▶ other OnboardingTask
                      due_date
```

### Gates
```
Employee → ITSetup:         Manager.approval_given == true     [actor gate]
Employee → FacilitiesSetup: Manager.approval_given == true     [actor gate]
ITSetup → accounts_created: ITSetup.admin_approved == true     [actor gate]
ITSetup → vpn_configured:   ITSetup.accounts_created == true   [property gate]
FacilitiesSetup → badge:    User.badge_photo_uploaded == true  [actor gate]
PayrollRecord → salary:     User.documents_signed == true      [actor gate]
Employee → PayrollRecord:   Employee.status == "approved"      [property gate]
```

### Tools
```
Agent READ:  get_employee, get_department, get_it_setup, get_facilities,
             get_payroll, get_onboarding_tasks, get_manager
Agent WRITE: create_employee, update_employee_status, order_laptop,
             request_accounts, assign_desk, request_badge,
             setup_payroll, request_manager_approval, request_it_approval,
             complete_onboarding_task
User WRITE:  sign_documents, upload_badge_photo, confirm_start_date
Manager:     approve_hire (simulated — agent requests, system updates)
IT Admin:    approve_accounts (simulated — agent requests, system updates)
```

### Example Task (multi-actor coordination)
```
Generator does:
  1. Create Employee record in "pending" status
  2. Set Manager.approval_given = false
  3. Set all ITSetup fields to false
  4. Set all FacilitiesSetup fields to false
  5. Set PayrollRecord to empty

Agent must:
  1. Request manager approval → wait for approval
  2. Once approved: request IT setup AND facilities setup in parallel
  3. Ask user to upload badge photo → facilities can create badge
  4. Ask user to sign documents → payroll can be set up
  5. Request IT admin approval → once approved, create accounts
  6. Once accounts created → configure VPN
  7. Complete all onboarding tasks

Goal: Employee.status == "onboarded"
      AND ITSetup.all_fields == true
      AND FacilitiesSetup.all_fields == true
      AND PayrollRecord.complete == true
      AND all OnboardingTasks.status == "completed"
```

### Skills Tested
- Multi-actor coordination (manager, IT, facilities, new hire)
- Parallel execution (IT and facilities can happen simultaneously)
- Dependency management (VPN requires accounts, badge requires photo)
- User interaction (asking new hire to take actions)
- Workflow orchestration across systems


---


## World 6: Research Analysis (information synthesis, minimal writes)
**Pattern:** Agent + User, gather and synthesize information, few state changes
**Actors:** Agent (research analyst), User (decision maker)

### Graph
```
User ─────────────────────────────────────────────
  props: query, constraints, accepted_findings

Database ──[1:N]──▶ Dataset ──[1:N]──▶ Record
  name                name                fields...
  description         schema
  access_level        row_count
  documentation

API ──[1:N]──▶ Endpoint
  name            path
  auth_required   method
  rate_limit      response_schema

Report ──[N:M]──▶ Dataset  (which datasets were used)
  title
  findings
  methodology
  status
  author

KnowledgeBase ──[1:N]──▶ Article
  topic                    title
                           content
                           citations
                           date
                           relevance_score
```

### Gates
```
Database → Dataset:     database.access_level <= agent.clearance  [property gate]
API → Endpoint:         api.auth_required == false OR
                        agent.has_api_key(api.name)               [property gate]
Dataset → Record:       (ungated once dataset is accessible)
Endpoint → response:    api.rate_limit > 0                        [property gate]
KnowledgeBase → Article: (ungated — always searchable)
Report → findings:      report.status == "published"              [property gate]
```

### Tools
```
Agent READ:  search_databases, query_dataset, call_api, search_knowledge_base,
             get_article, list_reports, get_report, get_dataset_schema,
             get_api_docs, compute_statistics
Agent WRITE: create_report, update_report, add_finding, request_api_access,
             request_database_access, save_query_results
User READ:   view_report, view_findings
User WRITE:  approve_methodology, accept_findings, provide_constraints,
             grant_database_access
```

### Example Task (information synthesis, depth 3)
```
Generator plants:
  1. User wants: "Compare Q4 sales performance across regions"
  2. Sales data is in Database A (requires user to grant access)
  3. Regional mapping is in Database B (freely accessible)
  4. Industry benchmarks are in an API (requires requesting access)
  5. Previous analysis exists in a Report (published)

Agent must:
  1. Understand user query
  2. Search for relevant datasets → find Database A and B
  3. Request access to Database A from user → user grants
  4. Query both datasets
  5. Find the API for industry benchmarks → request access
  6. Cross-reference sales data with regional mapping
  7. Compare against industry benchmarks
  8. Find and read previous report for methodology
  9. Create new report with findings
  10. Present to user for acceptance

Goal: Report.status == "created"
      AND Report.findings is not empty
      AND Report references Dataset A and Dataset B
      AND User.accepted_findings == true
```

### Skills Tested
- Information discovery and access management
- Cross-referencing multiple data sources
- Following a research methodology
- Presenting findings and getting user buy-in
- Minimal state changes (mostly reads, few writes)


---


## The Structural Proof

All six worlds map to the same model:

| Aspect           | World 1        | World 2          | World 3        | World 4        | World 5         | World 6         |
|------------------|----------------|------------------|----------------|----------------|-----------------|-----------------|
| Node types       | 6              | 8                | 9              | 10             | 8               | 7               |
| Gate types used  | property+actor | actor+info       | property       | property       | actor+property  | property+actor  |
| Actors           | agent+user     | agent+user       | agent only     | agent only     | agent+user+3    | agent+user      |
| Primary task     | fix            | coordinate       | diagnose       | trace          | orchestrate     | synthesize      |
| Write intensity  | high           | medium           | medium         | medium         | high            | low             |
| Cross-references | few            | many             | some           | many           | few             | many            |
| User interaction | medium         | permission-based | none           | none           | heavy           | access+approval |

But structurally, every world is:
1. A graph of typed nodes with properties
2. Edges with gate conditions (property, actor, information)
3. Tools = operations on the graph (read, write)
4. Rules = constraints on valid operations
5. Projections = what each actor can see
6. Tasks = entry point + goal predicate over graph state

The SAME task generator works for all six.  It traverses the graph,
performs operations, records them, derives goals.  The difference is
just the CONTENT of the nodes and the MIX of gate types.


## What Changes Per World (LLM-Authored)

For each new world, the LLM authors:
1. ~5-10 entity types with fields (~50-100 lines)
2. ~5-15 relationships with gates (~30-60 lines)
3. ~5-20 rules (~20-40 lines)
4. ~100-200 lines of seed data
5. ~2-5 custom tools (~20-50 lines)
6. ~10-30 lines of projection spec
7. ~50-100 lines of policy

Total: ~300-600 lines per world, spread across 7 verified steps.


## What's the Same (Code)

- Tool derivation from schema
- Task generation by graph traversal
- Composition engine
- Solvability verification
- Depth/diversity controls
- Rendering to evaluation format


## What Would NOT Fit (Honest Limitations)

### Continuous/streaming interactions
Agent monitoring a live feed, reacting to events in real-time.
The graph is discrete snapshots, not continuous.  Could model as
periodic graph updates, but loses real-time character.

### Creative/generative tasks
"Write a marketing email" or "Design a logo."  Goal predicate
needs to evaluate quality, which requires LLM judge.  The graph
can represent INPUTS (brand guidelines, target audience) but
can't mechanically verify OUTPUT quality.

### Adversarial/competitive interactions
Negotiation, debate, games.  The "other player" changes strategy
based on the agent's moves.  Static graph can't model this —
you'd need a game tree or opponent model.

### Unbounded exploration
"Find the best restaurant nearby" — the answer space is open-ended.
Graph can represent a fixed set of restaurants, but can't model
the open-ended nature of real search.

These limitations are real but bounded.  The framework covers
the vast majority of structured tool-calling tasks that matter
for training general agents.
