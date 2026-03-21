# Depgraph Two-Adapter Refinement

> **Status (2026-03-19):** This document captures the two-adapter architecture vision.
> Most kernel concepts (sections 3.1-3.5, 3.7) are implemented as described.
> Key deviations noted inline with `[CURRENT]` markers.

This note captures the architecture that is emerging from recent depgraph work.

It is not a replacement for `dependency_graph_domain_plan.md`. It is a cleanup and
refinement pass that makes explicit:

- what the shared depgraph kernel is responsible for,
- which runtime patterns we actually want to support,
- where tau2-specific and browser-specific concerns should live,
- and which cleanup moves would reduce recent one-off complexity.


## 1. What We Are Actually Building

The depgraph system is no longer just "a way to author tau2 domains."

It is a **task-sampling kernel** that:

1. authors a causal state machine,
2. samples valid start states via seed schemas,
3. proves sampled tasks are reachable by BFS,
4. emits compact terminal tasks by capturing goal state from solved terminal nodes,
5. and then hands those tasks to an **adapter-specific runtime**.

The runtime is not the kernel.

The kernel's job is:

- solvability,
- dependency structure,
- task diversity,
- and compact task emission.

The adapter's job is:

- to realize those sampled tasks in a concrete runtime,
- and to score whether the agent actually completed them.


## 2. The Two Adapter Patterns We Should Explicitly Support

### A. Tau2 Adapter

This is the collaborative / back-and-forth pattern.

Examples:

- `ev_charging_support`
- `telecom`-style domains

Key properties:

- assistant and user both exist as first-class actors,
- depgraph actions are intended to map 1:1 to runtime tool calls,
- sync behavior matters,
- stop gating matters,
- some user actions are causal,
- some user tools are knowledge-only,
- runtime compilation produces tau2 `Task` artifacts.

This is the adapter where:

- `sync_rules` and `sync_tools()` are meaningful,
- `stop_gate_map.yaml` is meaningful,
- policy and narrative scaffolding are meaningful,
- authoring is still close to runtime call structure.


### B. Browser-Embedded Adapter

This is the autonomous browser-agent pattern.

Examples:

- `amazon_shopping`

Key properties:

- there is no meaningful user simulator,
- the agent sees a synthetic browser environment,
- the agent-visible tools are generic browser tools such as
  `navigate`, `computer`, `get_page_text`,
- plus one or more adapter-level commit tools such as `submit_result`,
- depgraph actions are **not** 1:1 with agent-visible tool calls,
- instead, depgraph actions are **capabilities embedded in the browser world**,
- correctness still comes from the depgraph kernel, but runtime realization happens
  through browser affordances instead of direct tool exposure.

This is the adapter where:

- the depgraph action graph defines what must be possible,
- the browser environment is responsible for making those actions realizable,
- and environment audits are required to ensure the embedding is faithful.


## 3. Shared Kernel: What Should Be Stable Across Both Adapters

The following concepts are core depgraph kernel concepts and should not be framed as
"tau2-specific" going forward.

### 3.1 Solver State

The kernel reasons over:

- projected world state
- acquired bindings

Conceptually:

`node = (world, bindings)`

For tau2 domains, `world` may include assistant state plus projected user-causal state.
For browser domains, `world` should include the task-relevant browser/world projection,
including canonical answer facts and committed task-completion state.

The kernel should not care which adapter produced that state model.


### 3.2 Seed Schemas

Seed schemas are a strong abstraction and should remain central.

They give us:

- cartesian-product start-state generation,
- controllable diversity,
- programmatic domain fan-out,
- and a clean way to vary knowledge, blockers, branches, and fate flags.

This is the right abstraction for both adapters.


### 3.3 Action Contracts

Each action remains a transition contract:

- `requires_world`
- `requires_bindings`
- `effects_world`
- `effects_bindings`
- classification (`causal`, `knowledge-only`, `stutter-only`)

This is still the right kernel abstraction.

It gives us:

- causal ordering,
- knowledge gates,
- downstream dependency structure,
- and BFS solvability guarantees.


### 3.4 Bindings

Bindings should remain the kernel's representation of **agent-acquired knowledge**.

They should obey these rules:

