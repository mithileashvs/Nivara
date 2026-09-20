from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query

from app.core.dependencies import DB, CurrentUser, SettingsDep
from app.routes.docs import errs
from app.schemas.smart import (
    AppointmentOptionsPage, DepartmentSuggestionRequest, DepartmentSuggestionResponse, DoctorMatchPage, MatchCriteria,
)
from app.services.appointment_optimization_service import AppointmentOptimizationService
from app.services.department_routing_service import DepartmentRoutingService
from app.services.doctor_matching_service import DoctorMatchingService
from app.utils.pagination import PageParams, page_params

router = APIRouter(prefix="/smart", tags=["Smart Features"])

NOT_MEDICAL = "This is appointment discovery only — NOT a medical recommendation."


@router.post("/department-suggestion", response_model=DepartmentSuggestionResponse, summary="Suggest a department from symptoms (routing only)",
             description=("Rule-based **routing**: maps the symptoms you list to the department to book with. It does not diagnose, predict disease, or suggest "
                          "medicines, dosages or treatment; inputs asking for those are ignored. Rules are stored in the database and admin-editable. "
                          "**Auth:** any role."),
             responses=errs(401, 422))
async def department_suggestion(payload: DepartmentSuggestionRequest, _u: CurrentUser, db: DB) -> Any:
    return await DepartmentRoutingService(db).suggest(payload.symptoms, payload.hospital_id)


@router.get("/doctor-matching", response_model=DoctorMatchPage, summary="Find matching doctors with bookable slots (query params)",
            description=(f"{NOT_MEDICAL} Returns only doctors with genuinely bookable slots, ranked by a configurable, fully explained score "
                         "(`score_breakdown` lists every factor). **Auth:** any role."),
            responses=errs(400, 401, 422))
async def doctor_matching_get(_u: CurrentUser, db: DB, settings: SettingsDep, c: Annotated[MatchCriteria, Query()],
                              params: Annotated[PageParams, Depends(page_params)]) -> Any:
    return await DoctorMatchingService(db, settings).match_doctors(c, params.page, params.page_size)


@router.post("/doctor-matching", response_model=DoctorMatchPage, summary="Find matching doctors with bookable slots (JSON body)",
             description=f"{NOT_MEDICAL} Same as the GET variant, with criteria in the body. **Auth:** any role.", responses=errs(400, 401, 422))
async def doctor_matching_post(c: MatchCriteria, _u: CurrentUser, db: DB, settings: SettingsDep,
                               params: Annotated[PageParams, Depends(page_params)]) -> Any:
    return await DoctorMatchingService(db, settings).match_doctors(c, params.page, params.page_size)


@router.post("/appointment-options", response_model=AppointmentOptionsPage, summary="Ranked bookable appointment options",
             description=(f"{NOT_MEDICAL} Slot-level optimisation: every option is a real bookable slot, scored with the same transparent, "
                          "configurable factors (earlier and preferred-time slots rank higher). **Auth:** any role."),
             responses=errs(400, 401, 422))
async def appointment_options(c: MatchCriteria, _u: CurrentUser, db: DB, settings: SettingsDep,
                              params: Annotated[PageParams, Depends(page_params)]) -> Any:
    return await AppointmentOptimizationService(db, settings).find_options(c, params.page, params.page_size)
