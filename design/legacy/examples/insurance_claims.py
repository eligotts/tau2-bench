"""
Insurance Claims Domain: Deep dependency chain domain for hard tau2 tasks.

8 entities, depth 4, 13 breakable fields, 10 fault groups.

Gate chain:
  Policyholder ─[account_status + identity_verified]─> Policy
    Policy ─[status == "active"]─> Claim
      Claim ─[status == "under_review"]─> ClaimItem, Document, Assessment
        Assessment ─[status == "completed"]─> Payment

Agent must fix issues layer by layer: account → policy → claim → assessment → payment.
Each fix reveals the next problem. Progressive disclosure through topology.
"""

from design.framework import (
    Cardinality, EntitySpec, FieldSpec, FieldType,
    RelationshipSpec, SeedData, TopologyTargets, WorldConcept, WorldSchema,
    compose_blueprints, verify_concept, verify_perturbation_space,
    verify_schema, verify_seed_data,
)
from design.framework.gates import (
    ActorGate, CompoundGate, GatedRelationship, PropertyGate,
)
from design.framework.verify import Rule, verify_gates, verify_rules
from design.legacy.tau2 import (
    Archetype, FaultDeclaration, FaultGroup, FaultSpace,
    PolicyRule, PolicySpec, Tau2Concept, UnfixableFault,
    UserConfirmation, derive_entity_builder, derive_tool_signatures,
    render_tau2_task, verify_fault_space, verify_policy,
)
from design.legacy.tau2.sync import SyncBridge, SyncSpec
from design.legacy.tau2.pipeline import Tau2Pipeline

pipeline = Tau2Pipeline()

# ══════════════════════════════════════════════════════════════════════
# STEP 1: Concept + Topology
# ══════════════════════════════════════════════════════════════════════

concept = WorldConcept(
    name="insurance_claims",
    description=(
        "An insurance company claims processing department. Policyholders file "
        "claims against their insurance policies when incidents occur. Claims go "
        "through intake, documentation, assessment by adjusters, and settlement."
    ),
    entity_names=[
        "Policyholder", "Policy", "Claim", "ClaimItem",
        "Provider", "Assessment", "Payment", "Document",
    ],
)

topology = TopologyTargets(
    min_depth=4,
    min_width=6,
    gating_density="high",
    branching="moderate",
)

tau2_concept = Tau2Concept(
    archetype=Archetype.DIAGNOSTIC,
    agent_role="insurance claims support agent",
    user_role="policyholder",
    agent_purpose=(
        "Help policyholders resolve issues with their insurance claims, from "
        "account and policy problems to claim processing errors, assessment "
        "disputes, and payment failures."
    ),
)

assert pipeline.verify_step_1(concept, topology, tau2_concept).passed


# ══════════════════════════════════════════════════════════════════════
# STEP 2: Schema
# ══════════════════════════════════════════════════════════════════════