1. A binding comes from an explicit source.
2. A binding has a canonical `world_path` anchor.
3. A binding is used downstream as a `requires_bindings` gate on at least one action.
4. If the canonical `world_path` changes, the binding is invalidated.

That is the right mental model.

We should avoid introducing extra ad hoc "volatile binding" policy beyond this lifecycle rule.

The behavior is:

- bindings represent the agent's current knowledge of a canonical world fact,
- bindings are usable as preconditions for later actions,
- bindings are dropped automatically when their canonical world source changes.

Binding acquisition does not have to mean a dedicated read-only action.

In browser domains especially, a causal action may both:

- change world state,
- and surface a fact in the screenshot/page text returned to the agent.

Examples:

- selecting a variant may change the current price and also acquire the binding for that
  current price because the updated page now visibly contains it,
- entering a ZIP code may change shipping state and also acquire the binding for the
  displayed shipping estimate.

Corollaries:

- `world_path` should be required.
- a binding that is not referenced by a downstream action's `requires_bindings` is dead
  and should not exist.
- "terminal-required knowledge" should not be modeled as terminal binding presence;
  it should be modeled as a final consuming action that requires the binding and
  commits some world-state effect.

The invalidation rule should be precise:

- after a full transition completes, including any sync behavior if the adapter uses it,
- compare the old and new values at the binding's canonical `world_path`,
- if the value changed, drop the binding,
- if the value did not change, keep it.

This is the only binding-lifecycle rule we need.


### 3.5 Terminal Profiles

Terminal profiles are kernel concepts, not runtime concepts.

They should describe terminal nodes over world state only.

A terminal node is a committed world state, not a knowledge snapshot.

So the right shape is:

- `requires_world`

and not terminal binding predicates.

The terminal profile is how the sampler knows:

- which solved world states count as valid tasks.

If a task needs some acquired knowledge in order to count as complete, that should
be represented by a final action between acquisition and terminality.

Pattern:

1. acquire binding
2. binding gates a final action
3. final action writes committed world state
4. terminal profile checks that committed world state

Examples:

- tau2: binding `iccid` gates `reprovision_profile`, which sets terminal world state
- browser: bindings for extracted product facts gate `submit_results`, which sets
  committed report / submission world state

This keeps terminality in the world model and keeps bindings as action-enabling
epistemic state.


### 3.6 Goal Capture

`[CURRENT: Goal capture via diff + capture paths was replaced. goal_world is now populated directly from the matched terminal profile's requires_world predicates. Dedup is by (seed_id, terminal_profile_id), not (goal_world, terminal_profile_id). goal_capture_paths no longer exists as a concept.]`

Once BFS reaches a terminal node:

1. keep the terminal profile id,
2. capture `goal_world` from configured capture paths,
3. dedup by `(goal_world, terminal_profile_id)`.

This is the right kernel behavior.

The kernel should stay opinionated here.

For browser domains, `goal_capture_paths` will often include both:

- committed completion state under `commit.*`,
- and the canonical answer/truth paths the runtime rubric needs in order to verify the
  submitted artifact.

The important point is that terminal matching is still world-only. Task identity comes
from the captured world, not from live binding presence.


### 3.7 Enums / Finite Variants

Finite domains and action schemas are one of the key reasons the BFS remains tractable.

We should continue to lean on:

- enums in world state,
- action schemas for finite variants,
- explicit branching by values rather than runtime free-form logic,
- and bounded finite action surfaces.

This applies equally to tau2 and browser domains.


## 4. The Main Cleanup Decision

We should stop treating "depgraph action" and "agent-visible runtime tool call" as universally
the same concept.

That is true for the tau2 adapter.

It is not true for the browser-embedded adapter.

So the right conceptual split is:

- **Kernel action**: a causal/knowledge transition in the sampled state machine.
- **Adapter realization**: how that transition becomes possible in a concrete runtime.

For tau2:

- realization is usually direct 1:1 tool execution.

For browser-embedded:

- realization is indirect through a synthetic browser whose generic tools expose the
  action as an affordance the agent can discover and invoke.


## 5. Browser-Embedded Domains Need an Explicit "Action Embedding" Layer

Browser-embedded domains need a more explicit state model than the current ad hoc
`p1` / `p2` style.

