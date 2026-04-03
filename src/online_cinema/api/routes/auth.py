from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from online_cinema.api.dependencies.auth import get_current_active_user
from online_cinema.db.models import User
from online_cinema.db.session import get_db_session
from online_cinema.schemas.auth import (
    ChangePasswordRequest,
    ForgotPasswordRequest,
    LoginRequest,
    MessageResponse,
    RefreshRequest,
    RegistrationRequest,
    ResetPasswordRequest,
    TokenPairResponse,
)
from online_cinema.services.auth import (
    activate_account,
    change_password,
    login_user,
    logout_user,
    refresh_access_token,
    register_user,
    request_password_reset,
    resend_activation_token,
    reset_password,
)

router = APIRouter()


@router.post("/register", response_model=MessageResponse, status_code=status.HTTP_201_CREATED)
async def register(
    payload: RegistrationRequest,
    session: AsyncSession = Depends(get_db_session),
) -> MessageResponse:
    return await register_user(session=session, payload=payload)


@router.get("/activate/{token}", response_model=MessageResponse)
async def activate(
    token: str,
    session: AsyncSession = Depends(get_db_session),
) -> MessageResponse:
    return await activate_account(session=session, token=token)


@router.post("/resend-activation", response_model=MessageResponse)
async def resend_activation(
    payload: ForgotPasswordRequest,
    session: AsyncSession = Depends(get_db_session),
) -> MessageResponse:
    return await resend_activation_token(session=session, email=str(payload.email))


@router.post("/login", response_model=TokenPairResponse)
async def login(
    payload: LoginRequest,
    session: AsyncSession = Depends(get_db_session),
) -> TokenPairResponse:
    return await login_user(session=session, payload=payload)


@router.post("/refresh", response_model=TokenPairResponse)
async def refresh(
    payload: RefreshRequest,
    session: AsyncSession = Depends(get_db_session),
) -> TokenPairResponse:
    return await refresh_access_token(session=session, refresh_token=payload.refresh_token)


@router.post("/logout", response_model=MessageResponse)
async def logout(
    payload: RefreshRequest,
    session: AsyncSession = Depends(get_db_session),
    _: User = Depends(get_current_active_user),
) -> MessageResponse:
    return await logout_user(session=session, refresh_token=payload.refresh_token)


@router.post("/change-password", response_model=MessageResponse)
async def password_change(
    payload: ChangePasswordRequest,
    session: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_active_user),
) -> MessageResponse:
    return await change_password(session=session, user=user, payload=payload)


@router.post("/forgot-password", response_model=MessageResponse)
async def forgot_password(
    payload: ForgotPasswordRequest,
    session: AsyncSession = Depends(get_db_session),
) -> MessageResponse:
    return await request_password_reset(session=session, email=str(payload.email))


@router.post("/reset-password/{token}", response_model=MessageResponse)
async def password_reset(
    token: str,
    payload: ResetPasswordRequest,
    session: AsyncSession = Depends(get_db_session),
) -> MessageResponse:
    return await reset_password(session=session, token=token, new_password=payload.new_password)


@router.get("/ping", include_in_schema=False, response_class=Response)
async def auth_ping() -> Response:
    return Response(status_code=status.HTTP_204_NO_CONTENT)
