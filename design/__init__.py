"""
Design: Two-layer framework for synthetic task generation.

Layer 1 (framework/): Format-agnostic world model
    World graph → Gates → Tools → Tasks → Generation → Verification

Layer 2 (tau2/): tau2-specific adapter
    Concept → Tool signatures → Faults → Sync → Policy → Rendering → Pipeline
"""
