from typing import Annotated, Any

from fastapi import APIRouter, Depends, status
from fastapi.security import OAuth2PasswordRequestForm

from app.core.dependencies import DB, CurrentUser, SettingsDep
from app.core.rate_limit import auth_rate_limit
from app.routes.docs import errs
from app.schemas.auth import LoginRequest, OAuth2TokenResponse, RegisterRequest, TokenResponse, UserOut
from app.services.auth_service import AuthService
from app.utils.serialization import to_api

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post(
    "/register", response_model=UserOut, status_code=status.HTTP_201_CREATED, dependencies=[Depends(auth_rate_limit)],
    summary="Register a patient or doctor account",
    description=(
        "Creates an account and the matching profile. Only `PATIENT` and `DOCTOR` can self-register; admins are created by "
        "an existing platform admin. Doctor accounts start as `PENDING` and cannot publish availability until an admin "
        "activates the profile. **Auth:** none."
    ),
    responses=errs(409, 422, 429),
)
async def register(payload: RegisterRequest, db: DB, settings: SettingsDep) -> Any:
    return to_api(await AuthService(db, settings).register(payload))


async def _login(email: str, password: str, db: Any, settings: Any) -> tuple[dict, str, int]:
    return await AuthService(db, settings).authenticate(email, password)


@router.post(
    "/login", response_model=TokenResponse, dependencies=[Depends(auth_rate_limit)], summary="Log in and get an access token",
    description="Exchanges email + password for a short-lived JWT bearer token. **Auth:** none.", responses=errs(401, 422, 429),
)
async def login(payload: LoginRequest, db: DB, settings: SettingsDep) -> Any:
    user, token, expires_in = await _login(payload.email, payload.password, db, settings)
    return {"access_token": token, "token_type": "bearer", "expires_in": expires_in, "user": to_api(user)}


@router.post(
    "/token", response_model=OAuth2TokenResponse, dependencies=[Depends(auth_rate_limit)],
    summary="OAuth2 password-flow token (for Swagger 'Authorize')",
    description="Same as `/login` but accepts `application/x-www-form-urlencoded` (`username` = email). Lets the Swagger UI **Authorize** button work.",
    responses=errs(401, 422, 429),
)
async def token(form: Annotated[OAuth2PasswordRequestForm, Depends()], db: DB, settings: SettingsDep) -> Any:
    _user, tok, _ = await _login(form.username.lower(), form.password, db, settings)
    return {"access_token": tok, "token_type": "bearer"}


@router.get(
    "/me", response_model=UserOut, summary="Get the current user",
    description="Returns the authenticated account. **Auth:** any role.", responses=errs(401),
)
async def me(user: CurrentUser) -> Any:
    return to_api(user)