schema = WorldSchema(
    concept=concept,
    entities=[
        EntitySpec(
            name="Policyholder",
            description="An insurance customer who holds one or more policies.",
            identity_field="policyholder_id",
            fields=[
                FieldSpec(name="policyholder_id", type=FieldType.STRING,
                          description="Unique policyholder identifier", mutable=False),
                FieldSpec(name="name", type=FieldType.STRING,
                          description="Full name", mutable=False),
                FieldSpec(name="email", type=FieldType.STRING,
                          description="Contact email", mutable=True),
                FieldSpec(name="phone", type=FieldType.STRING,
                          description="Contact phone", mutable=True),
                FieldSpec(name="account_status", type=FieldType.ENUM,
                          description="Account standing — gates access to policies",
                          mutable=True, breakable=True,
                          normal_value="active", broken_values=["suspended", "frozen"],
                          enum_values=["active", "suspended", "frozen"]),
            ],
        ),
        EntitySpec(
            name="Policy",
            description="An insurance policy covering specific risks.",
            identity_field="policy_id",
            fields=[
                FieldSpec(name="policy_id", type=FieldType.STRING,
                          description="Unique policy identifier", mutable=False),
                FieldSpec(name="policyholder_id", type=FieldType.STRING,
                          description="FK to Policyholder", mutable=False),
                FieldSpec(name="policy_type", type=FieldType.ENUM,
                          description="Type of insurance coverage", mutable=False,
                          enum_values=["auto", "home", "health", "life"]),
                FieldSpec(name="status", type=FieldType.ENUM,
                          description="Policy status — gates access to claims",
                          mutable=True, breakable=True,
                          normal_value="active", broken_values=["suspended", "lapsed"],
                          enum_values=["active", "suspended", "lapsed", "cancelled"]),
                FieldSpec(name="premium_amount", type=FieldType.FLOAT,
                          description="Monthly premium charge",
                          mutable=True, breakable=True,
                          normal_value=None, broken_values=[]),
                FieldSpec(name="coverage_limit", type=FieldType.FLOAT,
                          description="Maximum coverage amount", mutable=False),
                FieldSpec(name="deductible", type=FieldType.FLOAT,
                          description="Deductible amount", mutable=False),
            ],
        ),
        EntitySpec(
            name="Claim",
            description="A filed insurance claim against a policy.",
            identity_field="claim_id",
            fields=[
                FieldSpec(name="claim_id", type=FieldType.STRING,
                          description="Unique claim identifier", mutable=False),
                FieldSpec(name="policy_id", type=FieldType.STRING,
                          description="FK to Policy", mutable=False),
                FieldSpec(name="policyholder_id", type=FieldType.STRING,
                          description="FK to Policyholder", mutable=False),
                FieldSpec(name="status", type=FieldType.ENUM,
                          description="Claim processing status — gates downstream access",
                          mutable=True, breakable=True,
                          normal_value="under_review", broken_values=["denied", "closed"],
                          enum_values=["open", "under_review", "approved", "denied", "closed"]),
                FieldSpec(name="claim_amount", type=FieldType.FLOAT,
                          description="Total claimed amount",
                          mutable=True, breakable=True,
                          normal_value=None, broken_values=[]),
                FieldSpec(name="incident_date", type=FieldType.STRING,
                          description="Date of the incident", mutable=False),
                FieldSpec(name="filed_date", type=FieldType.STRING,
                          description="Date claim was filed", mutable=False),
            ],
        ),
        EntitySpec(
            name="ClaimItem",
            description="An individual line item within a claim.",
            identity_field="item_id",
            fields=[
                FieldSpec(name="item_id", type=FieldType.STRING,
                          description="Unique item identifier", mutable=False),
                FieldSpec(name="claim_id", type=FieldType.STRING,
                          description="FK to Claim", mutable=False),
                FieldSpec(name="provider_id", type=FieldType.STRING,
                          description="FK to Provider who serviced this item", mutable=False),
                FieldSpec(name="description", type=FieldType.STRING,
                          description="Description of the item/service", mutable=False),
                FieldSpec(name="amount", type=FieldType.FLOAT,
                          description="Item cost amount",
                          mutable=True, breakable=True,
                          normal_value=None, broken_values=[]),
                FieldSpec(name="status", type=FieldType.ENUM,
                          description="Item approval status",
                          mutable=True, breakable=True,
                          normal_value="approved", broken_values=["denied", "pending"],
                          enum_values=["approved", "denied", "pending"]),
            ],
        ),
        EntitySpec(
            name="Provider",
            description="A service provider (hospital, repair shop, contractor). Lookup entity.",
            identity_field="provider_id",
            fields=[
                FieldSpec(name="provider_id", type=FieldType.STRING,
                          description="Unique provider identifier", mutable=False),
                FieldSpec(name="name", type=FieldType.STRING,
                          description="Provider business name", mutable=False),
                FieldSpec(name="provider_type", type=FieldType.ENUM,
                          description="Type of service provider", mutable=False,
                          enum_values=["hospital", "clinic", "repair_shop", "contractor"]),
                FieldSpec(name="network_status", type=FieldType.ENUM,
                          description="Whether provider is in the insurance network",
                          mutable=True, breakable=True,
                          normal_value="in_network", broken_values=["out_of_network"],
                          enum_values=["in_network", "out_of_network"]),
                FieldSpec(name="license_status", type=FieldType.ENUM,
                          description="Provider licensing status", mutable=False,
                          enum_values=["active", "suspended", "revoked"]),
            ],
        ),
        EntitySpec(
            name="Assessment",
            description="An adjuster's evaluation of a claim.",
            identity_field="assessment_id",
            fields=[
                FieldSpec(name="assessment_id", type=FieldType.STRING,
                          description="Unique assessment identifier", mutable=False),
                FieldSpec(name="claim_id", type=FieldType.STRING,
                          description="FK to Claim", mutable=False),
                FieldSpec(name="adjuster_name", type=FieldType.STRING,
                          description="Name of assigned adjuster", mutable=False),
                FieldSpec(name="status", type=FieldType.ENUM,
                          description="Assessment completion status — gates payment",
                          mutable=True, breakable=True,
                          normal_value="completed", broken_values=["pending", "in_progress"],
                          enum_values=["pending", "in_progress", "completed"]),
                FieldSpec(name="estimated_amount", type=FieldType.FLOAT,
                          description="Adjuster's estimated settlement amount",
                          mutable=True, breakable=True,
                          normal_value=None, broken_values=[]),
                FieldSpec(name="findings", type=FieldType.STRING,
                          description="Adjuster's written findings", mutable=True),
            ],
        ),
        EntitySpec(
            name="Payment",
            description="A settlement payment issued for a claim.",
            identity_field="payment_id",
            fields=[
                FieldSpec(name="payment_id", type=FieldType.STRING,
                          description="Unique payment identifier", mutable=False),
                FieldSpec(name="assessment_id", type=FieldType.STRING,
                          description="FK to Assessment", mutable=False),
                FieldSpec(name="claim_id", type=FieldType.STRING,
                          description="FK to Claim (denormalized)", mutable=False),
                FieldSpec(name="amount", type=FieldType.FLOAT,
                          description="Payment amount",
                          mutable=True, breakable=True,
                          normal_value=None, broken_values=[]),
                FieldSpec(name="status", type=FieldType.ENUM,
                          description="Payment processing status",
                          mutable=True, breakable=True,
                          normal_value="completed", broken_values=["failed", "pending"],
                          enum_values=["pending", "processing", "completed", "failed"]),
                FieldSpec(name="payment_method", type=FieldType.ENUM,
                          description="How payment is issued", mutable=True,
                          enum_values=["check", "direct_deposit", "wire"]),
            ],
        ),
        EntitySpec(
            name="Document",
            description="Supporting documentation for a claim.",
            identity_field="document_id",
            fields=[
                FieldSpec(name="document_id", type=FieldType.STRING,
                          description="Unique document identifier", mutable=False),
                FieldSpec(name="claim_id", type=FieldType.STRING,
                          description="FK to Claim", mutable=False),
                FieldSpec(name="document_type", type=FieldType.ENUM,
                          description="Type of supporting document", mutable=False,
                          enum_values=["police_report", "medical_record", "receipt", "photo", "estimate"]),
                FieldSpec(name="status", type=FieldType.ENUM,
                          description="Document receipt status",
                          mutable=True, breakable=True,
                          normal_value="received", broken_values=["missing", "rejected"],
                          enum_values=["received", "missing", "rejected", "pending"]),
            ],
        ),
    ],
    relationships=[
        RelationshipSpec("Policyholder", "Policy", Cardinality.ONE_TO_MANY,
                         "policyholder_id", "Policyholder's insurance policies"),
        RelationshipSpec("Policy", "Claim", Cardinality.ONE_TO_MANY,
                         "policy_id", "Claims filed against this policy"),
        RelationshipSpec("Claim", "ClaimItem", Cardinality.ONE_TO_MANY,
                         "claim_id", "Line items within the claim"),
        RelationshipSpec("Claim", "Document", Cardinality.ONE_TO_MANY,
                         "claim_id", "Supporting documents for the claim"),
        RelationshipSpec("Claim", "Assessment", Cardinality.ONE_TO_ONE,
                         "claim_id", "Adjuster's assessment of the claim"),
        RelationshipSpec("Assessment", "Payment", Cardinality.ONE_TO_ONE,
                         "assessment_id", "Settlement payment after assessment"),
    ],
)

