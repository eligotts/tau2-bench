# Wide Browse Domain — Build Plan

> **Status (2026-03-19):** This is a design plan for a future multi-domain browser benchmark.
> It has NOT been implemented yet. The amazon_shopping domain (which IS implemented) uses
> a simpler model — see `data/tau2/domains/amazon_shopping/graph_contract.yaml`.
> Some concepts here (goal_capture_paths, semantic slots) were superseded by the current
> kernel design. See `docs/prompts/depgraph/` for current authoring patterns.

> Verifiers-path domain modeling browser automation tasks.
> Source traces: `/Users/eligottlieb/Downloads/verified_trace_threads_inline_20260311_1626/`

## Overview

Synthetic domain that mirrors real browser automation traces across 13 websites and 6 task
categories. Uses the depgraph BFS system to generate verified-solvable tasks with structural
diversity. Targets the **verifiers adapter** (agent-only `StatefulToolEnv`, no user simulator).

---

## 1. Tool Mapping (Trace → Synthetic)

Keep 9 of the 15 trace tools. Drop agent-internal tools (`write`, `update_todo_list`,
`update_todo_status`) and rarely-used tools (`bash`, `load_skill`, `tabs_context`).

| Trace Tool (calls) | Synthetic Signature | Discretization Strategy |
|---|---|---|
| `navigate` (75) | `navigate(db, target: Literal["site_home", "search_page", "results_page", "detail_page", "next_page", "alternative_url"])` | URL → 6 page-type enums |
| `computer` (431) | `computer(db, action: Literal["click", "type", "scroll", "press_key", "select_all"], target: Literal["search_button", "result_item", "next_page_btn", "filter_option", "form_field", "nav_link", "close_popup"])` | Pixel coords → element enums. Most uses become **action schema variants** |
| `read_page` (22) | `read_page(db, filter: Literal["all", "interactive"] = "all")` | Direct mapping; returns structured page description |
| `get_page_text` (41) | `get_page_text(db)` | Direct mapping; returns text from current page state |
| `search_web` (22) | `search_web(db, query_type: Literal["find_site", "find_alternative", "error_recovery", "verify_info"])` | Free-text query → 4 intent enums |
| `form_input` (12) | `form_input(db, field: Literal["primary", "secondary", "date", "filter_1", "filter_2"], value: Literal["value_a", "value_b", "value_c"])` | Ref → field enum; free values → value enums |
| `find` (3) | `find(db, target: Literal["links", "buttons", "form_fields", "data_elements", "navigation"])` | NL query → 5 element-type enums |
| `fetch_url` (12) | `fetch_url(db, target: Literal["current_page", "detail_url", "api_endpoint"])` | URL → 3 target enums |
| `submit_result` (31) | `submit_result(db)` | No params — DB already has compiled results |

---

## 2. DB Model (World State)

```python
db = {
    # ── Navigation state (5 paths) ──
    "nav.on_target_site":       False,   # reached the right domain
    "nav.page_type":            "blank", # blank|home|search_form|results_list|detail|error|paywall
    "nav.page_loaded":          False,   # content is accessible
    "nav.pages_visited":        0,       # 0|1|2|3 (pagination depth)
    "nav.tab_count":            1,       # 1|2 (multi-tab tasks)

    # ── Form state (5 paths) ──
    "form.primary_filled":      False,   # origin / search term / main query
    "form.secondary_filled":    False,   # destination / location / refinement
    "form.date_filled":         False,   # date or date range
    "form.filters_applied":     False,   # price / stops / rating / etc.
    "form.submitted":           False,   # search form submitted

    # ── Content / extraction state (5 paths) ──
    "content.structure_known":  False,   # read_page completed on current page
    "content.text_extracted":   False,   # get_page_text completed
    "content.items_found":      "none",  # none|few|many (what the page has)
    "content.items_extracted":  "none",  # none|partial|complete (what we captured)
    "content.detail_extracted": False,   # visited + extracted detail page(s)

    # ── Error injection flags (set by seed, read by tools) ──
    "site.load_behavior":       "normal",  # normal|page_not_found|paywall|blocked|timeout
    "site.detail_behavior":     "normal",  # normal|paywall|blocked
    "site.fetch_behavior":      "normal",  # normal|rate_limited|blocked

    # ── Error encounter / recovery state (mutated at runtime) ──
    "error.encountered":        False,   # True once an error fires
    "error.type":               "none",  # what error was hit (mirrors the behavior flag value)
    "error.alternative_found":  False,   # search_web found a workaround
    "error.recovered":          False,   # recovery action succeeded

    # ── Results state (2 paths) ──
    "results.compiled":         False,   # data assembled for submission
    "results.submitted":        False,   # submit_result called

    # ── Task metadata (set by seed, gates which subgraph is active) ──
    "task.type":                "search",  # search|direct_extract|multi_page|form_fill
    "task.requires_form":       True,      # whether form filling lane is active
    "task.requires_detail":     False,     # whether detail page visits are needed
    "task.site_category":       "travel",  # travel|jobs|shopping|research|real_estate
}
```

