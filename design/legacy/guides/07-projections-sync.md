# Step 7: Projections + Sync

## Purpose

Define what the user can see (their projection of the world graph) and how
state changes by one actor propagate to the other (sync bridges).

The information asymmetry between agent and user projections drives the
interaction pattern: the agent sees raw graph state through tools, the user
sees a subset. When the agent fixes something, the user needs to see the
result. When the user performs an action, the agent needs to know.


## Input (locked from Steps 1-6)

- Full schema with entities and fields (Steps 1-2)
- Relationships and gates (Step 3)
- Tool suite including custom tools (Step 6)
- Actor gates that require user action (Step 3)


## Output

A `SyncSpec` containing a list of `SyncBridge` objects.

### SyncBridge
```
direction: str            # "user_to_agent" | "agent_to_user"

# For "user_to_agent":
user_trigger_field: str   # Field on user state that triggers sync
agent_entity: str         # Which agent entity gets updated
agent_field: str          # Which field on that entity
agent_value: Any          # What value to set
condition: str = None     # Optional condition string

# For "agent_to_user":
source_entity: str        # Which agent entity is the source
source_field: str         # Which field on that entity
target_field: str         # Which field on user state to update
```

### SyncSpec
```
bridges: list[SyncBridge]
```


## Constraints

- Every projected field must exist in the schema
- Every sync bridge must reference existing fields
- No circular bridges (A syncs to B syncs back to A)
- Every user-visible state change should have a sync path
- Actor gates from Step 3 should have corresponding user_to_agent bridges


## Examples

### Customer Service Sync
```python
SyncSpec(bridges=[
    # User verifies identity → agent can now access gated entities
    SyncBridge(
        direction="user_to_agent",
        user_trigger_field="identity_verified",
        agent_entity="Customer",
        agent_field="identity_verified",
        agent_value=True
    ),
    # User restarts device → agent sees updated device state
    SyncBridge(
        direction="user_to_agent",
        user_trigger_field="device_restarted",
        agent_entity="Device",
        agent_field="restarted",
        agent_value=True
    ),
    # Agent fixes account status → user can see their account is active
    SyncBridge(
        direction="agent_to_user",
        source_entity="Customer",
        source_field="account_status",
        target_field="visible_account_status"
    ),
    # Agent fixes order → user can see updated order status
    SyncBridge(
        direction="agent_to_user",
        source_entity="Order",
        source_field="status",
        target_field="visible_order_status"
    ),
])
```

### HR Onboarding Sync (multi-actor)
```python
SyncSpec(bridges=[
    # New hire signs documents → payroll setup can proceed
    SyncBridge(
        direction="user_to_agent",
        user_trigger_field="documents_signed",
        agent_entity="PayrollRecord",
        agent_field="documents_received",
        agent_value=True
    ),
    # New hire uploads badge photo → facilities can create badge
    SyncBridge(
        direction="user_to_agent",
        user_trigger_field="badge_photo_uploaded",
        agent_entity="FacilitiesSetup",
        agent_field="photo_received",
        agent_value=True
    ),
    # Agent completes IT setup → user sees their accounts are ready
    SyncBridge(
        direction="agent_to_user",
        source_entity="ITSetup",
        source_field="accounts_created",
        target_field="visible_accounts_ready"
    ),
])
```

### Agent-Only Domain (SRE)
```python
# No sync bridges needed — there's no user actor
SyncSpec(bridges=[])
```


## Anti-Patterns

**Missing sync for actor gates**
```python
# Step 3 has: ActorGate(actor="user", field="identity_verified", ...)
# But Step 7 has no user_to_agent bridge for identity_verified
# → Actor gate can never be satisfied!
```
Fix: every ActorGate in Step 3 needs a corresponding user_to_agent SyncBridge.

**Circular bridges**
```python
# BAD: Agent updates X → user sees X → user triggers Y → agent updates X
SyncBridge(direction="agent_to_user", source_field="status", target_field="user_status"),
SyncBridge(direction="user_to_agent", user_trigger_field="user_status",
           agent_field="status", ...)
```
Fix: sync should flow in one direction for each field. If the agent fixes a field,
the user sees it. If the user acts, the agent sees it. Not both for the same field.

**Non-existent fields**
```python
# BAD: "visible_order_total" doesn't exist on the user data model
SyncBridge(direction="agent_to_user", source_field="total",
           target_field="visible_order_total")
```


## Verification

Currently basic field existence checks. Full verification would check:
- All referenced fields exist in schema or user data model
- No circular bridge paths
- All actor gates have corresponding user_to_agent bridges
- All breakable fields visible to the user have agent_to_user bridges


## Common Failures & Fixes

**Actor gate not satisfiable**: Check that every ActorGate from Step 3 has a
matching SyncBridge. The bridge's `user_trigger_field` should match the gate's
`field`, and the bridge should set the agent-side value that satisfies the gate.

**Unnecessary complexity**: For agent-only domains (no user), skip this step
entirely — just return `SyncSpec(bridges=[])`. Only domains with user interaction
need sync bridges.
