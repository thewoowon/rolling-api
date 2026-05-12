from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models._enums import Gender


class ProfileBase(BaseModel):
    display_name: str = Field(min_length=1, max_length=80)
    gender: Gender
    birth_year: int = Field(ge=1900, le=2025)
    region: str | None = Field(default=None, max_length=100)
    job_title: str | None = Field(default=None, max_length=100)
    company_name: str | None = Field(default=None, max_length=100)
    education: str | None = Field(default=None, max_length=100)
    height_cm: int | None = Field(default=None, ge=100, le=250)
    smoking: str | None = Field(default=None, max_length=30)
    drinking: str | None = Field(default=None, max_length=30)
    religion: str | None = Field(default=None, max_length=50)
    relationship_intent: str | None = Field(default=None, max_length=50)
    intro: str | None = Field(default=None, max_length=2000)
    friend_intro: str | None = Field(default=None, max_length=2000)
    profile_image_url: str | None = None


class ProfileUpsert(ProfileBase):
    pass


class ProfileResponse(ProfileBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    verification_level: int
