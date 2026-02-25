from typing import Any, Dict, List, Optional

from tau2.domains.auto_repair.data_model import (
    AutoRepairDB,
    Customer,
    Invoice,
    ServiceOrder,
    Vehicle,
    WarrantyPlan,
)
from tau2.environment.toolkit import ToolKitBase, ToolType, is_tool


class AutoRepairTools(ToolKitBase):
    db: AutoRepairDB

    def __init__(self, db: AutoRepairDB):
        super().__init__(db)

    # =============================================
    # PRIVATE HELPERS
    # =============================================

    def _find_customer(self, customer_id: str) -> Customer:
        for c in self.db.customers:
            if c.customer_id == customer_id:
                return c
        raise ValueError(f"Customer '{customer_id}' not found.")

    def _find_customer_by_name(self, name: str) -> Optional[Customer]:
        name_lower = name.strip().lower()
        for c in self.db.customers:
            if c.name.lower() == name_lower:
                return c
        return None

    def _find_vehicle(self, vehicle_id: str) -> Vehicle:
        for v in self.db.vehicles:
            if v.vehicle_id == vehicle_id:
                return v
        raise ValueError(f"Vehicle '{vehicle_id}' not found.")

    def _find_order(self, order_id: str) -> ServiceOrder:
        for o in self.db.service_orders:
            if o.order_id == order_id:
                return o
        raise ValueError(f"Service order '{order_id}' not found.")

    def _find_invoice(self, invoice_id: str) -> Invoice:
        for i in self.db.invoices:
            if i.invoice_id == invoice_id:
                return i
        raise ValueError(f"Invoice '{invoice_id}' not found.")

    def _find_warranty(self, warranty_id: str) -> WarrantyPlan:
        for w in self.db.warranty_plans:
            if w.warranty_id == warranty_id:
                return w
        raise ValueError(f"Warranty plan '{warranty_id}' not found.")

    # =============================================
    # READ TOOLS — with information-hiding gates
    # =============================================

    @is_tool(ToolType.READ)
    def get_customer_by_name(self, name: str) -> Dict[str, Any]:
        """
        Look up a customer by name.

        Args:
            name: Customer's full name.

        Returns:
            Customer details including ID, contact info, and account status.
        """
        customer = self._find_customer_by_name(name)
        if customer is None:
            raise ValueError(f"No customer found with name '{name}'.")
        return {
            "customer_id": customer.customer_id,
            "name": customer.name,
            "phone": customer.phone,
            "email": customer.email,
            "account_status": customer.account_status,
        }

    @is_tool(ToolType.READ)
    def get_customer_by_id(self, customer_id: str) -> Dict[str, Any]:
        """
        Look up a customer by their customer ID.

        Args:
            customer_id: The unique customer identifier.

        Returns:
            Customer details including name, contact info, and account status.
        """
        customer = self._find_customer(customer_id)
        return {
            "customer_id": customer.customer_id,
            "name": customer.name,
            "phone": customer.phone,
            "email": customer.email,
            "account_status": customer.account_status,
        }

    @is_tool(ToolType.READ)
    def get_vehicles(self, customer_id: str) -> Any:
        """
        Get all vehicles registered to a customer.

        Args:
            customer_id: The customer's unique identifier.

        Returns:
            List of vehicles with make, model, year, mileage, and registration
            status. Returns an error message if the account is not active.
        """
        customer = self._find_customer(customer_id)
        # INFORMATION HIDING: account status gates vehicle access
        if customer.account_status == "suspended":
            return (
                f"Account {customer_id} is currently suspended. "
                "Reactivate the account before accessing vehicle records."
            )
        if customer.account_status == "flagged":
            return (
                f"Account {customer_id} is flagged for review. "
                "Clear the account flag before accessing vehicle records."
            )
        vehicles = [v for v in self.db.vehicles if v.customer_id == customer_id]
        # Return surface info only — diagnostic fields are hidden
        return [
            {
                "vehicle_id": v.vehicle_id,
                "make": v.make,
                "model": v.model,
                "year": v.year,
                "mileage": v.mileage,
                "registration_status": v.registration_status,
            }
            for v in vehicles
        ]

    @is_tool(ToolType.READ)
    def get_service_orders(self, vehicle_id: str) -> Any:
        """
        Get all service orders for a vehicle.

        Args:
            vehicle_id: The vehicle's unique identifier.

        Returns:
            List of service orders with type, date, technician, and status.
            Returns an error message if the vehicle registration is expired.
        """
        vehicle = self._find_vehicle(vehicle_id)
        # INFORMATION HIDING: registration status gates service order access
        if vehicle.registration_status == "expired":
            return (
                f"Vehicle {vehicle_id} has expired registration. "
                "Update registration before viewing service details."
            )
        orders = [o for o in self.db.service_orders if o.vehicle_id == vehicle_id]
        return [
            {
                "order_id": o.order_id,
                "service_type": o.service_type,
                "scheduled_date": o.scheduled_date,
                "technician": o.technician,
                "status": o.status,
                "notes": o.notes,
            }
            for o in orders
        ]

    @is_tool(ToolType.READ)
    def get_invoices(self, customer_id: str) -> Any:
        """
        Get all invoices for a customer.

        Args:
            customer_id: The customer's unique identifier.

        Returns:
            List of invoices with amounts, status, and descriptions.
            Returns an error message if the account is not active.
        """
        customer = self._find_customer(customer_id)
        # INFORMATION HIDING: account status gates invoice access
        if customer.account_status != "active":
            return (
                f"Account {customer_id} is not active (status: {customer.account_status}). "
                "Resolve account issues before viewing invoices."
            )
        invoices = [i for i in self.db.invoices if i.customer_id == customer_id]
        return [
            {
                "invoice_id": i.invoice_id,
                "order_id": i.order_id,
                "labor_hours": i.labor_hours,
                "labor_rate": i.labor_rate,
                "parts_cost": i.parts_cost,
                "discount_pct": i.discount_pct,
                "total": i.total,
                "status": i.status,
                "description": i.description,
            }
            for i in invoices
        ]

    @is_tool(ToolType.READ)
    def get_warranty(self, vehicle_id: str) -> Any:
        """
        Get the warranty plan for a vehicle.

        Args:
            vehicle_id: The vehicle's unique identifier.

        Returns:
            Warranty plan details or a message if no warranty is on file.
        """
        self._find_vehicle(vehicle_id)
        plans = [w for w in self.db.warranty_plans if w.vehicle_id == vehicle_id]
        if not plans:
            return f"No warranty plan on file for vehicle {vehicle_id}."
        w = plans[0]
        return {
            "warranty_id": w.warranty_id,
            "coverage_type": w.coverage_type,
            "status": w.status,
            "expiry_date": w.expiry_date,
        }

    @is_tool(ToolType.READ)
    def run_diagnostic(self, order_id: str) -> Dict[str, Any]:
        """
        Run a diagnostic scan on the vehicle associated with a service order.
        Checks brakes, engine, tires, and electrical systems.

        Args:
            order_id: The service order to run diagnostics for.

        Returns:
            Diagnostic results including any issues detected.
        """
        order = self._find_order(order_id)
        vehicle = self._find_vehicle(order.vehicle_id)

        issues = []
        if vehicle.brake_pad_thickness < 3.0:
            issues.append(
                f"Worn brake pads (thickness: {vehicle.brake_pad_thickness:.1f}mm, "
                "minimum: 3.0mm) - replacement needed"
            )
        if vehicle.brake_fluid_level == "low":
            issues.append("Brake fluid level is low - flush and refill needed")
        if vehicle.oil_life_pct < 20:
            issues.append(
                f"Oil change overdue (oil life: {vehicle.oil_life_pct}%, "
                "threshold: 20%) - service needed"
            )
        if vehicle.air_filter_status == "clogged":
            issues.append("Air filter is clogged - replacement needed")
        if vehicle.tire_pressure_psi < 30:
            issues.append(
                f"Tire pressure low ({vehicle.tire_pressure_psi} PSI, "
                "recommended: 32-35 PSI) - inflation needed"
            )
        if vehicle.wheel_alignment == "misaligned":
            issues.append("Wheel alignment is off - adjustment needed")
        if vehicle.battery_voltage < 12.4:
            issues.append(
                f"Battery voltage low ({vehicle.battery_voltage:.1f}V, "
                "minimum: 12.4V) - replacement recommended"
            )
        if vehicle.alternator_output == "faulty":
            issues.append("Alternator output abnormal - replacement recommended")

        return {
            "order_id": order_id,
            "vehicle_id": vehicle.vehicle_id,
            "vehicle": f"{vehicle.year} {vehicle.make} {vehicle.model}",
            "issues_detected": issues,
            "issue_count": len(issues),
            "status": "issues_found" if issues else "all_clear",
        }

    # =============================================
    # WRITE TOOLS — account / registration fixes
    # =============================================

    @is_tool(ToolType.WRITE)
    def reactivate_account(self, customer_id: str) -> str:
        """
        Reactivate a suspended customer account.

        Args:
            customer_id: The customer's unique identifier.

        Returns:
            Confirmation message.
        """
        customer = self._find_customer(customer_id)
        if customer.account_status != "suspended":
            return f"Account {customer_id} is not suspended (status: {customer.account_status}). No changes made."
        customer.account_status = "active"
        return f"Account {customer_id} has been reactivated."

    @is_tool(ToolType.WRITE)
    def clear_account_flag(self, customer_id: str) -> str:
        """
        Clear a flag on a customer account after review.

        Args:
            customer_id: The customer's unique identifier.

        Returns:
            Confirmation message.
        """
        customer = self._find_customer(customer_id)
        if customer.account_status != "flagged":
            return f"Account {customer_id} is not flagged (status: {customer.account_status}). No changes made."
        customer.account_status = "active"
        return f"Account {customer_id} flag has been cleared."

    @is_tool(ToolType.WRITE)
    def update_registration(self, vehicle_id: str) -> str:
        """
        Update a vehicle's expired registration to current.

        Args:
            vehicle_id: The vehicle's unique identifier.

        Returns:
            Confirmation message.
        """
        vehicle = self._find_vehicle(vehicle_id)
        if vehicle.registration_status != "expired":
            return f"Vehicle {vehicle_id} registration is already current. No changes made."
        vehicle.registration_status = "current"
        return f"Vehicle {vehicle_id} registration has been updated to current."

    # =============================================
    # WRITE TOOLS — service scheduling fixes
    # =============================================

    @is_tool(ToolType.WRITE)
    def reschedule_service(self, order_id: str, new_date: str) -> str:
        """
        Reschedule a service order to a new date.

        Args:
            order_id: The service order identifier.
            new_date: The new scheduled date (YYYY-MM-DD).

        Returns:
            Confirmation message.
        """
        order = self._find_order(order_id)
        old_date = order.scheduled_date
        order.scheduled_date = new_date
        return f"Service order {order_id} rescheduled from {old_date} to {new_date}."

    @is_tool(ToolType.WRITE)
    def update_service_type(self, order_id: str, service_type: str) -> str:
        """
        Update the service type on a service order.

        Args:
            order_id: The service order identifier.
            service_type: The correct service type.

        Returns:
            Confirmation message.
        """
        order = self._find_order(order_id)
        old_type = order.service_type
        order.service_type = service_type
        return f"Service order {order_id} type updated from '{old_type}' to '{service_type}'."

    # =============================================
    # WRITE TOOLS — mechanical / electrical repairs
    # =============================================

    @is_tool(ToolType.WRITE)
    def replace_brake_pads(self, order_id: str) -> str:
        """
        Replace worn brake pads on the vehicle in a service order.

        Args:
            order_id: The service order identifier.

        Returns:
            Confirmation message.
        """
        order = self._find_order(order_id)
        vehicle = self._find_vehicle(order.vehicle_id)
        vehicle.brake_pad_thickness = 12.0
        return f"Brake pads replaced on vehicle {vehicle.vehicle_id}. New thickness: 12.0mm."

    @is_tool(ToolType.WRITE)
    def flush_brake_fluid(self, order_id: str) -> str:
        """
        Flush and refill brake fluid on the vehicle in a service order.

        Args:
            order_id: The service order identifier.

        Returns:
            Confirmation message.
        """
        order = self._find_order(order_id)
        vehicle = self._find_vehicle(order.vehicle_id)
        vehicle.brake_fluid_level = "normal"
        return f"Brake fluid flushed and refilled on vehicle {vehicle.vehicle_id}."

    @is_tool(ToolType.WRITE)
    def perform_oil_change(self, order_id: str) -> str:
        """
        Perform an oil change on the vehicle in a service order.

        Args:
            order_id: The service order identifier.

        Returns:
            Confirmation message.
        """
        order = self._find_order(order_id)
        vehicle = self._find_vehicle(order.vehicle_id)
        vehicle.oil_life_pct = 100
        return f"Oil changed on vehicle {vehicle.vehicle_id}. Oil life: 100%."

    @is_tool(ToolType.WRITE)
    def replace_air_filter(self, order_id: str) -> str:
        """
        Replace a clogged air filter on the vehicle in a service order.

        Args:
            order_id: The service order identifier.

        Returns:
            Confirmation message.
        """
        order = self._find_order(order_id)
        vehicle = self._find_vehicle(order.vehicle_id)
        vehicle.air_filter_status = "clean"
        return f"Air filter replaced on vehicle {vehicle.vehicle_id}."

    @is_tool(ToolType.WRITE)
    def inflate_tires(self, order_id: str) -> str:
        """
        Inflate tires to the correct pressure on the vehicle in a service order.

        Args:
            order_id: The service order identifier.

        Returns:
            Confirmation message.
        """
        order = self._find_order(order_id)
        vehicle = self._find_vehicle(order.vehicle_id)
        vehicle.tire_pressure_psi = 35
        return f"Tires inflated to 35 PSI on vehicle {vehicle.vehicle_id}."

    @is_tool(ToolType.WRITE)
    def align_wheels(self, order_id: str) -> str:
        """
        Perform wheel alignment on the vehicle in a service order.

        Args:
            order_id: The service order identifier.

        Returns:
            Confirmation message.
        """
        order = self._find_order(order_id)
        vehicle = self._find_vehicle(order.vehicle_id)
        vehicle.wheel_alignment = "aligned"
        return f"Wheels aligned on vehicle {vehicle.vehicle_id}."

    @is_tool(ToolType.WRITE)
    def replace_battery(self, order_id: str) -> str:
        """
        Replace the battery on the vehicle in a service order.

        Args:
            order_id: The service order identifier.

        Returns:
            Confirmation message.
        """
        order = self._find_order(order_id)
        vehicle = self._find_vehicle(order.vehicle_id)
        vehicle.battery_voltage = 12.8
        return f"Battery replaced on vehicle {vehicle.vehicle_id}. Voltage: 12.8V."

    @is_tool(ToolType.WRITE)
    def replace_alternator(self, order_id: str) -> str:
        """
        Replace a faulty alternator on the vehicle in a service order.

        Args:
            order_id: The service order identifier.

        Returns:
            Confirmation message.
        """
        order = self._find_order(order_id)
        vehicle = self._find_vehicle(order.vehicle_id)
        vehicle.alternator_output = "normal"
        return f"Alternator replaced on vehicle {vehicle.vehicle_id}."

    # =============================================
    # WRITE TOOLS — warranty fixes
    # =============================================

    @is_tool(ToolType.WRITE)
    def renew_warranty(self, warranty_id: str, coverage_type: str) -> str:
        """
        Renew an expired warranty plan.

        Args:
            warranty_id: The warranty plan identifier.
            coverage_type: The coverage type to renew (basic, extended, premium).

        Returns:
            Confirmation message.
        """
        warranty = self._find_warranty(warranty_id)
        if warranty.status != "expired":
            return f"Warranty {warranty_id} is not expired (status: {warranty.status}). No changes made."
        warranty.status = "active"
        warranty.coverage_type = coverage_type
        return f"Warranty {warranty_id} renewed with {coverage_type} coverage."

    # =============================================
    # WRITE TOOLS — billing fixes
    # =============================================

    @is_tool(ToolType.WRITE)
    def adjust_labor_charge(self, invoice_id: str, labor_hours: float) -> str:
        """
        Adjust the labor hours on an invoice.

        Args:
            invoice_id: The invoice identifier.
            labor_hours: The correct number of labor hours.

        Returns:
            Confirmation message with updated total.
        """
        invoice = self._find_invoice(invoice_id)
        invoice.labor_hours = labor_hours
        invoice.total = round(
            (invoice.labor_hours * invoice.labor_rate + invoice.parts_cost)
            * (1 - invoice.discount_pct / 100),
            2,
        )
        return (
            f"Invoice {invoice_id} labor adjusted to {labor_hours} hours. "
            f"New total: ${invoice.total:.2f}."
        )

    @is_tool(ToolType.WRITE)
    def apply_discount(self, invoice_id: str, discount_pct: float) -> str:
        """
        Apply a discount percentage to an invoice.

        Args:
            invoice_id: The invoice identifier.
            discount_pct: The discount percentage to apply (0-100).

        Returns:
            Confirmation message with updated total.
        """
        invoice = self._find_invoice(invoice_id)
        invoice.discount_pct = discount_pct
        invoice.total = round(
            (invoice.labor_hours * invoice.labor_rate + invoice.parts_cost)
            * (1 - invoice.discount_pct / 100),
            2,
        )
        return (
            f"Invoice {invoice_id} discount updated to {discount_pct}%. "
            f"New total: ${invoice.total:.2f}."
        )

    # =============================================
    # GENERIC TOOLS
    # =============================================

    @is_tool(ToolType.GENERIC)
    def transfer_to_human(self, summary: str) -> str:
        """
        Transfer the call to a human specialist.

        Args:
            summary: Brief description of the issue for the specialist.

        Returns:
            Confirmation of transfer.
        """
        return f"Call transferred to human specialist. Summary: {summary}"

    # =============================================
    # SETUP HELPERS — called by scenarios init
    # =============================================

    def set_account_status(self, customer_id: str, status: str) -> None:
        customer = self._find_customer(customer_id)
        customer.account_status = status

    def set_registration_status(self, vehicle_id: str, status: str) -> None:
        vehicle = self._find_vehicle(vehicle_id)
        vehicle.registration_status = status

    def set_service_date(self, order_id: str, date: str) -> None:
        order = self._find_order(order_id)
        order.scheduled_date = date

    def set_service_type(self, order_id: str, service_type: str) -> None:
        order = self._find_order(order_id)
        order.service_type = service_type

    def set_brake_pad_thickness(self, vehicle_id: str, thickness: float) -> None:
        vehicle = self._find_vehicle(vehicle_id)
        vehicle.brake_pad_thickness = thickness

    def set_brake_fluid_level(self, vehicle_id: str, level: str) -> None:
        vehicle = self._find_vehicle(vehicle_id)
        vehicle.brake_fluid_level = level

    def set_oil_life(self, vehicle_id: str, pct: int) -> None:
        vehicle = self._find_vehicle(vehicle_id)
        vehicle.oil_life_pct = pct

    def set_air_filter_status(self, vehicle_id: str, status: str) -> None:
        vehicle = self._find_vehicle(vehicle_id)
        vehicle.air_filter_status = status

    def set_tire_pressure(self, vehicle_id: str, psi: int) -> None:
        vehicle = self._find_vehicle(vehicle_id)
        vehicle.tire_pressure_psi = psi

    def set_wheel_alignment(self, vehicle_id: str, alignment: str) -> None:
        vehicle = self._find_vehicle(vehicle_id)
        vehicle.wheel_alignment = alignment

    def set_battery_voltage(self, vehicle_id: str, voltage: float) -> None:
        vehicle = self._find_vehicle(vehicle_id)
        vehicle.battery_voltage = voltage

    def set_alternator_output(self, vehicle_id: str, output: str) -> None:
        vehicle = self._find_vehicle(vehicle_id)
        vehicle.alternator_output = output

    def set_warranty_status(self, warranty_id: str, status: str) -> None:
        warranty = self._find_warranty(warranty_id)
        warranty.status = status

    def set_warranty_coverage(self, warranty_id: str, coverage_type: str) -> None:
        warranty = self._find_warranty(warranty_id)
        warranty.coverage_type = coverage_type

    def set_labor_hours(self, invoice_id: str, hours: float) -> None:
        invoice = self._find_invoice(invoice_id)
        invoice.labor_hours = hours
        invoice.total = round(
            (invoice.labor_hours * invoice.labor_rate + invoice.parts_cost)
            * (1 - invoice.discount_pct / 100),
            2,
        )

    def set_discount_pct(self, invoice_id: str, pct: float) -> None:
        invoice = self._find_invoice(invoice_id)
        invoice.discount_pct = pct
        invoice.total = round(
            (invoice.labor_hours * invoice.labor_rate + invoice.parts_cost)
            * (1 - invoice.discount_pct / 100),
            2,
        )

    # =============================================
    # ASSERTION HELPERS — called by verification
    # =============================================

    def assert_account_status(self, customer_id: str, expected: str) -> bool:
        customer = self._find_customer(customer_id)
        return customer.account_status == expected

    def assert_registration_status(self, vehicle_id: str, expected: str) -> bool:
        vehicle = self._find_vehicle(vehicle_id)
        return vehicle.registration_status == expected

    def assert_service_date(self, order_id: str, expected_date: str) -> bool:
        order = self._find_order(order_id)
        return order.scheduled_date == expected_date

    def assert_service_type(self, order_id: str, expected_type: str) -> bool:
        order = self._find_order(order_id)
        return order.service_type == expected_type

    def assert_brake_pad_thickness(self, vehicle_id: str, min_thickness: float) -> bool:
        vehicle = self._find_vehicle(vehicle_id)
        return vehicle.brake_pad_thickness >= min_thickness

    def assert_brake_fluid_level(self, vehicle_id: str, expected: str) -> bool:
        vehicle = self._find_vehicle(vehicle_id)
        return vehicle.brake_fluid_level == expected

    def assert_oil_life(self, vehicle_id: str, min_pct: int) -> bool:
        vehicle = self._find_vehicle(vehicle_id)
        return vehicle.oil_life_pct >= min_pct

    def assert_air_filter_status(self, vehicle_id: str, expected: str) -> bool:
        vehicle = self._find_vehicle(vehicle_id)
        return vehicle.air_filter_status == expected

    def assert_tire_pressure(self, vehicle_id: str, min_psi: int) -> bool:
        vehicle = self._find_vehicle(vehicle_id)
        return vehicle.tire_pressure_psi >= min_psi

    def assert_wheel_alignment(self, vehicle_id: str, expected: str) -> bool:
        vehicle = self._find_vehicle(vehicle_id)
        return vehicle.wheel_alignment == expected

    def assert_battery_voltage(self, vehicle_id: str, min_voltage: float) -> bool:
        vehicle = self._find_vehicle(vehicle_id)
        return vehicle.battery_voltage >= min_voltage

    def assert_alternator_output(self, vehicle_id: str, expected: str) -> bool:
        vehicle = self._find_vehicle(vehicle_id)
        return vehicle.alternator_output == expected

    def assert_warranty_status(self, warranty_id: str, expected: str) -> bool:
        warranty = self._find_warranty(warranty_id)
        return warranty.status == expected

    def assert_labor_hours(self, invoice_id: str, expected_hours: float) -> bool:
        invoice = self._find_invoice(invoice_id)
        return abs(invoice.labor_hours - expected_hours) < 0.01

    def assert_discount_pct(self, invoice_id: str, expected_pct: float) -> bool:
        invoice = self._find_invoice(invoice_id)
        return abs(invoice.discount_pct - expected_pct) < 0.01