**25 projected world paths** for BFS + 4 task metadata paths (seed-controlled, read-only).

---

## 3. Error Injection Model

Errors are **deterministic world-state flags** set by the seed. They fire exactly once
when the agent takes the triggering action, then recovery clears them so retry succeeds.

### Lifecycle of an error

```
Seed sets:           site.load_behavior = "paywall"
                     error.encountered = false

Agent calls:         navigate(target="site_home")
Tool checks:         site.load_behavior != "normal" AND error.encountered == false
                     → ERROR fires
Tool mutates:        error.encountered = true
                     error.type = "paywall"
                     nav.page_type = "error"
                     nav.page_loaded = false
Tool returns:        "Error: paywall - content behind login wall"

Agent recovers:      read_page → detect_error (acquires K.error_info)
                     search_web → search_alternative (sets error.alternative_found = true)
                     navigate → recover_via_alternative
                         → sets error.recovered = true
                         → sets site.load_behavior = "normal"  ← CLEARS the flag
                         → sets nav.page_loaded = true

Agent retries:       navigate(target="site_home")
Tool checks:         site.load_behavior == "normal" → SUCCESS
                     → normal navigation proceeds
```

### Three independent injection points

| Flag | What triggers it | Recovery path |
|---|---|---|
| `site.load_behavior` | `navigate` to site home | search_web → find alt URL → navigate to alt |
| `site.detail_behavior` | `navigate` to detail page | fetch_url → direct HTTP extraction |
| `site.fetch_behavior` | `fetch_url` call | search_web → find cached/mirror → navigate there |

Each injection point has its own pair of contract actions (error variant + success variant),
and its own recovery sub-lane. They can be toggled independently in seeds, so:
- 0 errors active = clean path
- 1 error active = one recovery detour
- 2 errors active = two recovery detours (different points in the task)
- 3 errors active = maximum complexity

### Contract modeling

For each injection point, we split into two value-gated action variants:

```yaml
# Normal: site loads fine
- action_id: navigate_to_site_ok
  tool_name: navigate
  requires_world:
    - {path: site.load_behavior, value: normal}
  effects_world:
    - {path: nav.on_target_site, set: true}
    - {path: nav.page_type, set: home}
    - {path: nav.page_loaded, set: true}

# Error: site fails to load (fires once)
- action_id: navigate_to_site_fail
  tool_name: navigate
  requires_world:
    - {path: site.load_behavior, op: neq, value: normal}
    - {path: error.encountered, value: false}
  effects_world:
    - {path: error.encountered, set: true}
    - {path: nav.page_type, set: error}
    - {path: nav.page_loaded, set: false}

# Recovery clears the flag → re-enables the _ok variant
- action_id: recover_site_load
  tool_name: navigate
  requires_world:
    - {path: error.alternative_found, value: true}
    - {path: error.type, op: neq, value: none}
  effects_world:
    - {path: site.load_behavior, set: normal}    # ← CLEARS the error
    - {path: error.recovered, set: true}
    - {path: nav.on_target_site, set: true}
    - {path: nav.page_type, set: home}
    - {path: nav.page_loaded, set: true}
```