The clean model is:

- `truth.*`
- `surface.*`
- `K.*`
- `commit.*`

with semantic slots rather than hard-coded positional product ids.

`[CURRENT: For amazon_shopping, we kept the flat world structure (search.*, p1.*, filter.*, etc.) without truth/surface/K/commit namespacing. Ground truth lives in the entity sampler, not in the world state. The kernel tracks navigation (what the agent did), not extracted values.]`

### 5.0 Browser State Structure

#### A. `truth.*`

Canonical task-instance facts.

Examples:

- `truth.slot.primary.current_price_cents`
- `truth.slot.primary.seller_name`
- `truth.slot.primary.shipping_cost_cents`
- `truth.slot.candidate_a.rating`

These are the ground-truth facts for the task instance.

They are the canonical "answer world" for the task:

- the facts bindings anchor to,
- the facts the final submission is checked against,
- and, when needed, the facts that should be carried into emitted task artifacts via
  `goal_capture_paths`.


#### B. `surface.*`

Current browser/UI state.

Examples:

- `surface.page.kind = results | detail | cart`
- `surface.slot.primary.focused = true`
- `surface.slot.primary.variant = blue`
- `surface.zip_applied = true`

These paths describe what the browser is currently showing and what the agent has navigated to.


#### C. `K.*` bindings

Current agent knowledge of canonical truth paths.

Examples:

- `K.slot.primary.price_seen`
- `K.slot.primary.seller_seen`

These bindings are anchored to `truth.*` world paths. The actual value lives in `truth.*`;
the binding only represents that the agent currently knows it.

In browser domains, acquiring a binding does not require a separate "read" action.

If an action causes the browser to render a page state where a canonical fact is visible
in the returned screenshot or page text, that action can acquire the binding directly.

Examples:

- opening a detail page may acquire title and price bindings if those values are visible
  by default,
- selecting a variant may update the current price and simultaneously acquire the new
  price binding,
- opening shipping details may acquire the shipping estimate binding.


#### D. `commit.*`

Committed task-completion state written by final consuming actions.

Examples:

- `commit.report.primary.price_committed = true`
- `commit.report.primary.seller_committed = true`
- `commit.submission.received = true`
- `commit.submission.schema = listing_report_basic`

These are the world facts that terminal profiles and goal capture should use.


### 5.0A Semantic Slots Instead of `p1` / `p2`

Browser-agent tasks should use semantic slots rather than positional ids.

Good examples:

- `slot.primary`
- `slot.candidate_a`
- `slot.candidate_b`
- `slot.target_variant`
- `slot.best_offer`

This is cleaner than `p1` / `p2` because:

- task role is separated from screen rank,
- the same task shape can map to search results, category browsing, or detail-first flows,
- and the browser embedding can decide how a slot is realized on the page.

The domain still needs a finite set of slot roles so BFS remains tractable, but those
roles should be semantic rather than positional.

`[CURRENT: For amazon_shopping, we kept positional p1/p2/p3 naming rather than semantic slots. The positions map directly to search result rank, which IS the identity in this domain. Semantic slots may be more appropriate for future domains where role differs from position.]`

This is the biggest architectural cleanup item.

Right now the browser pattern exists in code, but not yet as a clean first-class concept.

The missing concept is:

- **action embedding**

Meaning:

For every depgraph action, the browser environment must define how that action is realized
through the generic browser interface.

Examples:

- `filter_prime_only`
  - not a separate agent-visible tool
  - realized by a click on an embedded Prime filter control
- `slot.primary.shipping_checked`
  - realized by entering ZIP code or opening delivery info in the browser
- `submit_results`
  - realized by the agent calling a non-browser commit tool such as `submit_result(data=...)`

The browser agent only sees the generic browser tools plus the commit tool.

Depgraph actions are therefore not "tool calls the agent sees." They are authored
capabilities that the environment must make realizable through that smaller tool surface.

### 5.1 What the embedding layer should guarantee

For each action:

1. the preconditions can become satisfiable in the rendered browser state,
2. there is at least one valid browser interaction sequence that realizes it,
3. the resulting world/binding effects match the depgraph contract,
4. the action remains observable/auditable in tests.


