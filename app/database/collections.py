"""Collection names in one place."""


class C:
    USERS = "users"
    PATIENTS = "patients"
    DOCTORS = "doctors"
    HOSPITALS = "hospitals"
    DEPARTMENTS = "departments"
    DOCTOR_AVAILABILITY = "doctor_availability"
    APPOINTMENT_SLOTS = "appointment_slots"
    APPOINTMENTS = "appointments"
    APPOINTMENT_HISTORY = "appointment_history"
    MEDICAL_RECORDS = "medical_records"
    REVIEWS = "reviews"
    NOTIFICATIONS = "notifications"
    WAITLIST_ENTRIES = "waitlist_entries"
    # Additional collections
    SYMPTOM_ROUTING_RULES = "symptom_routing_rules"  # editable rules for department routing
    INTAKE_EVENTS = "intake_events"  # audit trail of open/close decisions
