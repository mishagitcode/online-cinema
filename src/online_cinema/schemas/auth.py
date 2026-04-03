from pydantic import BaseModel, ConfigDict, EmailStr, Field

from online_cinema.db.models import UserGroupEnum


class MessageResponse(BaseModel):
    message: str


class RegistrationRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    first_name: str | None = None
    last_name: str | None = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenPairResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str = Field(min_length=8)


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    new_password: str = Field(min_length=8)


class GroupChangeRequest(BaseModel):
    group: UserGroupEnum


class UserGroupRead(BaseModel):
    id: int
    name: UserGroupEnum

    model_config = ConfigDict(from_attributes=True)