### 5.2 What artifact should represent this

We should introduce a browser-domain artifact such as:

- `browser_embedding.yaml`

YAML is the better default than hiding this in Python because it keeps the embedding
contract declarative and auditable alongside other depgraph-authored artifacts.

It should map:

- depgraph `action_id`
- to browser affordance / page location / interaction route
- plus expected world/binding deltas
- plus optional audit hints

This gives us a proper contract between:

- the sampled depgraph world,
- and the synthetic browser implementation.


### 5.3 Why this matters

Without an explicit embedding layer, browser domains tend to drift into:

- hand-authored browser logic,
- action-by-action implicit special cases,
- and fragile "it seems aligned" audits.

With an explicit embedding layer, we can preserve correct-by-construction semantics:

- the sampled action must be realizable,
- and the environment must prove it.


## 6. Adapter Boundaries We Should Clean Up

### 6.1 Kernel

Owns:

- `types.py`
- `semantics.py`
- `solver.py`
- `sampler.py`
- `preflight.py`
- `goal_capture.py`
  `[CURRENT: goal_capture.py was deleted. Its functionality is no longer needed since goal_world comes directly from terminal profiles.]`

Responsibilities:

- state semantics,
- binding semantics,
- BFS reachability,
- terminal matching,
- task emission.

The kernel should know nothing about:

- tau2 `Task` JSON,
- Playwright,
- screenshots,
- user simulation narratives,
- or browser selectors.


### 6.2 Tau2 Adapter

Owns:

- compilation into tau2 runtime tasks,
- stop-gate injection,
- runtime defaults / scaffold / env assertions,
- assistant/user runtime tool integration,
- sync behavior,
- narrative/policy enrichment.

This adapter is where 1:1 action-to-tool realization belongs.


### 6.3 Browser-Embedded Adapter

Owns:

- browser runtime tools (`navigate`, `computer`, `get_page_text`, `submit_result`),
- synthetic page generation,
- action embedding,
- browser-side world tracking,
- submission validation,
- environment audits ensuring depgraph action realizability.

This adapter should not be forced into tau2-style assumptions.


## 7. Scoring Model by Adapter

### Tau2 Adapter

End-of-task checks are mostly:

- world assertions,
- stop-gate observability,
- and optional action expectations.


### Browser-Embedded Adapter

End-of-task checks should be split:

1. **process / state score**
   - did the relevant world state reach the required terminal region?
2. **submission correctness score**
   - did the structured submission content match task truth?

For browser domains like `amazon_shopping`, the final checkable artifact is the submitted
payload, not a filled browser form and not merely a boolean `results.submitted`.

The clean browser pattern is:

1. browser actions acquire bindings against `truth.*`,
2. a final submit/commit action consumes those bindings,
3. that action writes `commit.*` world state,
4. terminal profiles and goal capture operate over that committed world state,
5. the runtime rubric separately compares the submitted payload against `truth.*`.

For nontrivial browser tasks, the final commit action should usually write richer
`commit.*` state than just `submission.received = true`.

Otherwise distinct task families collapse too aggressively under goal-world capture and
dedup. The committed world should preserve the task-relevant completion shape.

So this adapter should explicitly allow:

- depgraph terminal state proving the task was solvable and properly staged,
- runtime rubric checking the submitted artifact against ground truth.


## 8. Domain Authoring Model After Cleanup

### Shared domain-authored files

These should remain shared across both adapters:

- `graph_contract.yaml`
- `sampling_request.yaml`
- domain entity/task generation inputs where applicable


### Tau2-specific authored files

- `policy.md`
- `runtime_defaults.yaml`
- `stop_gate_map.yaml`
- `user_tools.py`
- `environment.py`
- tau2 runtime enrichment files


### Browser-embedded-specific authored files

- browser environment package
- page rendering / server / browser logic
- submission rubric logic
- action embedding spec
- browser audit tests


## 9. Practical Cleanup Recommendations

### 9.1 Rename the mental model in docs

The docs should stop speaking as if there is only:

- "tau2 path" and
- "verifiers path"

That split is too shallow.

The real split is:

- **tau2 collaborative adapter**
- **browser-embedded autonomous adapter**