BFS sees this cleanly:
- Seed with `site.load_behavior=normal` → `navigate_to_site_ok` is enabled, `_fail` is not
- Seed with `site.load_behavior=paywall` → `navigate_to_site_fail` fires → recovery lane → `recover_site_load` clears flag → rest of task proceeds normally

---

## 4. Graph Contract — All Actions

### Navigation lane

| action_id | tool | classification | requires_world | requires_bindings | effects_world | effects_bindings |
|---|---|---|---|---|---|---|
| `navigate_to_site_ok` | `navigate` | causal | `site.load_behavior=normal` | — | `nav.on_target_site=true, nav.page_type=home, nav.page_loaded=true` | — |
| `navigate_to_site_fail` | `navigate` | causal | `site.load_behavior≠normal, error.encountered=false` | — | `error.encountered=true, nav.page_type=error, nav.page_loaded=false` | — |
| `navigate_to_search` | `navigate` | causal | `nav.on_target_site=true, task.requires_form=true` | — | `nav.page_type=search_form` | — |
| `navigate_to_results` | `navigate` | causal | `form.submitted=true` | — | `nav.page_type=results_list, nav.page_loaded=true, content.structure_known=false, content.text_extracted=false` | — |
| `navigate_to_detail_ok` | `navigate` | causal | `nav.page_type=results_list, site.detail_behavior=normal` | `K.result_urls` | `nav.page_type=detail, nav.page_loaded=true, content.structure_known=false, content.text_extracted=false` | — |
| `navigate_to_detail_fail` | `navigate` | causal | `nav.page_type=results_list, site.detail_behavior≠normal, error.encountered=false` | `K.result_urls` | `error.encountered=true, error.type=<from_flag>, nav.page_type=error, nav.page_loaded=false` | — |
| `navigate_next_page` | `navigate` | causal | `nav.page_type=results_list, content.items_extracted≠none` | — | `nav.pages_visited→+1, content.structure_known=false, content.text_extracted=false` | — |

### Form lane (action schema: `computer_fill_form`)

Schema expands to 4 concrete actions via `action_schemas`:

| variant / action_id | requires_world | effects_world | tool_arg_literals |
|---|---|---|---|
| `computer_fill_primary` | `nav.page_type=search_form` | `form.primary_filled=true` | `{action: "type", target: "form_field", text: "primary_value"}` |
| `computer_fill_secondary` | `nav.page_type=search_form` | `form.secondary_filled=true` | `{action: "type", target: "form_field", text: "secondary_value"}` |
| `computer_fill_date` | `nav.page_type=search_form` | `form.date_filled=true` | `{action: "type", target: "form_field", text: "date_value"}` |
| `computer_apply_filters` | `nav.page_type=search_form` | `form.filters_applied=true` | `{action: "click", target: "filter_option"}` |

Plus standalone:

| action_id | tool | requires_world | effects_world |
|---|---|---|---|
| `computer_submit_search` | `computer` | `form.primary_filled=true, form.secondary_filled=true` | `form.submitted=true` |

### Extraction lane

| action_id | tool | classification | requires_world | requires_bindings | effects_world | effects_bindings |
|---|---|---|---|---|---|---|
| `read_page_structure` | `read_page` | knowledge-only | `nav.page_loaded=true` | — | — | `K.page_structure` |
| `identify_form_fields` | `read_page` | knowledge-only | `nav.page_type=search_form` | — | — | `K.available_filters` |
| `extract_page_text` | `get_page_text` | causal | `nav.page_loaded=true` | — | `content.text_extracted=true` | — |
| `extract_list_items` | `get_page_text` | causal | `nav.page_type=results_list` | `K.page_structure` | `content.items_extracted=partial` | `K.result_urls` |
| `extract_detail_info` | `get_page_text` | causal | `nav.page_type=detail` | — | `content.detail_extracted=true, content.items_extracted=complete` | — |
| `fetch_page_ok` | `fetch_url` | causal | `nav.page_loaded=true, site.fetch_behavior=normal` | — | `content.text_extracted=true` | — |
| `fetch_page_fail` | `fetch_url` | causal | `site.fetch_behavior≠normal, error.encountered=false` | — | `error.encountered=true, error.type=rate_limited` | — |

### Error recovery lane

