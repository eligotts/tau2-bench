import types
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from tau2.generators.validate_domain import (
    _resolve_class,
    validate_policy,
    validate_sampling_request_file,
)


class TestValidateDomainClassResolution(unittest.TestCase):
    def test_resolve_class_prefers_exact_match(self):
        class EvChargingSupportTools:
            pass

        module = types.SimpleNamespace(EvChargingSupportTools=EvChargingSupportTools)
        actual_name, cls = _resolve_class(module, "EvChargingSupportTools")
        self.assertEqual(actual_name, "EvChargingSupportTools")
        self.assertIs(cls, EvChargingSupportTools)

    def test_resolve_class_accepts_acronym_capitalization(self):
        class EVChargingSupportTools:
            pass

        module = types.SimpleNamespace(EVChargingSupportTools=EVChargingSupportTools)
        actual_name, cls = _resolve_class(module, "EvChargingSupportTools")
        self.assertEqual(actual_name, "EVChargingSupportTools")
        self.assertIs(cls, EVChargingSupportTools)

    def test_resolve_class_returns_none_when_missing(self):
        module = types.SimpleNamespace()
        actual_name, cls = _resolve_class(module, "EvChargingSupportTools")
        self.assertIsNone(actual_name)
        self.assertIsNone(cls)


class TestValidateDomainPolicy(unittest.TestCase):
    def test_validate_policy_flags_contract_tool_drift(self):
        with TemporaryDirectory() as tmp_dir:
            domains_root = Path(tmp_dir)
            domain_dir = domains_root / "sample_domain"
            domain_dir.mkdir()
            (domain_dir / "policy.md").write_text("short policy mentioning nothing useful")
            (domain_dir / "graph_contract.yaml").write_text(
                """
version: 2
projection_fields:
  - agent.session.visible_code
bindings:
  - binding_id: visible_code
    source_tool: check_station_screen
    extraction_path: result.code
    world_path: agent.session.visible_code
    observability_all_of: []
    observability_any_of: []
actions:
  - action_id: acquire_visible_code
    requestor: user
    tool_name: check_station_screen
    classification: knowledge-only
    requires_world: []
    requires_bindings:
      - binding_id: visible_code
        acquired: false
    effects_world: []
    effects_bindings: [visible_code]
    tool_arg_bindings: {}
  - action_id: recover_session
    requestor: assistant
    tool_name: run_backend_diagnostics
    classification: causal
    requires_world: []
    requires_bindings:
      - binding_id: visible_code
        acquired: true
    effects_world: []
    effects_bindings: []
    tool_arg_bindings:
      visible_code: visible_code
  - action_id: stop_gate
    requestor: user
    tool_name: check_resolution_status
    classification: stutter-only
    requires_world: []
    requires_bindings: []
    effects_world: []
    effects_bindings: []
    tool_arg_bindings: {}
sync_rules: []
assistant_stutter_allowlist: []
""".strip()
            )

            with patch("tau2.generators.validate_domain._DATA_DOMAINS", domains_root):
                errors = validate_policy("sample_domain")

        self.assertTrue(
            any("check_station_screen" in error for error in errors),
            errors,
        )
        self.assertTrue(
            any("run_backend_diagnostics" in error for error in errors),
            errors,
        )
        self.assertTrue(any("resolved=true" in error for error in errors), errors)
        self.assertTrue(any("resolved=false" in error for error in errors), errors)

    def test_validate_policy_accepts_contract_aligned_policy(self):
        with TemporaryDirectory() as tmp_dir:
            domains_root = Path(tmp_dir)
            domain_dir = domains_root / "sample_domain"
            domain_dir.mkdir()
            (domain_dir / "policy.md").write_text(
                """
Use check_station_screen first, then run_backend_diagnostics.
Before stopping, call check_resolution_status.
Only stop when check_resolution_status returns resolved=true.
If check_resolution_status returns resolved=false, continue from the unmet items.
""".strip()
            )
            (domain_dir / "graph_contract.yaml").write_text(
                """
version: 2
projection_fields:
  - agent.session.visible_code
bindings:
  - binding_id: visible_code
    source_tool: check_station_screen
    extraction_path: result.code
    world_path: agent.session.visible_code
    observability_all_of: []
    observability_any_of: []
actions:
  - action_id: acquire_visible_code
    requestor: user
    tool_name: check_station_screen
    classification: knowledge-only
    requires_world: []
    requires_bindings:
      - binding_id: visible_code
        acquired: false
    effects_world: []
    effects_bindings: [visible_code]
    tool_arg_bindings: {}
  - action_id: recover_session
    requestor: assistant
    tool_name: run_backend_diagnostics
    classification: causal
    requires_world: []
    requires_bindings:
      - binding_id: visible_code
        acquired: true
    effects_world: []
    effects_bindings: []
    tool_arg_bindings:
      visible_code: visible_code
  - action_id: stop_gate
    requestor: user
    tool_name: check_resolution_status
    classification: stutter-only
    requires_world: []
    requires_bindings: []
    effects_world: []
    effects_bindings: []
    tool_arg_bindings: {}
sync_rules: []
assistant_stutter_allowlist: []
""".strip()
            )

            with patch("tau2.generators.validate_domain._DATA_DOMAINS", domains_root):
                errors = validate_policy("sample_domain")

        self.assertEqual(errors, [])


class TestValidateDomainSamplingRequest(unittest.TestCase):
    def test_validate_sampling_request_accepts_seed_schemas(self):
        with TemporaryDirectory() as tmp_dir:
            domains_root = Path(tmp_dir)
            domain_dir = domains_root / "sample_domain"
            domain_dir.mkdir()
            (domain_dir / "sampling_request.yaml").write_text(
                """
version: 1
max_tasks: 4
goal_capture_paths: [agent]
terminal_profiles:
  - profile_id: resolved
    requires_world:
      - path: agent.done
        op: eq
        value: true
seed_schemas:
  - schema_id: sample_cases
    seed_id_template: "{case}"
    allowed_terminal_profiles: [resolved]
    min_depth: 1
    max_depth: 2
    dimensions:
      - dimension_id: case
        variants:
          - variant_id: base
""".strip()
            )

            with patch("tau2.generators.validate_domain._DATA_DOMAINS", domains_root):
                errors = validate_sampling_request_file("sample_domain")

        self.assertEqual(errors, [])

    def test_validate_sampling_request_rejects_direct_seeds(self):
        with TemporaryDirectory() as tmp_dir:
            domains_root = Path(tmp_dir)
            domain_dir = domains_root / "sample_domain"
            domain_dir.mkdir()
            (domain_dir / "sampling_request.yaml").write_text(
                """
version: 1
max_tasks: 1
goal_capture_paths: [agent]
terminal_profiles:
  - profile_id: resolved
    requires_world:
      - path: agent.done
        op: eq
        value: true
seeds:
  - seed_id: legacy
    start_world: []
    allowed_terminal_profiles: [resolved]
    min_depth: 1
    max_depth: 1
""".strip()
            )

            with patch("tau2.generators.validate_domain._DATA_DOMAINS", domains_root):
                errors = validate_sampling_request_file("sample_domain")

        self.assertTrue(any("direct 'seeds' authoring has been removed" in e for e in errors))


if __name__ == "__main__":
    unittest.main()