The generic 1:1 verifiers environment can still exist, but it should be treated as a
simple autonomous adapter, not as the defining non-tau2 pattern.


### 9.2 Make "binding invalidation by world_path change" the single lifecycle rule

We should standardize the language around bindings:

- binding acquired from source,
- binding usable downstream,
- binding invalidated when canonical world source changes.

Avoid layering on separate policy words unless they materially change behavior.

Precisely:

- compare old and new values at the canonical `world_path`,
- if the value changed, drop the binding,
- if the value did not change, keep the binding.


### 9.3 Keep terminal profiles world-only

This should remain the canonical way to define what counts as a sampled terminal node.

Do not define terminality in terms of acquired bindings.

If knowledge matters for completion, make it gate a final consuming action whose
effects are in world state. Then let terminal profiles check that world state.


### 9.4 Add a first-class browser embedding contract

This is the most important cleanup missing today.

For browser domains, we should not rely on environment code alone to encode the mapping from:

- depgraph action
- to browser-realizable capability

That mapping should become explicit and testable.


### 9.4A Use semantic slots plus `truth` / `surface` / `commit` layering

This should be the default browser-domain modeling pattern.

- `truth.*` for canonical answer facts
- `surface.*` for current browser-visible state
- `K.*` for acquired knowledge of `truth.*`
- `commit.*` for world-state completion markers written by final actions

This model aligns much better with screenshot-driven autonomous agents than hard-coded
`p1` / `p2` positional paths.

It also makes the browser pattern line up with the sampling kernel:

- bindings gate the final consuming action,
- the final consuming action writes committed world state,
- terminal profiles stay world-only,
- and goal capture can carry both completion state and canonical answer facts.


### 9.5 Separate kernel audits from adapter audits

We should be able to say clearly:

- kernel audit: is the sampled task reachable in the depgraph state machine?
- adapter audit: is every sampled action faithfully realizable in the runtime?

For browser domains, both are necessary.


### 9.6 Treat sync rules as tau2-adapter semantics, not kernel semantics

`[CURRENT: Sync rules are now run via run_contract_sync() in tau2 domains — the contract YAML is the single source of truth. Domain sync_tools() calls the generic runner plus adapter-specific view projections.]`

The kernel can support sync rules.

But sync rules are only needed for patterns where there is a split between:

- causal runtime state,
- and projected/user-observable/runtime-derived state.

That is mostly a tau2 concern.

We should stop talking about sync as if it is a universal domain feature.


## 10. Suggested Cleanup Roadmap

### Phase 1: Documentation / Naming Cleanup

1. Document the kernel as adapter-agnostic.
2. Document the two target adapter patterns explicitly.
3. Clarify that terminal profiles are world-only.
4. Clarify binding lifecycle and invalidation rules.
5. Document the browser `truth` / `surface` / `K` / `commit` pattern and semantic slots.


### Phase 2: Browser Adapter Formalization

1. Introduce a browser action-embedding artifact.
2. Introduce semantic-slot browser world modeling in the reference browser domain.
3. Standardize final submit/commit actions for browser domains.
4. Build loader/validator support for the embedding artifact.
5. Refactor browser audits to validate embedding coverage mechanically.
6. Make `amazon_shopping` the canonical browser-embedded reference domain.


### Phase 3: Module Boundary Cleanup

Refactor `src/tau2/generators/depgraph/` conceptually into:

- kernel
- tau2 adapter
- browser adapter

This may be done incrementally without immediately moving files, but the module boundary
should become clearer in naming and documentation.


### Phase 4: Domain Migration and Consistency

1. Make `ev_charging_support` the reference tau2 collaborative domain.
2. Make `amazon_shopping` the reference browser-embedded autonomous domain.
3. Use both as regression anchors for future depgraph changes.


## 11. Summary

The right cleanup is not "make everything look like tau2" and not "make everything look
like a browser benchmark."

The right cleanup is:

- a stable depgraph kernel,
- explicit adapter boundaries,
- explicit browser action embedding,
- and domain authoring contracts that preserve correct-by-construction sampling while
  allowing different runtime realization patterns.

That gives us one sampling language and two runtime realization styles:

- collaborative tau2 execution,
- autonomous browser-embedded execution.