assert pipeline.verify_step_2(schema).passed


# ══════════════════════════════════════════════════════════════════════
# STEP 3: Relationships + Gates (depth 4)
# ══════════════════════════════════════════════════════════════════════

gated_relationships = [
    # Depth 1: account_status + identity verified
    GatedRelationship(
        relationship=RelationshipSpec(
            "Policyholder", "Policy", Cardinality.ONE_TO_MANY,
            "policyholder_id", "Policyholder's policies"),
        gate=CompoundGate(conditions=[
            PropertyGate(entity="Policyholder", field="account_status",
                         required_value="active"),
            ActorGate(actor="user", field="identity_verified",
                      required_value=True, trigger_tool="verify_identity"),
        ]),
        description="Account must be active AND identity verified to access policies",
    ),
    # Depth 2: policy active
    GatedRelationship(
        relationship=RelationshipSpec(
            "Policy", "Claim", Cardinality.ONE_TO_MANY,
            "policy_id", "Claims against this policy"),
        gate=PropertyGate(entity="Policy", field="status",
                          required_value="active"),
        description="Policy must be active to access claims",
    ),
    # Depth 3: claim under review (3 branches)
    GatedRelationship(
        relationship=RelationshipSpec(
            "Claim", "ClaimItem", Cardinality.ONE_TO_MANY,
            "claim_id", "Items in claim"),
        gate=PropertyGate(entity="Claim", field="status",
                          required_value="under_review"),
        description="Claim must be under review to access items",
    ),
    GatedRelationship(
        relationship=RelationshipSpec(
            "Claim", "Document", Cardinality.ONE_TO_MANY,
            "claim_id", "Docs for claim"),
        gate=PropertyGate(entity="Claim", field="status",
                          required_value="under_review"),
        description="Claim must be under review to access documents",
    ),
    GatedRelationship(
        relationship=RelationshipSpec(
            "Claim", "Assessment", Cardinality.ONE_TO_ONE,
            "claim_id", "Assessment of claim"),
        gate=PropertyGate(entity="Claim", field="status",
                          required_value="under_review"),
        description="Claim must be under review to access assessment",
    ),
    # Depth 4: assessment completed
    GatedRelationship(
        relationship=RelationshipSpec(
            "Assessment", "Payment", Cardinality.ONE_TO_ONE,
            "assessment_id", "Payment after assessment"),
        gate=PropertyGate(entity="Assessment", field="status",
                          required_value="completed"),
        description="Assessment must be completed to access payment",
    ),
]

assert pipeline.verify_step_3(gated_relationships).passed


# ══════════════════════════════════════════════════════════════════════
# STEP 4: Business Rules
# ══════════════════════════════════════════════════════════════════════

rules = [
    Rule(description="Cannot modify claim amount once claim status is approved",
         entity="Claim", field="claim_amount",
         condition_entity="Claim", condition_field="status", condition_value="approved"),
    Rule(description="Cannot process payment if assessment status is pending",
         entity="Payment",
         condition_entity="Assessment", condition_field="status", condition_value="pending"),
    Rule(description="Claim amount cannot exceed the policy coverage limit",
         entity="Claim", field="claim_amount"),
    Rule(description="Payment amount must not exceed the assessment estimated amount",
         entity="Payment", field="amount"),
    Rule(description="Must verify policyholder identity before accessing details",
         entity="Policyholder"),
    Rule(description="Cannot reopen a claim that has been closed for more than 30 days",
         entity="Claim", field="status"),
    Rule(description="Provider must have active license status for valid claim items",
         entity="ClaimItem",
         condition_entity="Provider", condition_field="license_status", condition_value="active"),
]

assert pipeline.verify_step_4(rules).passed


# ══════════════════════════════════════════════════════════════════════
# STEP 5: Seed Data
# ══════════════════════════════════════════════════════════════════════

