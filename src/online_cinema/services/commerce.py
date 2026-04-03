from decimal import Decimal
from typing import Any

import stripe
from fastapi import HTTPException, status
from sqlalchemy import Select, delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from online_cinema.core.config import get_settings
from online_cinema.db.models import (
    Cart,
    CartItem,
    Movie,
    Order,
    OrderItem,
    OrderStatusEnum,
    Payment,
    PaymentItem,
    PaymentStatusEnum,
    PurchasedMovie,
    User,
)
from online_cinema.schemas.auth import MessageResponse
from online_cinema.schemas.commerce import (
    CartItemRead,
    CartRead,
    OrderItemRead,
    OrderRead,
    PaymentRead,
    PurchasedMovieRead,
)
from online_cinema.services.email import email_service


async def _get_or_create_cart(session: AsyncSession, user: User) -> Cart:
    cart = await session.scalar(
        select(Cart).options(selectinload(Cart.items)).where(Cart.user_id == user.id)
    )
    if cart is None:
        cart = Cart(user_id=user.id)
        session.add(cart)
        await session.commit()
        await session.refresh(cart)
        cart = await session.scalar(
            select(Cart).options(selectinload(Cart.items)).where(Cart.user_id == user.id)
        )
    assert cart is not None
    return cart


async def _fetch_movies(session: AsyncSession, movie_ids: list[int]) -> dict[int, Movie]:
    if not movie_ids:
        return {}
    stmt = select(Movie).options(selectinload(Movie.genres)).where(Movie.id.in_(movie_ids))
    movies = list((await session.scalars(stmt)).all())
    return {movie.id: movie for movie in movies}


def _cart_to_schema(cart: Cart, movies_map: dict[int, Movie]) -> CartRead:
    items: list[CartItemRead] = []
    total = Decimal("0.00")
    for item in cart.items:
        movie = movies_map[item.movie_id]
        price = Decimal(movie.price)
        items.append(
            CartItemRead(
                movie_id=movie.id,
                title=movie.name,
                price=price,
                year=movie.year,
                genres=[genre.name for genre in movie.genres],
            )
        )
        total += price
    return CartRead(id=cart.id, items=items, total_amount=total)


def _order_to_schema(order: Order, movies_map: dict[int, Movie]) -> OrderRead:
    items = [
        OrderItemRead(
            movie_id=item.movie_id,
            title=movies_map[item.movie_id].name,
            price_at_order=Decimal(item.price_at_order),
        )
        for item in order.items
    ]
    return OrderRead(
        id=order.id,
        created_at=order.created_at,
        status=order.status,
        total_amount=Decimal(order.total_amount),
        items=items,
    )


def _payment_to_schema(payment: Payment, checkout_url: str | None = None) -> PaymentRead:
    return PaymentRead(
        id=payment.id,
        order_id=payment.order_id,
        created_at=payment.created_at,
        status=payment.status,
        amount=Decimal(payment.amount),
        external_payment_id=payment.external_payment_id,
        checkout_url=checkout_url,
    )


async def get_cart(session: AsyncSession, user: User) -> CartRead:
    cart = await _get_or_create_cart(session, user)
    movies_map = await _fetch_movies(session, [item.movie_id for item in cart.items])
    return _cart_to_schema(cart, movies_map)


async def add_movie_to_cart(session: AsyncSession, user: User, movie_id: int) -> MessageResponse:
    movie = await session.scalar(select(Movie).where(Movie.id == movie_id))
    if movie is None or not movie.is_available:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Movie is unavailable.")

    purchased = await session.scalar(
        select(PurchasedMovie).where(
            PurchasedMovie.user_id == user.id,
            PurchasedMovie.movie_id == movie_id,
        )
    )
    if purchased is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Movie already purchased."
        )

    cart = await _get_or_create_cart(session, user)
    existing_item = await session.scalar(
        select(CartItem).where(CartItem.cart_id == cart.id, CartItem.movie_id == movie_id)
    )
    if existing_item is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Movie already exists in cart."
        )

    session.add(CartItem(cart_id=cart.id, movie_id=movie_id))
    await session.commit()
    return MessageResponse(message="Movie added to cart.")


async def remove_movie_from_cart(
    session: AsyncSession, user: User, movie_id: int
) -> MessageResponse:
    cart = await _get_or_create_cart(session, user)
    item = await session.scalar(
        select(CartItem).where(CartItem.cart_id == cart.id, CartItem.movie_id == movie_id)
    )
    if item is not None:
        await session.delete(item)
        await session.commit()
    return MessageResponse(message="Movie removed from cart.")


async def clear_cart(session: AsyncSession, user: User) -> MessageResponse:
    cart = await _get_or_create_cart(session, user)
    await session.execute(delete(CartItem).where(CartItem.cart_id == cart.id))
    await session.commit()
    return MessageResponse(message="Cart cleared.")


