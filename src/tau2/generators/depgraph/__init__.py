"""Dependency-graph task sampling and compilation."""

from tau2.generators.depgraph.compiler import CompileResult, preflight_and_compile
from tau2.generators.depgraph.context_bindings import (
    TaskContextBindingSpec,
    TaskContextBindingsDoc,
    dump_task_context_bindings,
    generate_ev_context_bindings,
    load_task_context_bindings,
)
from tau2.generators.depgraph.loaders import (
    load_graph_contract,
    load_sampling_request,
    load_task_specs,
)
from tau2.generators.depgraph.preflight import (
    TaskPreflightReport,
    run_task_preflight,
)
from tau2.generators.depgraph.review_bundle import (
    ReviewSourcePaths,
    build_review_bundle_markdown,
    infer_review_source_paths,
    infer_task_family,
    select_representative_tasks,
)
from tau2.generators.depgraph.runtime_scaffold import (
    generate_runtime_scaffold,
    load_persona_pool,
    load_runtime_defaults,
)
from tau2.generators.depgraph.runtime_narrative_checks import (
    check_runtime_narratives,
    load_narrative_briefs,
)
from tau2.generators.depgraph.runtime_checks import (
    check_contract_against_environment,
    check_runtime_against_environment,
    check_start_bindings_visibility,
    check_task_runtime_fields,
)
from tau2.generators.depgraph.runtime_surface import check_runtime_author_surface
from tau2.generators.depgraph.sampler import SampledTask, sample_task_intents
try:
    from tau2.generators.depgraph.verifiers_env import (
        DepgraphTaskConfig,
        DepgraphToolEnv,
        check_goal,
        compile_task_config,
    )
    from tau2.generators.depgraph.verifiers_rubric import DepgraphRubric
    from tau2.generators.depgraph.verifiers_compiler import (
        VerifiersCompileResult,
        compile_for_verifiers,
    )
except ImportError:
    pass
from tau2.generators.depgraph.solver import SearchResult, find_plan
from tau2.generators.depgraph.types import (
    ActionContract,
    ActionSchemaSpec,
    ActionSchemaVariantSpec,
    ActionExpectationSpec,
    BindingPredicateSpec,
    BindingSourceSpec,
    EnvAssertionSpec,
    EnvFunctionCallSpec,
    GraphContractSpec,
    RuntimeTaskSpec,
    SamplingRequestDoc,
    SamplingSeedSpec,
    SyncEffectSpec,
    SyncRuleSpec,
    TaskIntent,
    TaskSpecsDoc,
    TerminalProfileSpec,
    TerminalSchemaSpec,
)
