"""Application settings, loaded from environment variables / `.env`.

Nothing secret has a default value: the app refuses to start without a JWT
secret and a MongoDB URI, and refuses weak secrets in production.
"""
import ipaddress
from functools import lru_cache
from typing import Annotated, Literal

from pydantic import BaseModel, Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class MatchingConfig(BaseModel):
    """Configurable, transparent scoring for doctor matching / appointment options.

    Every factor has a weight; the API returns each factor's contribution so the
    result is never an unexplained black-box score. Override via the
    ``MATCHING_CONFIG`` environment variable (JSON); omitted keys keep defaults.
    """

    weights: dict[str, float] = Field(
        default_factory=lambda: {
            "specialty": 30.0,
            "department": 15.0,
            "hospital_preference": 10.0,
            "consultation_type": 10.0,
            "availability_soon": 20.0,
            "availability_depth": 5.0,
            "preferred_time": 10.0,
            "location": 10.0,
        }
    )
    # Waitlist ranking (transparent additive points; also returned in the notification payload)
    waitlist_weights: dict[str, float] = Field(
        default_factory=lambda: {
            "doctor": 30.0,
            "specialty": 15.0,
            "department": 15.0,
            "hospital": 10.0,
            "time_window": 10.0,
            "consultation_type": 5.0,
            "earlier_than_existing": 15.0,
            "waiting_time": 10.0,  # scaled by days waited, capped at waiting_time_cap_days
        }
    )
    waiting_time_cap_days: int = Field(default=14, ge=1)
    availability_horizon_days: int = Field(default=14, ge=1, le=90)
    availability_depth_target: int = Field(default=5, ge=1)
    location_max_distance_km: float = Field(default=25.0, gt=0)
    max_candidate_doctors: int = Field(default=200, ge=1, le=1000)

    @field_validator("weights")
    @classmethod
    def _non_negative(cls, v: dict[str, float]) -> dict[str, float]:
        if any(w < 0 for w in v.values()):
            raise ValueError("matching weights must be >= 0")
        return v

    @model_validator(mode="after")
    def _fill_defaults(self) -> "MatchingConfig":
        for field in ("weights", "waitlist_weights"):
            defaults = MatchingConfig.model_fields[field].default_factory()  # type: ignore[misc]
            target = getattr(self, field)
            for key, value in defaults.items():
                target.setdefault(key, value)
        return self


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Nivara API"
    app_version: str = "1.0.0"
    environment: Literal["development", "test", "production"] = "development"

    # --- database ---
    database_url: str = Field(default="postgresql+asyncpg://postgres:postgres@localhost:5432/nivara")
    database_name: str = "nivara"
    mongodb_uri: str | None = None  # kept optional for legacy config compatibility

    # --- auth ---
    jwt_secret: SecretStr
    jwt_algorithm: Literal["HS256", "HS384", "HS512"] = "HS256"
    access_token_expire_minutes: int = Field(default=60, ge=1, le=60 * 24 * 7)
    bcrypt_rounds: int = Field(default=12, ge=4, le=15)

    # --- http ---
    cors_origins: Annotated[list[str], NoDecode] = Field(default_factory=list)
    log_level: str = "INFO"
    api_prefix: str = "/api/v1"

    # --- proxy & client IP handling ---
    # Security rule: forwarded IP headers (X-Forwarded-For, X-Real-IP) are NEVER
    # trusted unless trust_proxy_headers=True AND the direct socket peer IP matches
    # a configured IP/CIDR in trusted_proxy_ips.
    # For Render production deployments behind Render's TLS reverse proxy, set:
    #   TRUST_PROXY_HEADERS=true
    #   TRUSTED_PROXY_IPS=127.0.0.1/32,::1/128,10.0.0.0/8,172.16.0.0/12,192.168.0.0/16,100.64.0.0/10
    trust_proxy_headers: bool = False
    trusted_proxy_ips: Annotated[list[str], NoDecode] = Field(default_factory=list)

    # --- scheduling ---
    app_timezone: str = "Asia/Kolkata"
    request_hold_minutes: int = Field(default=720, ge=1)
    max_pending_requests_per_patient: int = Field(default=5, ge=1)
    max_scheduling_horizon_days: int = Field(default=90, ge=1, le=365)
    min_booking_lead_minutes: int = Field(default=15, ge=0)
    reminder_hours_before: int = Field(default=24, ge=1)

    # --- background jobs ---
    background_jobs_enabled: bool = True
    background_job_interval_seconds: int = Field(default=60, ge=5)

    # --- waitlist ---
    waitlist_notify_top_n: int = Field(default=3, ge=1, le=20)
    waitlist_max_active_entries_per_patient: int = Field(default=10, ge=1)
    waitlist_offer_expiry_minutes: int = Field(default=15, ge=1, le=1440)

    # --- rate limiting ---
    rate_limit_enabled: bool = True
    rate_limit_auth_per_minute: int = Field(default=10, ge=1)

    # --- documents (metadata only; files live in external object storage) ---
    allowed_document_hosts: Annotated[list[str], NoDecode] = Field(default_factory=list)

    # --- medical documents & object storage (Phase 4) ---
    supabase_url: str | None = None
    supabase_service_role_key: SecretStr | None = None
    supabase_storage_bucket: str = "medical-documents"
    document_storage_provider: Literal["local", "supabase"] = "local"
    local_storage_dir: str = "storage/medical_documents"
    max_document_upload_bytes: int = Field(default=25 * 1024 * 1024, ge=1024)  # 25 MB

    matching_config: MatchingConfig = Field(default_factory=MatchingConfig)

    @field_validator("cors_origins", "allowed_document_hosts", "trusted_proxy_ips", mode="before")
    @classmethod
    def _split_csv(cls, v):
        if isinstance(v, str):
            return [item.strip() for item in v.split(",") if item.strip()]
        return v

    @field_validator("trusted_proxy_ips")
    @classmethod
    def _validate_trusted_proxy_ips(cls, v: list[str]) -> list[str]:
        normalized: list[str] = []
        for entry in v:
            cleaned = str(entry).strip()
            if not cleaned:
                continue
            if cleaned == "*":
                raise ValueError(
                    "TRUSTED_PROXY_IPS must list explicit IPs or CIDR ranges; wildcard '*' is not allowed"
                )
            net = ipaddress.ip_network(cleaned, strict=False)
            normalized.append(str(net))
        return normalized

    @field_validator("app_timezone")
    @classmethod
    def _valid_timezone(cls, v: str) -> str:
        from zoneinfo import ZoneInfo

        ZoneInfo(v)  # raises if unknown
        return v

    @model_validator(mode="after")
    def _enforce_production_safety(self) -> "Settings":
        secret = self.jwt_secret.get_secret_value()
        if not secret:
            raise ValueError("JWT_SECRET must be set")

        if self.document_storage_provider == "supabase":
            if not self.supabase_url:
                raise ValueError("SUPABASE_URL must be configured when DOCUMENT_STORAGE_PROVIDER is 'supabase'")
            if not self.supabase_service_role_key or not self.supabase_service_role_key.get_secret_value():
                raise ValueError("SUPABASE_SERVICE_ROLE_KEY must be configured when DOCUMENT_STORAGE_PROVIDER is 'supabase'")

        if self.environment == "production":
            if len(secret) < 32:
                raise ValueError("JWT_SECRET must be at least 32 characters in production")
            if "*" in self.cors_origins:
                raise ValueError("CORS_ORIGINS must not contain '*' in production")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]  # values come from the environment