| action_id | tool | classification | requires_world | requires_bindings | effects_world | effects_bindings |
|---|---|---|---|---|---|---|
| `detect_error` | `read_page` | knowledge-only | `error.encountered=true` | — | — | `K.error_info` |
| `search_alternative` | `search_web` | causal | — | `K.error_info` | `error.alternative_found=true` | — |
| `recover_site_load` | `navigate` | causal | `error.alternative_found=true, site.load_behavior≠normal` | — | `site.load_behavior=normal, error.recovered=true, nav.on_target_site=true, nav.page_type=home, nav.page_loaded=true` | — |
| `recover_detail_load` | `navigate` | causal | `error.alternative_found=true, site.detail_behavior≠normal` | — | `site.detail_behavior=normal, error.recovered=true, nav.page_type=detail, nav.page_loaded=true` | — |
| `recover_fetch` | `fetch_url` | causal | `error.alternative_found=true, site.fetch_behavior≠normal` | — | `site.fetch_behavior=normal, error.recovered=true, content.text_extracted=true` | — |

### Results lane

| action_id | tool | classification | requires_world | effects_world |
|---|---|---|---|---|
| `compile_results` | `find` | causal | `content.items_extracted≠none` | `results.compiled=true` |
| `submit_results` | `submit_result` | causal | `results.compiled=true` | `results.submitted=true` |

### Summary

**~25 concrete actions** after schema expansion. Each action has clear requires/effects,
creating a rich BFS graph with multiple independent lanes, value-gated branching at 3
error injection points, and early convergence (extraction requires both navigation success
AND page structure knowledge).

---

## 5. Bindings (Knowledge Gates)

| binding_id | source_tool | purpose | world_path (volatile on) |
|---|---|---|---|
| `K.page_structure` | `read_page` | Needed before targeted extraction from results | `nav.page_type` |
| `K.available_filters` | `read_page` | Needed before applying search filters | `nav.page_type` |
| `K.result_urls` | `get_page_text` | Needed before navigating to detail pages | `content.items_found` |
| `K.error_info` | `read_page` | Needed before choosing recovery strategy | `error.type` |

**4 bindings from 2 source tools** (read_page, get_page_text).

Key binding dynamics:
- `K.page_structure` is volatile on `nav.page_type` — invalidated when navigating to new page,
  forcing re-read. This mirrors real traces where agents screenshot/read_page after every navigation.
- `K.result_urls` produced during extraction — gates detail navigation.
- `K.error_info` produced during error detection — gates recovery strategy choice.
- `K.available_filters` produced during form identification — optional gate for filter application.

Multi-binding gate: `extract_list_items` requires BOTH `nav.page_type=results_list` AND
`K.page_structure` (must read page structure before extracting items). This forces the agent
to do read_page before get_page_text on results pages.

---

## 6. Value-Gated Branching

### Branch family 1: Task type (seed-controlled)

| `task.type` | Active lanes | Depth range |
|---|---|---|
| `search` | navigate + form + extract + results | 8-12 |
| `direct_extract` | navigate + extract + results (skip form) | 4-6 |
| `multi_page` | navigate + extract + pagination + detail + results | 10-14 |

### Branch family 2: Error injection (seed-controlled, fires once)

| Error flag | Triggering action | Recovery lane | Extra depth |
|---|---|---|---|
| `site.load_behavior≠normal` | `navigate_to_site` | detect → search_alt → recover_site | +3 |
| `site.detail_behavior≠normal` | `navigate_to_detail` | detect → search_alt → recover_detail | +3 |
| `site.fetch_behavior≠normal` | `fetch_url` | detect → search_alt → recover_fetch | +2 |

### Branch family 3: Content richness (seed-controlled)

| `content.items_found` | Effect |
|---|---|
| `few` | Direct extraction, no pagination |
| `many` | May need pagination + detail pages |

### Cross-branch interactions

- Error + multi_page = most complex tasks (navigate errors + pagination + detail errors)
- Error + direct_extract = medium tasks (short path but with recovery detour)
- Clean + search = bread-and-butter tasks (form fill + extract + submit)

---

## 7. Seed Schemas