seed_data = SeedData(records={
    "Policyholder": [
        {"policyholder_id": "PH001", "name": "Maria Santos", "email": "maria.santos@email.com", "phone": "555-0201", "account_status": "active"},
        {"policyholder_id": "PH002", "name": "Robert Chen", "email": "r.chen@email.com", "phone": "555-0202", "account_status": "active"},
        {"policyholder_id": "PH003", "name": "Aisha Johnson", "email": "aisha.j@email.com", "phone": "555-0203", "account_status": "active"},
        {"policyholder_id": "PH004", "name": "David Kowalski", "email": "d.kowalski@email.com", "phone": "555-0204", "account_status": "active"},
        {"policyholder_id": "PH005", "name": "Fatima Al-Rashid", "email": "f.alrashid@email.com", "phone": "555-0205", "account_status": "active"},
        {"policyholder_id": "PH006", "name": "James O'Brien", "email": "jobrien@email.com", "phone": "555-0206", "account_status": "active"},
        {"policyholder_id": "PH007", "name": "Yuki Tanaka", "email": "y.tanaka@email.com", "phone": "555-0207", "account_status": "active"},
        {"policyholder_id": "PH008", "name": "Elena Volkov", "email": "e.volkov@email.com", "phone": "555-0208", "account_status": "active"},
        {"policyholder_id": "PH009", "name": "Marcus Williams", "email": "m.williams@email.com", "phone": "555-0209", "account_status": "active"},
        {"policyholder_id": "PH010", "name": "Priya Sharma", "email": "p.sharma@email.com", "phone": "555-0210", "account_status": "active"},
    ],
    "Policy": [
        {"policy_id": "POL001", "policyholder_id": "PH001", "policy_type": "auto", "status": "active", "premium_amount": 145.00, "coverage_limit": 50000.0, "deductible": 500.0},
        {"policy_id": "POL002", "policyholder_id": "PH002", "policy_type": "home", "status": "active", "premium_amount": 210.00, "coverage_limit": 300000.0, "deductible": 1000.0},
        {"policy_id": "POL003", "policyholder_id": "PH003", "policy_type": "health", "status": "active", "premium_amount": 380.00, "coverage_limit": 500000.0, "deductible": 2000.0},
        {"policy_id": "POL004", "policyholder_id": "PH004", "policy_type": "auto", "status": "active", "premium_amount": 165.00, "coverage_limit": 75000.0, "deductible": 750.0},
        {"policy_id": "POL005", "policyholder_id": "PH005", "policy_type": "life", "status": "active", "premium_amount": 95.00, "coverage_limit": 250000.0, "deductible": 0.0},
        {"policy_id": "POL006", "policyholder_id": "PH006", "policy_type": "home", "status": "active", "premium_amount": 275.00, "coverage_limit": 450000.0, "deductible": 1500.0},
        {"policy_id": "POL007", "policyholder_id": "PH007", "policy_type": "health", "status": "active", "premium_amount": 420.00, "coverage_limit": 750000.0, "deductible": 1000.0},
        {"policy_id": "POL008", "policyholder_id": "PH008", "policy_type": "auto", "status": "active", "premium_amount": 130.00, "coverage_limit": 50000.0, "deductible": 500.0},
        {"policy_id": "POL009", "policyholder_id": "PH009", "policy_type": "life", "status": "active", "premium_amount": 110.00, "coverage_limit": 500000.0, "deductible": 0.0},
        {"policy_id": "POL010", "policyholder_id": "PH010", "policy_type": "home", "status": "active", "premium_amount": 195.00, "coverage_limit": 350000.0, "deductible": 1000.0},
    ],
    "Claim": [
        {"claim_id": "CLM001", "policy_id": "POL001", "policyholder_id": "PH001", "status": "under_review", "claim_amount": 8500.00, "incident_date": "2025-11-15", "filed_date": "2025-11-18"},
        {"claim_id": "CLM002", "policy_id": "POL002", "policyholder_id": "PH002", "status": "under_review", "claim_amount": 45000.00, "incident_date": "2025-10-02", "filed_date": "2025-10-05"},
        {"claim_id": "CLM003", "policy_id": "POL003", "policyholder_id": "PH003", "status": "under_review", "claim_amount": 12300.00, "incident_date": "2025-12-01", "filed_date": "2025-12-03"},
        {"claim_id": "CLM004", "policy_id": "POL004", "policyholder_id": "PH004", "status": "under_review", "claim_amount": 3200.00, "incident_date": "2025-09-20", "filed_date": "2025-09-22"},
        {"claim_id": "CLM005", "policy_id": "POL005", "policyholder_id": "PH005", "status": "under_review", "claim_amount": 250000.00, "incident_date": "2025-08-10", "filed_date": "2025-08-12"},
        {"claim_id": "CLM006", "policy_id": "POL006", "policyholder_id": "PH006", "status": "under_review", "claim_amount": 28000.00, "incident_date": "2025-11-30", "filed_date": "2025-12-02"},
        {"claim_id": "CLM007", "policy_id": "POL007", "policyholder_id": "PH007", "status": "under_review", "claim_amount": 5600.00, "incident_date": "2025-12-10", "filed_date": "2025-12-12"},
        {"claim_id": "CLM008", "policy_id": "POL008", "policyholder_id": "PH008", "status": "under_review", "claim_amount": 15800.00, "incident_date": "2025-10-25", "filed_date": "2025-10-28"},
        {"claim_id": "CLM009", "policy_id": "POL009", "policyholder_id": "PH009", "status": "under_review", "claim_amount": 500000.00, "incident_date": "2025-07-15", "filed_date": "2025-07-17"},
        {"claim_id": "CLM010", "policy_id": "POL010", "policyholder_id": "PH010", "status": "under_review", "claim_amount": 18500.00, "incident_date": "2025-11-05", "filed_date": "2025-11-07"},
    ],
    "ClaimItem": [
        {"item_id": "CI001", "claim_id": "CLM001", "provider_id": "PRV001", "description": "Body repair - front bumper", "amount": 3500.00, "status": "approved"},
        {"item_id": "CI002", "claim_id": "CLM001", "provider_id": "PRV002", "description": "Windshield replacement", "amount": 1200.00, "status": "approved"},
        {"item_id": "CI003", "claim_id": "CLM002", "provider_id": "PRV003", "description": "Water damage restoration", "amount": 22000.00, "status": "approved"},
        {"item_id": "CI004", "claim_id": "CLM003", "provider_id": "PRV004", "description": "Emergency room visit", "amount": 4800.00, "status": "approved"},
        {"item_id": "CI005", "claim_id": "CLM003", "provider_id": "PRV005", "description": "Physical therapy sessions", "amount": 3200.00, "status": "approved"},
        {"item_id": "CI006", "claim_id": "CLM004", "provider_id": "PRV001", "description": "Paint and detailing", "amount": 1800.00, "status": "approved"},
        {"item_id": "CI007", "claim_id": "CLM006", "provider_id": "PRV006", "description": "Roof repair", "amount": 15000.00, "status": "approved"},
        {"item_id": "CI008", "claim_id": "CLM007", "provider_id": "PRV004", "description": "Specialist consultation", "amount": 2800.00, "status": "approved"},
        {"item_id": "CI009", "claim_id": "CLM008", "provider_id": "PRV002", "description": "Frame realignment", "amount": 6500.00, "status": "approved"},
        {"item_id": "CI010", "claim_id": "CLM010", "provider_id": "PRV003", "description": "Mold remediation", "amount": 9500.00, "status": "approved"},
    ],
    "Provider": [
        {"provider_id": "PRV001", "name": "AutoCare Collision Center", "provider_type": "repair_shop", "network_status": "in_network", "license_status": "active"},
        {"provider_id": "PRV002", "name": "SafeGlass Auto Services", "provider_type": "repair_shop", "network_status": "in_network", "license_status": "active"},
        {"provider_id": "PRV003", "name": "RestorePro Water & Fire", "provider_type": "contractor", "network_status": "in_network", "license_status": "active"},
        {"provider_id": "PRV004", "name": "Mercy General Hospital", "provider_type": "hospital", "network_status": "in_network", "license_status": "active"},
        {"provider_id": "PRV005", "name": "Peak Performance Physical Therapy", "provider_type": "clinic", "network_status": "in_network", "license_status": "active"},
        {"provider_id": "PRV006", "name": "Summit Roofing & Construction", "provider_type": "contractor", "network_status": "in_network", "license_status": "active"},
        {"provider_id": "PRV007", "name": "Downtown Medical Clinic", "provider_type": "clinic", "network_status": "in_network", "license_status": "suspended"},
        {"provider_id": "PRV008", "name": "Elite Auto Body", "provider_type": "repair_shop", "network_status": "in_network", "license_status": "revoked"},
    ],
    "Assessment": [
        {"assessment_id": "ASM001", "claim_id": "CLM001", "adjuster_name": "Thomas Reed", "status": "completed", "estimated_amount": 8200.00, "findings": "Damage consistent with reported collision."},
        {"assessment_id": "ASM002", "claim_id": "CLM002", "adjuster_name": "Sandra Liu", "status": "completed", "estimated_amount": 42000.00, "findings": "Extensive water damage to first floor."},
        {"assessment_id": "ASM003", "claim_id": "CLM003", "adjuster_name": "Michael Torres", "status": "completed", "estimated_amount": 11500.00, "findings": "Medical expenses verified."},
        {"assessment_id": "ASM004", "claim_id": "CLM004", "adjuster_name": "Thomas Reed", "status": "completed", "estimated_amount": 3000.00, "findings": "Minor cosmetic damage confirmed."},
        {"assessment_id": "ASM005", "claim_id": "CLM005", "adjuster_name": "Karen Phelps", "status": "completed", "estimated_amount": 250000.00, "findings": "Life insurance claim verified."},
        {"assessment_id": "ASM006", "claim_id": "CLM006", "adjuster_name": "Sandra Liu", "status": "completed", "estimated_amount": 26000.00, "findings": "Storm damage to roof confirmed."},
        {"assessment_id": "ASM007", "claim_id": "CLM007", "adjuster_name": "Michael Torres", "status": "completed", "estimated_amount": 5200.00, "findings": "Specialist visit medically necessary."},
        {"assessment_id": "ASM008", "claim_id": "CLM008", "adjuster_name": "Thomas Reed", "status": "completed", "estimated_amount": 14500.00, "findings": "Structural frame damage confirmed."},
        {"assessment_id": "ASM009", "claim_id": "CLM009", "adjuster_name": "Karen Phelps", "status": "completed", "estimated_amount": 500000.00, "findings": "Full policy payout approved."},
        {"assessment_id": "ASM010", "claim_id": "CLM010", "adjuster_name": "Sandra Liu", "status": "completed", "estimated_amount": 17000.00, "findings": "Mold remediation required."},
    ],
    "Payment": [
        {"payment_id": "PAY001", "assessment_id": "ASM001", "claim_id": "CLM001", "amount": 7700.00, "status": "completed", "payment_method": "direct_deposit"},
        {"payment_id": "PAY002", "assessment_id": "ASM002", "claim_id": "CLM002", "amount": 41000.00, "status": "completed", "payment_method": "check"},
        {"payment_id": "PAY003", "assessment_id": "ASM003", "claim_id": "CLM003", "amount": 9500.00, "status": "completed", "payment_method": "direct_deposit"},
        {"payment_id": "PAY004", "assessment_id": "ASM004", "claim_id": "CLM004", "amount": 2250.00, "status": "completed", "payment_method": "direct_deposit"},
        {"payment_id": "PAY005", "assessment_id": "ASM005", "claim_id": "CLM005", "amount": 250000.00, "status": "completed", "payment_method": "wire"},
        {"payment_id": "PAY006", "assessment_id": "ASM006", "claim_id": "CLM006", "amount": 24500.00, "status": "completed", "payment_method": "check"},
        {"payment_id": "PAY007", "assessment_id": "ASM007", "claim_id": "CLM007", "amount": 4200.00, "status": "completed", "payment_method": "direct_deposit"},
        {"payment_id": "PAY008", "assessment_id": "ASM008", "claim_id": "CLM008", "amount": 14000.00, "status": "completed", "payment_method": "check"},
        {"payment_id": "PAY009", "assessment_id": "ASM009", "claim_id": "CLM009", "amount": 500000.00, "status": "completed", "payment_method": "wire"},
        {"payment_id": "PAY010", "assessment_id": "ASM010", "claim_id": "CLM010", "amount": 16000.00, "status": "completed", "payment_method": "direct_deposit"},
    ],
    "Document": [
        {"document_id": "DOC001", "claim_id": "CLM001", "document_type": "police_report", "status": "received"},
        {"document_id": "DOC002", "claim_id": "CLM001", "document_type": "photo", "status": "received"},
        {"document_id": "DOC003", "claim_id": "CLM002", "document_type": "photo", "status": "received"},
        {"document_id": "DOC004", "claim_id": "CLM002", "document_type": "estimate", "status": "received"},
        {"document_id": "DOC005", "claim_id": "CLM003", "document_type": "medical_record", "status": "received"},
        {"document_id": "DOC006", "claim_id": "CLM003", "document_type": "receipt", "status": "received"},
        {"document_id": "DOC007", "claim_id": "CLM004", "document_type": "estimate", "status": "received"},
        {"document_id": "DOC008", "claim_id": "CLM006", "document_type": "photo", "status": "received"},
        {"document_id": "DOC009", "claim_id": "CLM007", "document_type": "medical_record", "status": "received"},
        {"document_id": "DOC010", "claim_id": "CLM008", "document_type": "police_report", "status": "received"},
    ],
})

