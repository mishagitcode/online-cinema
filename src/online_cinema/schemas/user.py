from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, EmailStr

from online_cinema.db.models import GenderEnum
from online_cinema.schemas.auth import UserGroupRead


class UserProfileRead(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    avatar: str | None = None
    gender: GenderEnum | None = None
    date_of_birth: date | None = None
    info: str | None = None

    model_config = ConfigDict(from_attributes=True)


class UserProfileUpdate(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    avatar: str | None = None
    gender: GenderEnum | None = None
    date_of_birth: date | None = None
    info: str | None = None


class UserRead(BaseModel):
    id: int
    email: EmailStr
    is_active: bool
    created_at: datetime
    updated_at: datetime
    group: UserGroupRead
    profile: UserProfileRead | None = None

    model_config = ConfigDict(from_attributes=True)