```yaml
seed_schemas:
  - schema_id: browse_tasks
    seed_id_template: "{task_family}_{error}_{complexity}"
    allowed_terminal_profiles: [complete_submission, partial_submission]
    goal_capture_paths:
      # [CURRENT: goal_capture_paths no longer exists. Terminal profiles define the goal directly.]
      - results.submitted
      - content.items_extracted
      - error.recovered
    min_depth: 4
    max_depth: 14
    dimensions:

      # ── Dimension 1: Task family (5 variants) ──
      - dimension_id: task_family
        variants:
          - variant_id: search_flight
            start_world:
              - {path: task.type, set: search}
              - {path: task.requires_form, set: true}
              - {path: task.requires_detail, set: false}
              - {path: task.site_category, set: travel}
          - variant_id: search_jobs
            start_world:
              - {path: task.type, set: search}
              - {path: task.requires_form, set: true}
              - {path: task.requires_detail, set: true}
              - {path: task.site_category, set: jobs}
            min_depth_delta: 2
          - variant_id: direct_extract
            start_world:
              - {path: task.type, set: direct_extract}
              - {path: task.requires_form, set: false}
              - {path: task.requires_detail, set: false}
              - {path: task.site_category, set: research}
          - variant_id: multi_page_research
            start_world:
              - {path: task.type, set: multi_page}
              - {path: task.requires_form, set: false}
              - {path: task.requires_detail, set: true}
              - {path: task.site_category, set: shopping}
            min_depth_delta: 3
          - variant_id: search_and_detail
            start_world:
              - {path: task.type, set: search}
              - {path: task.requires_form, set: true}
              - {path: task.requires_detail, set: true}
              - {path: task.site_category, set: real_estate}
            min_depth_delta: 2

      # ── Dimension 2: Error injection (4 variants) ──
      - dimension_id: error
        variants:
          - variant_id: clean
            start_world:
              - {path: site.load_behavior, set: normal}
              - {path: site.detail_behavior, set: normal}
              - {path: site.fetch_behavior, set: normal}
          - variant_id: site_not_found
            start_world:
              - {path: site.load_behavior, set: page_not_found}
              - {path: site.detail_behavior, set: normal}
              - {path: site.fetch_behavior, set: normal}
            min_depth_delta: 3
          - variant_id: detail_paywall
            start_world:
              - {path: site.load_behavior, set: normal}
              - {path: site.detail_behavior, set: paywall}
              - {path: site.fetch_behavior, set: normal}
            min_depth_delta: 3
          - variant_id: fetch_blocked
            start_world:
              - {path: site.load_behavior, set: normal}
              - {path: site.detail_behavior, set: normal}
              - {path: site.fetch_behavior, set: blocked}
            min_depth_delta: 2

      # ── Dimension 3: Content complexity (2 variants) ──
      - dimension_id: complexity
        variants:
          - variant_id: simple
            start_world:
              - {path: content.items_found, set: few}
          - variant_id: rich
            start_world:
              - {path: content.items_found, set: many}
            min_depth_delta: 2
```

### Expansion: 5 × 4 × 2 = **40 concrete seeds**

Each seed has a unique combination of task family + error condition + content complexity.
BFS from each seed explores different subgraphs and depth ranges.

### Seed → trace mapping

| Seed | Mirrors traces from |
|---|---|
| `search_flight_clean_simple` | google_flights single-date searches |
| `search_flight_clean_rich` | kayak multi-result flight sweeps |
| `search_jobs_clean_rich` | linkedin job search with detail pages |
| `direct_extract_clean_simple` | youtube video checks, github profiles |
| `direct_extract_site_not_found_simple` | golfnow page-not-found recovery |
| `multi_page_research_clean_rich` | amazon product research, airbnb listings |
| `search_and_detail_detail_paywall_rich` | zillow with paywall on details |
| `direct_extract_fetch_blocked_simple` | coindesk/airbnb blocked fetch recovery |

---

## 8. Terminal Profiles

```yaml
terminal_profiles:
  - profile_id: complete_submission
    description: "All requested data extracted and submitted successfully"
    requires_world:
      - {path: results.submitted, value: true}
      - {path: content.items_extracted, value: complete}

  - profile_id: partial_submission
    description: "Partial data extracted and submitted after error recovery"
    requires_world:
      - {path: results.submitted, value: true}
      - {path: content.items_extracted, value: partial}
      - {path: error.recovered, value: true}
```