assert pipeline.verify_step_5(seed_data).passed


# ══════════════════════════════════════════════════════════════════════
# STEP 6: Tools (auto-derived)
# ══════════════════════════════════════════════════════════════════════

tools = pipeline.step_6_tools()


# ══════════════════════════════════════════════════════════════════════
# STEP 7: Sync
# ══════════════════════════════════════════════════════════════════════

sync_spec = SyncSpec(bridges=[
    SyncBridge(direction="user_to_agent", user_trigger_field="identity_verified",
               agent_entity="Policyholder", agent_field="identity_verified", agent_value=True),
    SyncBridge(direction="agent_to_user", source_entity="Policyholder",
               source_field="account_status", target_field="visible_account_status"),
    SyncBridge(direction="agent_to_user", source_entity="Policy",
               source_field="status", target_field="visible_policy_status"),
    SyncBridge(direction="agent_to_user", source_entity="Claim",
               source_field="status", target_field="visible_claim_status"),
    SyncBridge(direction="agent_to_user", source_entity="Payment",
               source_field="status", target_field="visible_payment_status"),
])

assert pipeline.verify_step_7(sync_spec).passed


# ══════════════════════════════════════════════════════════════════════
# STEP 8: Fault Space (10 groups, composition-safe)
# ══════════════════════════════════════════════════════════════════════