async def list_all_carts(session: AsyncSession, user_id: int | None = None) -> list[CartRead]:
    stmt: Select[Any] = select(Cart).options(selectinload(Cart.items)).order_by(Cart.id)
    if user_id is not None:
        stmt = stmt.where(Cart.user_id == user_id)
    carts = list((await session.scalars(stmt)).all())
    movie_ids = [item.movie_id for cart in carts for item in cart.items]
    movies_map = await _fetch_movies(session, movie_ids)
    return [_cart_to_schema(cart, movies_map) for cart in carts]


async def create_order_from_cart(session: AsyncSession, user: User) -> OrderRead:
    cart = await _get_or_create_cart(session, user)
    if not cart.items:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cart is empty.")

    movies_map = await _fetch_movies(session, [item.movie_id for item in cart.items])
    movie_ids = list(movies_map)

    purchased_ids = set(
        (
            await session.scalars(
                select(PurchasedMovie.movie_id).where(
                    PurchasedMovie.user_id == user.id,
                    PurchasedMovie.movie_id.in_(movie_ids),
                )
            )
        ).all()
    )
    pending_ids = set(
        (
            await session.scalars(
                select(OrderItem.movie_id)
                .join(Order)
                .where(
                    Order.user_id == user.id,
                    Order.status == OrderStatusEnum.PENDING,
                    OrderItem.movie_id.in_(movie_ids),
                )
            )
        ).all()
    )

    valid_items = [
        item
        for item in cart.items
        if item.movie_id in movies_map
        and movies_map[item.movie_id].is_available
        and item.movie_id not in purchased_ids
        and item.movie_id not in pending_ids
    ]
    if not valid_items:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No cart items are available for ordering.",
        )

    total_amount = sum(Decimal(movies_map[item.movie_id].price) for item in valid_items)
    order = Order(user_id=user.id, total_amount=total_amount)
    session.add(order)
    await session.flush()

    for item in valid_items:
        session.add(
            OrderItem(
                order_id=order.id,
                movie_id=item.movie_id,
                price_at_order=Decimal(movies_map[item.movie_id].price),
            )
        )

    for item in list(cart.items):
        await session.delete(item)

    await session.commit()
    created_order = await session.scalar(
        select(Order).options(selectinload(Order.items)).where(Order.id == order.id)
    )
    assert created_order is not None
    return _order_to_schema(created_order, movies_map)


async def list_user_orders(session: AsyncSession, user: User) -> list[OrderRead]:
    orders = list(
        (
            await session.scalars(
                select(Order)
                .options(selectinload(Order.items))
                .where(Order.user_id == user.id)
                .order_by(Order.created_at.desc())
            )
        ).all()
    )
    movie_ids = [item.movie_id for order in orders for item in order.items]
    movies_map = await _fetch_movies(session, movie_ids)
    return [_order_to_schema(order, movies_map) for order in orders]


async def list_all_orders(
    session: AsyncSession,
    *,
    user_id: int | None,
    status_filter: OrderStatusEnum | None,
) -> list[OrderRead]:
    stmt: Select[Any] = (
        select(Order).options(selectinload(Order.items)).order_by(Order.created_at.desc())
    )
    if user_id is not None:
        stmt = stmt.where(Order.user_id == user_id)
    if status_filter is not None:
        stmt = stmt.where(Order.status == status_filter)
    orders = list((await session.scalars(stmt)).all())
    movie_ids = [item.movie_id for order in orders for item in order.items]
    movies_map = await _fetch_movies(session, movie_ids)
    return [_order_to_schema(order, movies_map) for order in orders]


async def cancel_order(session: AsyncSession, user: User, order_id: int) -> MessageResponse:
    order = await session.scalar(
        select(Order).where(Order.id == order_id, Order.user_id == user.id)
    )
    if order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found.")
    if order.status == OrderStatusEnum.PAID:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Paid orders require a refund."
        )
    order.status = OrderStatusEnum.CANCELED
    await session.commit()
    return MessageResponse(message="Order canceled.")


async def _revalidate_order_total(session: AsyncSession, order: Order) -> Decimal:
    movie_ids = [item.movie_id for item in order.items]
    movies_map = await _fetch_movies(session, movie_ids)
    total = Decimal("0.00")
    for item in order.items:
        current_price = Decimal(movies_map[item.movie_id].price)
        item.price_at_order = current_price
        total += current_price
    order.total_amount = total
    return total


async def _finalize_successful_payment(session: AsyncSession, payment: Payment) -> None:
    order = await session.scalar(
        select(Order).options(selectinload(Order.items)).where(Order.id == payment.order_id)
    )
    if order is None:
        return

    order.status = OrderStatusEnum.PAID
    payment.status = PaymentStatusEnum.SUCCESSFUL

    for item in order.items:
        existing = await session.scalar(
            select(PurchasedMovie).where(
                PurchasedMovie.user_id == order.user_id,
                PurchasedMovie.movie_id == item.movie_id,
            )
        )
        if existing is None:
            session.add(
                PurchasedMovie(
                    user_id=order.user_id,
                    movie_id=item.movie_id,
                    order_id=order.id,
                    payment_id=payment.id,
                )
            )

    user = await session.scalar(select(User).where(User.id == order.user_id))
    if user is not None:
        await email_service.send_email(
            recipient=user.email,
            subject="Payment successful",
            body=f"Your payment for order #{order.id} was successful.",
        )


