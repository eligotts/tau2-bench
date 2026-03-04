import random
from pathlib import Path
from typing import Optional

from tau2.data_model.tasks import Task
from tau2.domains.vet_clinic.data_model import VetClinicDB
from tau2.domains.vet_clinic.tools import VetClinicTools
from tau2.domains.vet_clinic.user_data_model import (
    AppointmentSummary,
    InvoiceSummary,
    PetSummary,
    TreatmentSummary,
    VetClinicUserDB,
)
from tau2.domains.vet_clinic.user_tools import VetClinicUserTools
from tau2.domains.vet_clinic.utils import (
    VET_CLINIC_DB_PATH,
    VET_CLINIC_POLICY_PATH,
    VET_CLINIC_TASK_SET_PATH,
    VET_CLINIC_USER_DB_PATH,
)
from tau2.environment.environment import Environment
from tau2.utils import load_file


class VetClinicEnvironment(Environment):
    tools: VetClinicTools
    user_tools: VetClinicUserTools

    def __init__(
        self,
        domain_name: str,
        policy: str,
        tools: VetClinicTools,
        user_tools: VetClinicUserTools,
    ):
        super().__init__(domain_name, policy, tools, user_tools)

    def sync_tools(self):
        """
        Synchronize agent-side DB state into user-visible summaries.

        Projects:
        1. Pet summaries from agent pets DB
        2. Appointment summaries from agent appointments DB
        3. Treatment summaries from agent treatments DB
        4. Invoice summaries from agent invoices DB
        """
        if self.user_tools.db.owner_id is None:
            return

        owner_id = self.user_tools.db.owner_id
        pet_map = {p.pet_id: p for p in self.tools.db.pets}

        # Find this owner's pets
        owner_pets = [p for p in self.tools.db.pets if p.owner_id == owner_id]
        owner_pet_ids = {p.pet_id for p in owner_pets}

        # 1. Sync pet summaries
        self.user_tools.db.my_pets = [
            PetSummary(
                pet_id=p.pet_id,
                pet_name=p.pet_name,
                species=p.species,
                vaccination_status=p.vaccination_status,
            )
            for p in owner_pets
        ]

        # 2. Sync appointment summaries
        owner_appts = [
            a for a in self.tools.db.appointments
            if a.pet_id in owner_pet_ids
        ]
        self.user_tools.db.my_appointments = [
            AppointmentSummary(
                appointment_id=a.appointment_id,
                pet_name=pet_map[a.pet_id].pet_name if a.pet_id in pet_map else "Unknown",
                appt_date=a.appt_date,
                appointment_type=a.appointment_type,
                checked_in=a.checked_in,
            )
            for a in owner_appts
        ]

        # 3. Sync treatment summaries
        owner_appt_ids = {a.appointment_id for a in owner_appts}
        owner_treatments = [
            t for t in self.tools.db.treatments
            if t.appointment_id in owner_appt_ids
        ]
        # Build appt→pet mapping for pet names in treatment summaries
        appt_pet_map = {a.appointment_id: a.pet_id for a in owner_appts}
        self.user_tools.db.my_treatments = [
            TreatmentSummary(
                treatment_id=t.treatment_id,
                pet_name=(
                    pet_map[appt_pet_map[t.appointment_id]].pet_name
                    if t.appointment_id in appt_pet_map
                    and appt_pet_map[t.appointment_id] in pet_map
                    else "Unknown"
                ),
                medication=t.medication,
                dosage=t.dosage,
                status=t.status,
            )
            for t in owner_treatments
        ]

        # 4. Sync invoice summaries
        owner_treatment_ids = {t.treatment_id for t in owner_treatments}
        self.user_tools.db.my_invoices = [
            InvoiceSummary(
                invoice_id=inv.invoice_id,
                amount=inv.amount,
                payment_status=inv.payment_status,
            )
            for inv in self.tools.db.invoices
            if inv.treatment_id in owner_treatment_ids
        ]


def get_environment(
    db: Optional[VetClinicDB] = None,
    user_db: Optional[VetClinicUserDB] = None,
    solo_mode: bool = False,
) -> VetClinicEnvironment:
    """Factory function to create the vet clinic environment."""
    if db is None:
        db = VetClinicDB.load(VET_CLINIC_DB_PATH)
    tools = VetClinicTools(db)
    if user_db is None:
        user_db = VetClinicUserDB.load(VET_CLINIC_USER_DB_PATH)
    user_tools = VetClinicUserTools(user_db)
    policy = load_file(VET_CLINIC_POLICY_PATH)
    env = VetClinicEnvironment(
        domain_name="vet_clinic",
        policy=policy,
        tools=tools,
        user_tools=user_tools,
    )
    if solo_mode:
        env.set_solo_mode(True)
    return env


def load_tasks(path: str) -> list[Task]:
    """Load tasks from a JSON file."""
    tasks = load_file(path)
    if isinstance(tasks, dict) and "tasks" in tasks:
        tasks = tasks["tasks"]
    return [Task.model_validate(task) for task in tasks]


def get_tasks(task_split_name: Optional[str] = "base") -> list[Task]:
    """Get tasks for the domain, shuffled for representative sampling."""
    if not VET_CLINIC_TASK_SET_PATH.exists():
        return []
    tasks = load_tasks(VET_CLINIC_TASK_SET_PATH)
    if task_split_name is None:
        pass
    else:
        task_splits = get_tasks_split()
        if task_splits is not None and task_split_name in task_splits:
            tasks = [task for task in tasks if task.id in task_splits[task_split_name]]
    # Shuffle with fixed seed so --num-tasks N gets a representative sample
    rng = random.Random(42)
    rng.shuffle(tasks)
    return tasks


def get_tasks_split() -> Optional[dict[str, list[str]]]:
    """Load task splits from JSON if they exist."""
    split_file = (
        Path(VET_CLINIC_TASK_SET_PATH).parent
        / f"split_{Path(VET_CLINIC_TASK_SET_PATH).stem}.json"
    )
    if split_file.exists():
        return load_file(split_file)
    return None