fault_space = FaultSpace(
    groups=[
        # ── GROUP 1: Account issues (depth 1 gate) ──
        FaultGroup(
            name="account_issues", category="account",
            perturbations=[
                FaultDeclaration(
                    name="suspended_account",
                    description="my account appears to be suspended",
                    fixed_description="your account has been reactivated",
                    entity="Policyholder", field="account_status",
                    broken_value="suspended",
                    fix_tool="update_policyholder_account_status",
                    fix_args={"policyholder_id": "{policyholder_id}", "account_status": "active"},
                ),
                FaultDeclaration(
                    name="frozen_account",
                    description="my account has been frozen",
                    fixed_description="your account has been unfrozen",
                    entity="Policyholder", field="account_status",
                    broken_value="frozen",
                    fix_tool="update_policyholder_account_status",
                    fix_args={"policyholder_id": "{policyholder_id}", "account_status": "active"},
                ),
            ],
            user_confirmation=UserConfirmation(tool_name="acknowledge_resolution"),
        ),
        # ── GROUP 2: Policy status issues (depth 2 gate) ──
        FaultGroup(
            name="policy_status_issues", category="policy",
            perturbations=[
                FaultDeclaration(
                    name="suspended_policy",
                    description="my insurance policy has been suspended",
                    fixed_description="your policy has been reinstated",
                    entity="Policy", field="status",
                    broken_value="suspended",
                    fix_tool="update_policy_status",
                    fix_args={"policy_id": "{policy_id}", "status": "active"},
                ),
                FaultDeclaration(
                    name="lapsed_policy",
                    description="my insurance policy shows as lapsed",
                    fixed_description="your policy has been reinstated",
                    entity="Policy", field="status",
                    broken_value="lapsed",
                    fix_tool="update_policy_status",
                    fix_args={"policy_id": "{policy_id}", "status": "active"},
                ),
            ],
        ),
        # ── GROUP 3: Policy premium issues ──
        FaultGroup(
            name="premium_issues", category="billing",
            perturbations=[
                FaultDeclaration(
                    name="wrong_premium",
                    description="my premium amount is incorrect",
                    fixed_description="your premium has been corrected",
                    entity="Policy", field="premium_amount",
                    broken_value=999.99,
                    fix_tool="update_policy_premium_amount",
                    fix_args={"policy_id": "{policy_id}", "premium_amount": "{correct_premium_amount}"},
                    check_value="{correct_premium_amount}",
                ),
            ],
        ),
        # ── GROUP 4: Claim status issues (depth 3 gate) ──
        FaultGroup(
            name="claim_status_issues", category="claims",
            perturbations=[
                FaultDeclaration(
                    name="denied_claim",
                    description="my claim was denied incorrectly",
                    fixed_description="your claim has been reopened for review",
                    entity="Claim", field="status",
                    broken_value="denied",
                    fix_tool="update_claim_status",
                    fix_args={"claim_id": "{claim_id}", "status": "under_review"},
                ),
                FaultDeclaration(
                    name="closed_claim",
                    description="my claim was closed prematurely",
                    fixed_description="your claim has been reopened",
                    entity="Claim", field="status",
                    broken_value="closed",
                    fix_tool="update_claim_status",
                    fix_args={"claim_id": "{claim_id}", "status": "under_review"},
                ),
            ],
        ),
        # ── GROUP 5: Claim amount issues ──
        FaultGroup(
            name="claim_amount_issues", category="claims",
            perturbations=[
                FaultDeclaration(
                    name="wrong_claim_amount",
                    description="the total amount on my claim is wrong",
                    fixed_description="your claim amount has been corrected",
                    entity="Claim", field="claim_amount",
                    broken_value=0.0,
                    fix_tool="update_claim_claim_amount",
                    fix_args={"claim_id": "{claim_id}", "claim_amount": "{correct_claim_amount}"},
                    check_value="{correct_claim_amount}",
                ),
            ],
        ),
        # ── GROUP 6: Claim item status issues ──
        FaultGroup(
            name="claim_item_issues", category="items",
            perturbations=[
                FaultDeclaration(
                    name="denied_item",
                    description="one of my claim items was wrongly denied",
                    fixed_description="your claim item has been approved",
                    entity="ClaimItem", field="status",
                    broken_value="denied",
                    fix_tool="update_claim_item_status",
                    fix_args={"item_id": "{item_id}", "status": "approved"},
                ),
                FaultDeclaration(
                    name="pending_item",
                    description="one of my claim items is stuck in pending",
                    fixed_description="your claim item has been approved",
                    entity="ClaimItem", field="status",
                    broken_value="pending",
                    fix_tool="update_claim_item_status",
                    fix_args={"item_id": "{item_id}", "status": "approved"},
                ),
            ],
        ),
        # ── GROUP 7: Assessment status issues (depth 4 gate) ──
        FaultGroup(
            name="assessment_issues", category="assessment",
            perturbations=[
                FaultDeclaration(
                    name="pending_assessment",
                    description="my claim assessment is stuck in pending",
                    fixed_description="your assessment has been completed",
                    entity="Assessment", field="status",
                    broken_value="pending",
                    fix_tool="update_assessment_status",
                    fix_args={"assessment_id": "{assessment_id}", "status": "completed"},
                ),
                FaultDeclaration(
                    name="incomplete_assessment",
                    description="my claim assessment is marked in-progress but nothing is happening",
                    fixed_description="your assessment has been completed",
                    entity="Assessment", field="status",
                    broken_value="in_progress",
                    fix_tool="update_assessment_status",
                    fix_args={"assessment_id": "{assessment_id}", "status": "completed"},
                ),
            ],
        ),
        # ── GROUP 8: Payment status issues ──
        FaultGroup(
            name="payment_status_issues", category="payment",
            perturbations=[
                FaultDeclaration(
                    name="failed_payment",
                    description="my settlement payment failed",
                    fixed_description="your payment has been processed successfully",
                    entity="Payment", field="status",
                    broken_value="failed",
                    fix_tool="update_payment_status",
                    fix_args={"payment_id": "{payment_id}", "status": "completed"},
                ),
                FaultDeclaration(
                    name="stuck_payment",
                    description="my settlement payment is stuck in pending",
                    fixed_description="your payment has been processed",
                    entity="Payment", field="status",
                    broken_value="pending",
                    fix_tool="update_payment_status",
                    fix_args={"payment_id": "{payment_id}", "status": "completed"},
                ),
            ],
        ),
        # ── GROUP 9: Document issues ──
        FaultGroup(
            name="document_issues", category="documentation",
            perturbations=[
                FaultDeclaration(
                    name="missing_document",
                    description="a required document is missing from my claim",
                    fixed_description="your document has been marked as received",
                    entity="Document", field="status",
                    broken_value="missing",
                    fix_tool="update_document_status",
                    fix_args={"document_id": "{document_id}", "status": "received"},
                ),
                FaultDeclaration(
                    name="rejected_document",
                    description="my submitted document was rejected",
                    fixed_description="your document has been accepted",
                    entity="Document", field="status",
                    broken_value="rejected",
                    fix_tool="update_document_status",
                    fix_args={"document_id": "{document_id}", "status": "received"},
                ),
            ],
        ),
        # ── GROUP 10: Provider network (unfixable — must escalate) ──
        FaultGroup(
            name="provider_network_issues", category="provider",
            perturbations=[],
            unfixable_fault=UnfixableFault(
                name="out_of_network_provider",
                description="the provider used for my claim is out of network",
                entity="Provider", field="network_status",
                broken_value="out_of_network",
                preservation_check=True,
            ),
        ),
    ],
    field_ownership={
        "Policyholder.account_status": "account_issues",
        "Policy.status": "policy_status_issues",
        "Policy.premium_amount": "premium_issues",
        "Claim.status": "claim_status_issues",
        "Claim.claim_amount": "claim_amount_issues",
        "ClaimItem.status": "claim_item_issues",
        "Assessment.status": "assessment_issues",
        "Payment.status": "payment_status_issues",
        "Document.status": "document_issues",
        "Provider.network_status": "provider_network_issues",
    },
    tool_ownership={
        "update_policyholder_account_status": "account_issues",
        "update_policy_status": "policy_status_issues",
        "update_policy_premium_amount": "premium_issues",
        "update_claim_status": "claim_status_issues",
        "update_claim_claim_amount": "claim_amount_issues",
        "update_claim_item_status": "claim_item_issues",
        "update_assessment_status": "assessment_issues",
        "update_payment_status": "payment_status_issues",
        "update_document_status": "document_issues",
    },
    resolution_instruction=(
        "all your account, policy, claim, assessment, payment, and documentation "
        "issues have been resolved"
    ),
    min_perturbations=1,
    max_perturbations=5,
    max_total_tasks=400,
)

