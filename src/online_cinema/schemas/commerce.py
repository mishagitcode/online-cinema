from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel

from online_cinema.db.models import OrderStatusEnum, PaymentStatusEnum


class CartItemRead(BaseModel):
    movie_id: int
    title: str
    price: Decimal
    year: int
    genres: list[str]


class CartRead(BaseModel):
    id: int
    items: list[CartItemRead]
    total_amount: Decimal


class OrderItemRead(BaseModel):
    movie_id: int
    title: str
    price_at_order: Decimal


class OrderRead(BaseModel):
    id: int
    created_at: datetime
    status: OrderStatusEnum
    total_amount: Decimal
    items: list[OrderItemRead]


class PaymentRead(BaseModel):
    id: int
    order_id: int
    created_at: datetime
    status: PaymentStatusEnum
    amount: Decimal
    external_payment_id: str | None = None
    checkout_url: str | None = None


class CheckoutResponse(BaseModel):
    payment: PaymentRead


class PurchasedMovieRead(BaseModel):
    movie_id: int
    title: str
    purchased_at: datetime
