from fastapi import APIRouter

from app.routes import (
    admin, appointments, auth, departments, doctors, hospitals, medical_records, notifications, patients, reviews, slots, smart, waitlist,
)

api_router = APIRouter()
for module in (auth, patients, doctors, hospitals, departments, appointments, slots, medical_records, reviews, notifications, waitlist, smart, admin):
    api_router.include_router(module.router)
