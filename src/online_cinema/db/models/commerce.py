from datetime import datetime
from decimal import Decimal
from enum import Enum

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy import (
    Enum as SqlEnum,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from online_cinema.core.security import utcnow
from online_cinema.db.base import Base


class OrderStatusEnum(str, Enum):
    PENDING = "pending"
    PAID = "paid"
    CANCELED = "canceled"


class PaymentStatusEnum(str, Enum):
    PENDING = "pending"
    SUCCESSFUL = "successful"
    CANCELED = "canceled"
    REFUNDED = "refunded"


class Cart(Base):
    __tablename__ = "carts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True, nullable=False)

    items: Mapped[list["CartItem"]] = relationship(
        back_populates="cart", cascade="all, delete-orphan"
    )


class CartItem(Base):
    __tablename__ = "cart_items"
    __table_args__ = (UniqueConstraint("cart_id", "movie_id", name="uq_cart_item_cart_movie"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    cart_id: Mapped[int] = mapped_column(ForeignKey("carts.id"), nullable=False)
    movie_id: Mapped[int] = mapped_column(ForeignKey("movies.id"), nullable=False)
    added_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )

    cart: Mapped[Cart] = relationship(back_populates="items")


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    status: Mapped[OrderStatusEnum] = mapped_column(
        SqlEnum(OrderStatusEnum),
        default=OrderStatusEnum.PENDING,
        nullable=False,
    )
    total_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)

    items: Mapped[list["OrderItem"]] = relationship(
        back_populates="order", cascade="all, delete-orphan"
    )
    payments: Mapped[list["Payment"]] = relationship(
        back_populates="order", cascade="all, delete-orphan"
    )


class OrderItem(Base):
    __tablename__ = "order_items"
    __table_args__ = (UniqueConstraint("order_id", "movie_id", name="uq_order_item_order_movie"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), nullable=False)
    movie_id: Mapped[int] = mapped_column(ForeignKey("movies.id"), nullable=False)
    price_at_order: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)

    order: Mapped[Order] = relationship(back_populates="items")


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    status: Mapped[PaymentStatusEnum] = mapped_column(
        SqlEnum(PaymentStatusEnum),
        default=PaymentStatusEnum.PENDING,
        nullable=False,
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    external_payment_id: Mapped[str | None] = mapped_column(String(255), nullable=True)

    order: Mapped[Order] = relationship(back_populates="payments")
    items: Mapped[list["PaymentItem"]] = relationship(
        back_populates="payment",
        cascade="all, delete-orphan",
    )


class PaymentItem(Base):
    __tablename__ = "payment_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    payment_id: Mapped[int] = mapped_column(ForeignKey("payments.id"), nullable=False)
    order_item_id: Mapped[int] = mapped_column(ForeignKey("order_items.id"), nullable=False)
    price_at_payment: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)

    payment: Mapped[Payment] = relationship(back_populates="items")


class PurchasedMovie(Base):
    __tablename__ = "purchased_movies"
    __table_args__ = (UniqueConstraint("user_id", "movie_id", name="uq_purchased_user_movie"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    movie_id: Mapped[int] = mapped_column(ForeignKey("movies.id"), nullable=False)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), nullable=False)
    payment_id: Mapped[int] = mapped_column(ForeignKey("payments.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
