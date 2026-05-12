from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field

from app.models._enums import UserRole


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    role: UserRole = UserRole.PARTICIPANT


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1)


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class MeResponse(BaseModel):
    id: UUID
    email: str | None
    phone: str | None
    role: UserRole
    status: str
    last_login_at: datetime | None
    created_at: datetime
