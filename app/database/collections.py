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
    NOTIFICATION_PREFERENCES = "notification_preferences"
    WAITLIST_ENTRIES = "waitlist_entries"
    WAITLIST_OFFERS = "waitlist_offers"
    RESCHEDULING_REQUESTS = "rescheduling_requests"
    # Additional collections
    SYMPTOM_ROUTING_RULES = "symptom_routing_rules"  # editable rules for department routing
    INTAKE_EVENTS = "intake_events"  # audit trail of open/close decisions
    # Phase 4 collections
    MEDICAL_DOCUMENTS = "medical_documents"
    DOCUMENT_SHARES = "document_shares"
    MEDICAL_RECORD_AUDITS = "medical_record_audits"
    # Phase 6 collections
    AUDIT_LOGS = "audit_logs"
