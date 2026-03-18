# Tau2 Domains

This folder contains the runnable domain runtime packages for Tau2.

Authoring for new domains is centered on the depgraph pipeline. The runtime code here is
the execution surface that those authored/compiled artifacts load through.

## Domain Structure

Each domain has its own folder with the following structure:

- `data_model.py`: Defines the data models for the domain. 
    - This implements the `DB` class, which is a base class for all domain databases.
- `user_data_model.py`: Defines the data models for the user data for the domain.
    - This implements the `DB` class, which is a base class for all domain user databases.
- `tools.py`: Defines the tools for the domain. 
    - Implements `ToolKitBase` class, which is a base class for all domain toolkits. 
- `user_tools.py`: Defines the user tools for the domain.
    - Implements `ToolKitBase` class, which is a base class for all domain toolkits. 
- `environment.py`: Defines the environment for the domain. 
    - Implements `get_environment()` functions that returns an `Environment` instance for the domain.
    - Implements `get_tasks()` functions that returns a list of tasks for the domain.
- `utils.py`: Defines the utility functions for the domain.

## Data Storage

All the data for the domain is stored in `data/tau2/domains/<domain_name>` folder.
Common runtime files:
- task file:
  - existing domains may use `tasks.json`
  - depgraph-authored domains compile to `tasks.depgraph.json`
- optional split file (for example `split_tasks.json` or `split_tasks.depgraph.json`)
- `policy.md`
- `db.json`
- `user_db.json`

For depgraph-authored domains, `user_data_model.py`, `user_tools.py`, and
`user_db.json` are part of the required package shape. The user DB should be a
clean baseline state with an empty stop-gate configuration; task-specific user
state must come from runtime init actions, not from mutating the checked-in seed
file per task.

Depgraph-authored domains additionally keep their authoring artifacts in the same data
directory, for example:
- `graph_contract.yaml`
- `sampling_request.yaml`
- `runtime_defaults.yaml`
- `personas.yaml`
- `stop_gate_map.yaml`
- `task_specs.sampled.yaml`
- `task_specs.runtime.scaffold.yaml`
- `task_specs.runtime.yaml`

## Tests
Domain tests live under `tests/test_domains/`.

To run tests:
```sh
pytest tests/test_domains/test_<domain_name>
```

## Registering your domain
To make a domain runnable through `tau2`, register both its environment constructor and
task loader in `src/tau2/registry.py`.

In `registry.py`:
```python
from tau2.domains.your_domain.environment import get_environment as your_domain_get_environment
from tau2.domains.your_domain.environment import get_tasks as your_domain_get_tasks
...
registry.register_domain(your_domain_get_environment, "your_domain_name")
registry.register_tasks(your_domain_get_tasks, "your_domain_name")
```
