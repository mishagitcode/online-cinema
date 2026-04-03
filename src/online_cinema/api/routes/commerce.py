from fastapi import APIRouter, Depends, Header, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from online_cinema.api.dependencies.auth import get_current_active_user, require_roles
from online_cinema.db.models import OrderStatusEnum, PaymentStatusEnum, User, UserGroupEnum
from online_cinema.db.session import get_db_session
from online_cinema.schemas.auth import MessageResponse
from online_cinema.schemas.commerce import CartRead, OrderRead, PaymentRead, PurchasedMovieRead
from online_cinema.services.commerce import (
    add_movie_to_cart,
    cancel_order,
    clear_cart,
    create_order_from_cart,
    create_payment,
    get_cart,
    handle_stripe_webhook,
    list_all_carts,
    list_all_orders,
    list_all_payments,
    list_purchased_movies,
    list_user_orders,
    list_user_payments,
    refund_payment,
    remove_movie_from_cart,
)

router = APIRouter()
admin_router = APIRouter()
admin_dependency = Depends(require_roles(UserGroupEnum.ADMIN))


@router.get("/cart", response_model=CartRead)
async def read_cart(
    session: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_active_user),
) -> CartRead:
    return await get_cart(session, user)


@router.post("/cart/items/{movie_id}", response_model=MessageResponse)
async def add_to_cart(
    movie_id: int,
    session: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_active_user),
) -> MessageResponse:
    return await add_movie_to_cart(session, user, movie_id)


@router.delete("/cart/items/{movie_id}", response_model=MessageResponse)
async def remove_from_cart(
    movie_id: int,
    session: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_active_user),
) -> MessageResponse:
    return await remove_movie_from_cart(session, user, movie_id)


@router.delete("/cart", response_model=MessageResponse)
async def clear_current_cart(
    session: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_active_user),
) -> MessageResponse:
    return await clear_cart(session, user)


@router.post("/orders", response_model=OrderRead, status_code=status.HTTP_201_CREATED)
async def create_order(
    session: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_active_user),
) -> OrderRead:
    return await create_order_from_cart(session, user)


@router.get("/orders", response_model=list[OrderRead])
async def get_orders(
    session: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_active_user),
) -> list[OrderRead]:
    return await list_user_orders(session, user)


@router.post("/orders/{order_id}/cancel", response_model=MessageResponse)
async def cancel_user_order(
    order_id: int,
    session: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_active_user),
) -> MessageResponse:
    return await cancel_order(session, user, order_id)


@router.post("/orders/{order_id}/pay", response_model=PaymentRead)
async def pay_for_order(
    order_id: int,
    session: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_active_user),
) -> PaymentRead:
    return await create_payment(session, user, order_id)


@router.get("/payments", response_model=list[PaymentRead])
async def get_payments(
    session: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_active_user),
) -> list[PaymentRead]:
    return await list_user_payments(session, user)


@router.post("/payments/{payment_id}/refund", response_model=MessageResponse)
async def refund_user_payment(
    payment_id: int,
    session: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_active_user),
) -> MessageResponse:
    return await refund_payment(session, user, payment_id)


@router.get("/purchased", response_model=list[PurchasedMovieRead])
async def get_purchased_library(
    session: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_active_user),
) -> list[PurchasedMovieRead]:
    return await list_purchased_movies(session, user)


@router.post("/payments/webhook/stripe", response_model=MessageResponse)
async def stripe_webhook(
    request: Request,
    stripe_signature: str = Header(alias="Stripe-Signature"),
    session: AsyncSession = Depends(get_db_session),
) -> MessageResponse:
    payload = await request.body()
    return await handle_stripe_webhook(session, payload, stripe_signature)


@admin_router.get("/carts", response_model=list[CartRead], dependencies=[admin_dependency])
async def admin_get_carts(
    user_id: int | None = Query(default=None),
    session: AsyncSession = Depends(get_db_session),
) -> list[CartRead]:
    return await list_all_carts(session, user_id=user_id)


@admin_router.get("/orders", response_model=list[OrderRead], dependencies=[admin_dependency])
async def admin_get_orders(
    user_id: int | None = Query(default=None),
    status_filter: OrderStatusEnum | None = Query(default=None, alias="status"),
    session: AsyncSession = Depends(get_db_session),
) -> list[OrderRead]:
    return await list_all_orders(session, user_id=user_id, status_filter=status_filter)


@admin_router.get("/payments", response_model=list[PaymentRead], dependencies=[admin_dependency])
async def admin_get_payments(
    user_id: int | None = Query(default=None),
    status_filter: PaymentStatusEnum | None = Query(default=None, alias="status"),
    session: AsyncSession = Depends(get_db_session),
) -> list[PaymentRead]:
    return await list_all_payments(session, user_id=user_id, status_filter=status_filter)