async def create_payment(session: AsyncSession, user: User, order_id: int) -> PaymentRead:
    order = await session.scalar(
        select(Order)
        .options(selectinload(Order.items))
        .where(Order.id == order_id, Order.user_id == user.id)
    )
    if order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found.")
    if order.status != OrderStatusEnum.PENDING:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Order is not pending.")

    total_amount = await _revalidate_order_total(session, order)
    payment = Payment(
        user_id=user.id, order_id=order.id, amount=total_amount, status=PaymentStatusEnum.PENDING
    )
    session.add(payment)
    await session.flush()

    for order_item in order.items:
        session.add(
            PaymentItem(
                payment_id=payment.id,
                order_item_id=order_item.id,
                price_at_payment=Decimal(order_item.price_at_order),
            )
        )

    settings = get_settings()
    checkout_url: str | None = None

    if settings.payment_provider == "stripe" and settings.stripe_api_key:
        stripe.api_key = settings.stripe_api_key
        movies_map = await _fetch_movies(session, [item.movie_id for item in order.items])
        checkout_session = stripe.checkout.Session.create(
            mode="payment",
            success_url=f"{settings.frontend_base_url}/payments/success",
            cancel_url=f"{settings.frontend_base_url}/payments/cancel",
            line_items=[
                {
                    "price_data": {
                        "currency": "usd",
                        "product_data": {"name": movies_map[item.movie_id].name},
                        "unit_amount": int(Decimal(item.price_at_order) * 100),
                    },
                    "quantity": 1,
                }
                for item in order.items
            ],
        )
        payment.external_payment_id = checkout_session["id"]
        checkout_url = checkout_session["url"]
    else:
        payment.external_payment_id = f"fake_{payment.id}"
        await _finalize_successful_payment(session, payment)

    await session.commit()
    return _payment_to_schema(payment, checkout_url=checkout_url)


async def list_user_payments(session: AsyncSession, user: User) -> list[PaymentRead]:
    payments = list(
        (
            await session.scalars(
                select(Payment)
                .where(Payment.user_id == user.id)
                .order_by(Payment.created_at.desc())
            )
        ).all()
    )
    return [_payment_to_schema(payment) for payment in payments]


async def list_all_payments(
    session: AsyncSession,
    *,
    user_id: int | None,
    status_filter: PaymentStatusEnum | None,
) -> list[PaymentRead]:
    stmt: Select[Any] = select(Payment).order_by(Payment.created_at.desc())
    if user_id is not None:
        stmt = stmt.where(Payment.user_id == user_id)
    if status_filter is not None:
        stmt = stmt.where(Payment.status == status_filter)
    payments = list((await session.scalars(stmt)).all())
    return [_payment_to_schema(payment) for payment in payments]


async def refund_payment(session: AsyncSession, user: User, payment_id: int) -> MessageResponse:
    payment = await session.scalar(
        select(Payment).where(Payment.id == payment_id, Payment.user_id == user.id)
    )
    if payment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment not found.")
    if payment.status != PaymentStatusEnum.SUCCESSFUL:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Payment cannot be refunded."
        )

    payment.status = PaymentStatusEnum.REFUNDED
    order = await session.scalar(select(Order).where(Order.id == payment.order_id))
    if order is not None:
        order.status = OrderStatusEnum.CANCELED
    await session.execute(delete(PurchasedMovie).where(PurchasedMovie.payment_id == payment.id))
    await session.commit()
    return MessageResponse(message="Payment refunded.")


async def list_purchased_movies(session: AsyncSession, user: User) -> list[PurchasedMovieRead]:
    purchases = list(
        (
            await session.scalars(
                select(PurchasedMovie)
                .where(PurchasedMovie.user_id == user.id)
                .order_by(PurchasedMovie.created_at.desc())
            )
        ).all()
    )
    movies_map = await _fetch_movies(session, [purchase.movie_id for purchase in purchases])
    return [
        PurchasedMovieRead(
            movie_id=purchase.movie_id,
            title=movies_map[purchase.movie_id].name,
            purchased_at=purchase.created_at,
        )
        for purchase in purchases
    ]


async def handle_stripe_webhook(
    session: AsyncSession,
    payload: bytes,
    signature: str,
) -> MessageResponse:
    settings = get_settings()
    if not settings.stripe_webhook_secret:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Stripe webhook secret is missing."
        )

    event = stripe.Webhook.construct_event(
        payload=payload,
        sig_header=signature,
        secret=settings.stripe_webhook_secret,
    )

    if event["type"] == "checkout.session.completed":
        external_payment_id = event["data"]["object"]["id"]
        payment = await session.scalar(
            select(Payment).where(Payment.external_payment_id == external_payment_id)
        )
        if payment is not None and payment.status == PaymentStatusEnum.PENDING:
            await _finalize_successful_payment(session, payment)
            await session.commit()

    return MessageResponse(message="Webhook processed.")