r8 = pipeline.verify_step_8(fault_space)
assert r8.passed, f"Step 8 failed: {[(i.check_name, i.message) for i in r8.issues if i.severity.name == 'ERROR']}"


# ══════════════════════════════════════════════════════════════════════
# STEP 9: Policy
# ══════════════════════════════════════════════════════════════════════

policy = PolicySpec(
    structured_rules=[
        PolicyRule(condition="policyholder account is suspended or frozen",
                   action="reactivate account", tools_referenced=["update_policyholder_account_status"], priority=1),
        PolicyRule(condition="policy status is suspended or lapsed",
                   action="reinstate policy", tools_referenced=["update_policy_status"], priority=1),
        PolicyRule(condition="policy premium amount is incorrect",
                   action="correct premium amount", tools_referenced=["update_policy_premium_amount"]),
        PolicyRule(condition="claim status is denied or closed incorrectly",
                   action="reopen claim for review", tools_referenced=["update_claim_status"], priority=1),
        PolicyRule(condition="claim amount is wrong",
                   action="correct claim amount", tools_referenced=["update_claim_claim_amount"]),
        PolicyRule(condition="claim item status is denied or pending incorrectly",
                   action="approve claim item", tools_referenced=["update_claim_item_status"]),
        PolicyRule(condition="assessment status is pending or in-progress",
                   action="complete assessment", tools_referenced=["update_assessment_status"]),
        PolicyRule(condition="payment status is failed or stuck pending",
                   action="process payment", tools_referenced=["update_payment_status"]),
        PolicyRule(condition="required document is missing or rejected",
                   action="mark document as received", tools_referenced=["update_document_status"]),
        PolicyRule(condition="provider is out of network",
                   action="inform policyholder and escalate — cannot change provider network status",
                   tools_referenced=[]),
    ],
    prose="""# Insurance Claims Support Policy

## Your Role
You are an insurance claims support agent. Help policyholders resolve issues
with their accounts, policies, claims, assessments, and payments.

## Authentication
Before accessing any policy or claim details, ask the policyholder to verify
their identity. Do not proceed until identity is confirmed.

## Diagnostic Approach
1. Start by retrieving the policyholder's profile with get_policyholder
2. If the account is suspended or frozen, reactivate it before proceeding
3. Once account is active, retrieve the policy with get_policy
4. If the policy is suspended or lapsed, reinstate it
5. Once policy is active, retrieve the claim with get_claim
6. If the claim is denied or closed, reopen it for review
7. Once claim is under review, check claim items, documents, and assessment
8. If assessment is incomplete, complete it
9. Once assessment is complete, check the payment status

## Resolution Procedures

### Account Issues
When the policyholder's account_status is suspended or frozen:
- Use update_policyholder_account_status to set it back to active
- Confirm with the policyholder that their account is accessible

### Policy Issues
When a policy shows as suspended or lapsed:
- Use update_policy_status to reinstate it to active
When the premium amount is incorrect:
- Use update_policy_premium_amount to correct it

### Claim Issues
When a claim has been denied or closed incorrectly:
- Use update_claim_status to reopen it as under_review
When the claim amount is wrong:
- Use update_claim_claim_amount to correct it

### Claim Item Issues
When a claim item has been wrongly denied or is stuck pending:
- Use update_claim_item_status to approve it

### Assessment Issues
When an assessment is stuck in pending or in_progress:
- Use update_assessment_status to mark it as completed

### Payment Issues
When a payment has failed or is stuck pending:
- Use update_payment_status to process it as completed

### Document Issues
When a required document is missing or rejected:
- Use update_document_status to mark it as received

### Provider Network Issues
When a provider is out of network:
- This cannot be fixed. Inform the policyholder and transfer to a specialist.

## Tools Available
- get_policyholder(policyholder_id) — retrieve policyholder profile
- get_policy(policy_id) — retrieve policy details
- get_claim(claim_id) — retrieve claim details
- get_claim_item(item_id) — retrieve claim item details
- get_provider(provider_id) — retrieve provider details
- get_assessment(assessment_id) — retrieve assessment details
- get_payment(payment_id) — retrieve payment details
- get_document(document_id) — retrieve document details
- update_policyholder_account_status — fix account status
- update_policy_status — fix policy status
- update_policy_premium_amount — fix premium
- update_claim_status — fix claim status
- update_claim_claim_amount — fix claim amount
- update_claim_item_status — fix item approval
- update_assessment_status — fix assessment status
- update_payment_status — fix payment status
- update_document_status — fix document status
""",
)

r9 = pipeline.verify_step_9(policy)
assert r9.passed, f"Step 9 failed: {[(i.check_name, i.message) for i in r9.issues if i.severity.name == 'ERROR']}"


# ══════════════════════════════════════════════════════════════════════
# STEP 10: Task Generation (pure code)
# ══════════════════════════════════════════════════════════════════════

result = pipeline.step_10_tasks(seed=42)
blueprints = result["blueprints"]
tau2_tasks = result["tau2_tasks"]

print(f"Generated {len(blueprints)} task blueprints")
print(f"Rendered {len(tau2_tasks)} tau2 tasks")

# Show difficulty distribution
from collections import Counter
difficulties = Counter(bp.difficulty for bp in blueprints)
for diff, count in sorted(difficulties.items()):
    print(f"  Difficulty {diff}: {count} tasks")
