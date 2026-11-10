from fastapi import APIRouter

from app.routes import (
    admin, admin_audit, analytics, appointments, auth, departments, doctors, hospitals, medical_records, notifications, patients,
    reschedule_requests, reviews, slots, smart, waitlist,
)

api_router = APIRouter()
for module in (
    auth, patients, doctors, hospitals, departments, appointments, slots, medical_records, reviews,
    notifications, waitlist, smart, admin, admin_audit, analytics, reschedule_requests,
):
    api_router.include_router(module.router)
