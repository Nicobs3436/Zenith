from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, computed_field, field_validator

MIN_USER_AGE = 18


def normalize_email(value: str) -> str:
    # Emails sin distinguir mayusculas: "Juan@x.com" y "juan@x.com" son la misma cuenta.
    return str(value).strip().lower()


class UserCreate(BaseModel):
    email: EmailStr
    username: str = Field(min_length=3, max_length=50, pattern=r"^[a-zA-Z0-9_]+$")
    password: str = Field(min_length=8, max_length=128)
    # Consentimientos obligatorios: se guardan con fecha para poder demostrarlos (RGPD).
    accepted_terms: Literal[True] = Field(
        description="Acepta privacidad, terminos y aviso medico. Debe ser true.",
    )
    adult_confirmed: Literal[True] = Field(
        description=f"Confirma tener {MIN_USER_AGE} anos o mas. Debe ser true.",
    )

    @field_validator("email", mode="after")
    @classmethod
    def lower_email(cls, value: str) -> str:
        return normalize_email(value)


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: EmailStr
    username: str
    is_active: bool
    email_verified_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    @computed_field
    @property
    def email_verified(self) -> bool:
        return self.email_verified_at is not None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)

    @field_validator("email", mode="after")
    @classmethod
    def lower_email(cls, value: str) -> str:
        return normalize_email(value)


class TokenResponse(BaseModel):
    access_token: str
    # En web va en cookie httpOnly y aqui llega null; en movil se devuelve para SecureStore.
    refresh_token: str | None = None
    token_type: Literal["bearer"] = "bearer"


class RefreshTokenRequest(BaseModel):
    refresh_token: str | None = Field(default=None, min_length=1, max_length=512)


class LogoutRequest(BaseModel):
    refresh_token: str | None = Field(default=None, min_length=1, max_length=512)


class PasswordResetRequest(BaseModel):
    email: EmailStr

    @field_validator("email", mode="after")
    @classmethod
    def lower_email(cls, value: str) -> str:
        return normalize_email(value)


class PasswordResetConfirm(BaseModel):
    token: str = Field(min_length=10, max_length=256)
    new_password: str = Field(min_length=8, max_length=128)


class EmailVerificationConfirm(BaseModel):
    token: str = Field(min_length=10, max_length=256)


class AccountDeleteRequest(BaseModel):
    password: str = Field(min_length=1, max_length=128)
