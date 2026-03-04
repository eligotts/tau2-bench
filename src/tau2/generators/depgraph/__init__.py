"""Dependency-graph task preflight scaffolding."""

from tau2.generators.depgraph.compiler import CompileResult, preflight_and_compile
from tau2.generators.depgraph.loaders import (
    load_graph_contract,
    load_sampling_request,
    load_task_specs,
)
from tau2.generators.depgraph.preflight import (
    TaskPreflightReport,
    run_task_preflight,
)
from tau2.generators.depgraph.runtime_checks import (
    check_contract_against_environment,
    check_runtime_against_environment,
    check_task_runtime_fields,
)
from tau2.generators.depgraph.sampler import SampledTask, sample_task_intents
from tau2.generators.depgraph.solver import SearchResult, find_plan
from tau2.generators.depgraph.types import (
    ActionContract,
    ActionExpectationSpec,
    EnvAssertionSpec,
    EnvFunctionCallSpec,
    FactSourceSpec,
    GraphContractSpec,
    InvariantSpec,
    RuntimeTaskSpec,
    SamplingRequestDoc,
    SamplingSeedSpec,
    TaskIntent,
    TaskSpecsDoc,
)

__all__ = [
    "ActionContract",
    "ActionExpectationSpec",
    "CompileResult",
    "EnvAssertionSpec",
    "EnvFunctionCallSpec",
    "FactSourceSpec",
    "GraphContractSpec",
    "InvariantSpec",
    "RuntimeTaskSpec",
    "SampledTask",
    "SamplingRequestDoc",
    "SamplingSeedSpec",
    "SearchResult",
    "TaskIntent",
    "TaskPreflightReport",
    "TaskSpecsDoc",
    "check_contract_against_environment",
    "check_runtime_against_environment",
    "check_task_runtime_fields",
    "find_plan",
    "load_graph_contract",
    "load_sampling_request",
    "load_task_specs",
    "preflight_and_compile",
    "run_task_preflight",
    "sample_task_intents",
]
