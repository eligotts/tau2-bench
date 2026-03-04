# Prompt 09: Registry Wiring + End-to-End Verification

## Instruction

Finalize tau2 runtime integration and prove that depgraph artifacts compile and load through the real registry path.

Inputs:

- `src/tau2/domains/<domain>/environment.py`
- `src/tau2/registry.py`
- `data/tau2/domains/<domain>/graph_contract.yaml`
- `data/tau2/domains/<domain>/stop_gate_map.yaml`
- `data/tau2/domains/<domain>/task_specs.runtime.yaml`

Author one minimal file edit at a time.

## Step 09.1: Registry Wiring

Edit:

- `src/tau2/registry.py`

Requirements:

1. Import `<domain>.environment.get_environment` and `<domain>.environment.get_tasks`.
2. Register both domain constructor and tasks loader.
3. Keep ordering/style consistent with existing registry entries.

Validation:

```bash
uv run python - <<'PY'
from tau2.registry import registry
print("<domain>" in registry.get_domains())
print("<domain>" in registry.get_task_sets())
PY
```

Pass condition:

- Both checks print `True`.

## Step 09.2: Full Preflight via Registry

Run:

```bash
uv run python -m tau2.generators.depgraph.run_preflight \
  --graph-contract data/tau2/domains/<domain>/graph_contract.yaml \
  --task-specs data/tau2/domains/<domain>/task_specs.runtime.yaml \
  --domain <domain> \
  --stop-gate-map data/tau2/domains/<domain>/stop_gate_map.yaml \
  --strict-tool-coverage
```

Pass condition:

- All tasks pass SAT checks and contract/runtime alignment checks.
- All tasks pass runtime instruction checks (explicit completion criterion + `###STOP###` guidance).
- Stop-gate runtime alignment passes when `--stop-gate-map` is provided.

## Step 09.3: Compile via Registry

Run:

```bash
uv run python -m tau2.generators.depgraph.run_compile \
  --graph-contract data/tau2/domains/<domain>/graph_contract.yaml \
  --task-specs data/tau2/domains/<domain>/task_specs.runtime.yaml \
  --domain <domain> \
  --stop-gate-map data/tau2/domains/<domain>/stop_gate_map.yaml \
  --out data/tau2/domains/<domain>/tasks.depgraph.json
```

Pass condition:

- Compile succeeds and writes `tasks.depgraph.json` with zero task failures.

## Step 09.4: Runtime Load Smoke Test

Run:

```bash
uv run python - <<'PY'
from tau2.registry import registry
tasks = registry.get_tasks_loader("<domain>")()
env = registry.get_env_constructor("<domain>")()
print("loaded_tasks", len(tasks))
print("env_domain", env.get_domain_name())
PY
```

Pass condition:

- Tasks load and environment constructs through registry path.

## Step 09.5: Short Simulation Smoke (Recommended)

Run:

```bash
uv run tau2 run \
  --domain <domain> \
  --task-set-name <domain> \
  --num-tasks 2 \
  --agent-llm gpt-5-mini \
  --user-llm gpt-5-mini
```

Pass condition:

- No runtime crashes.
- No immediate `###OUT-OF-SCOPE###` on normal tasks.
- At least one task reaches terminal state with non-zero reward.

## Deliverable

Summarize:

1. files authored/edited
2. validation commands run
3. pass/fail status per step
4. remaining blockers (if any)