- **Clean seeds** → can only reach `complete_submission` (no errors to recover from)
- **Error seeds** → can reach either `complete_submission` (full recovery + complete extraction)
  or `partial_submission` (recovered but only partial data — matches best-effort traces)

---

## 9. BFS Path Examples

### Example 1: `search_flight_clean_simple` (depth ~8)

```
navigate_to_site_ok → navigate_to_search → identify_form_fields
→ computer_fill_primary → computer_fill_secondary → computer_submit_search
→ navigate_to_results → read_page_structure → extract_list_items
→ compile_results → submit_results
```

Mirrors: google_flights Lisbon→London trace

### Example 2: `search_jobs_clean_rich` (depth ~12)

```
navigate_to_site_ok → navigate_to_search → identify_form_fields
→ computer_fill_primary → computer_fill_secondary → computer_submit_search
→ navigate_to_results → read_page_structure → extract_list_items
→ navigate_to_detail_ok → extract_detail_info
→ compile_results → submit_results
```

Mirrors: linkedin job search with detail page visits

### Example 3: `direct_extract_site_not_found_simple` (depth ~8)

```
navigate_to_site_fail → detect_error → search_alternative
→ recover_site_load → read_page_structure → extract_page_text
→ compile_results → submit_results
```

Mirrors: golfnow "Page Not Found" → search → alternate facility

### Example 4: `search_and_detail_detail_paywall_rich` (depth ~14)

```
navigate_to_site_ok → navigate_to_search → identify_form_fields
→ computer_fill_primary → computer_fill_secondary → computer_fill_date
→ computer_submit_search → navigate_to_results → read_page_structure
→ extract_list_items → navigate_to_detail_fail → detect_error
→ search_alternative → recover_detail_load → extract_detail_info
→ compile_results → submit_results
```

Mirrors: zillow property search where detail page hits paywall

---

## 10. Graph Topology Checklist

| Requirement | How satisfied |
|---|---|
| **≥ 2 bindings from different source_tools** | `K.page_structure` (read_page), `K.result_urls` (get_page_text), `K.error_info` (read_page), `K.available_filters` (read_page) — 2 source tools |
| **Multi-binding gate** | `extract_list_items` requires `K.page_structure` + `nav.page_type=results_list` |
| **Value-dependent branching** | `site.load_behavior` gates navigate success/fail; `task.type` gates form lane; `site.detail_behavior` gates detail success/fail |
| **Action ordering constraints** | `computer_fill_primary` before `computer_submit_search`; `extract_list_items` before `navigate_to_detail`; `detect_error` before `search_alternative` before `recover_*` |
| **Early convergence** | `extract_list_items` requires BOTH completed navigation (nav lane) AND `K.page_structure` (extraction lane) — mid-graph convergence |

---

## 11. Implementation Order

1. `graph_contract.yaml` + `tools.py` — Step 02v (contract + tool functions together)
2. `sampling_request.yaml` — Step 03 (seeds + terminal profiles)
3. Run sampler → `task_specs.sampled.yaml`
4. `verifiers_config.py` — Step 04v (system prompt + task prompt factory)
5. Compile + smoke test → verify end-to-end

---

## 12. Task Prompt Strategy

The `task_prompt_factory` maps task metadata to natural-language instructions that mirror
real trace prompts:

```python
def task_prompt_factory(task: TaskIntent, contract: GraphContractSpec) -> str:
    # Read seed-controlled metadata from start_world
    task_type = ...      # from task.type
    site_category = ...  # from task.site_category
    has_errors = ...     # from site.load_behavior etc.

    # Generate prompt that matches real trace style:
    # "Go to [site]. Search for [criteria]. For each result, extract: [fields].
    #  Submit structured results."
    # Error seeds get: "If the page doesn't load, find an alternative source."
```

Maps to real trace prompt structure:
- Task description (what to find)
- Site/URL to start from
- Extraction requirements (what fields to capture)
- Output schema (what to submit)
- Implicit error handling (present in complex tasks)
