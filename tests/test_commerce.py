import pytest
from sqlalchemy import select

from online_cinema.db.models import ActivationToken, User


async def register_and_login(
    client,
    db_session,
    email: str,
    password: str = "Password1!",
) -> dict[str, str]:
    register_response = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password},
    )
    assert register_response.status_code == 201

    activation_token = await db_session.scalar(
        select(ActivationToken).join(User).where(User.email == email)
    )
    assert activation_token is not None

    await client.get(f"/api/v1/auth/activate/{activation_token.token}")
    login_response = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert login_response.status_code == 200
    return login_response.json()


async def admin_headers(client) -> dict[str, str]:
    login_response = await client.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.com", "password": "Admin123!"},
    )
    tokens = login_response.json()
    return {"Authorization": f"Bearer {tokens['access_token']}"}


async def create_movie_fixture(client, headers: dict[str, str], name: str = "The Matrix") -> int:
    certification_response = await client.post(
        "/api/v1/certifications",
        json={"name": f"PG-13-{name}"},
        headers=headers,
    )
    genre_response = await client.post(
        "/api/v1/genres",
        json={"name": f"Sci-Fi-{name}"},
        headers=headers,
    )
    star_response = await client.post(
        "/api/v1/stars",
        json={"name": f"Star-{name}"},
        headers=headers,
    )
    director_response = await client.post(
        "/api/v1/directors",
        json={"name": f"Director-{name}"},
        headers=headers,
    )

    movie_response = await client.post(
        "/api/v1/movies",
        json={
            "name": name,
            "year": 1999,
            "time": 136,
            "imdb": 8.7,
            "votes": 2000000,
            "meta_score": 73,
            "gross": 463.5,
            "description": "A hacker discovers reality is a simulation.",
            "price": 12.99,
            "certification_id": certification_response.json()["id"],
            "genre_ids": [genre_response.json()["id"]],
            "director_ids": [director_response.json()["id"]],
            "star_ids": [star_response.json()["id"]],
        },
        headers=headers,
    )

    assert movie_response.status_code == 201
    return movie_response.json()["id"]


@pytest.mark.asyncio
async def test_cart_add_and_remove_flow(client, db_session) -> None:
    headers = await admin_headers(client)
    movie_id = await create_movie_fixture(client, headers)
    user_tokens = await register_and_login(client, db_session, "cart-user@example.com")
    user_headers = {"Authorization": f"Bearer {user_tokens['access_token']}"}

    add_response = await client.post(f"/api/v1/cart/items/{movie_id}", headers=user_headers)
    cart_response = await client.get("/api/v1/cart", headers=user_headers)
    remove_response = await client.delete(f"/api/v1/cart/items/{movie_id}", headers=user_headers)

    assert add_response.status_code == 200
    assert cart_response.status_code == 200
    assert cart_response.json()["items"][0]["movie_id"] == movie_id
    assert remove_response.status_code == 200


@pytest.mark.asyncio
async def test_order_payment_and_purchased_library_flow(client, db_session) -> None:
    headers = await admin_headers(client)
    movie_id = await create_movie_fixture(client, headers)
    user_tokens = await register_and_login(client, db_session, "buyer@example.com")
    user_headers = {"Authorization": f"Bearer {user_tokens['access_token']}"}

    await client.post(f"/api/v1/cart/items/{movie_id}", headers=user_headers)
    order_response = await client.post("/api/v1/orders", headers=user_headers)
    order_id = order_response.json()["id"]
    payment_response = await client.post(f"/api/v1/orders/{order_id}/pay", headers=user_headers)
    orders_response = await client.get("/api/v1/orders", headers=user_headers)
    purchased_response = await client.get("/api/v1/purchased", headers=user_headers)

    assert order_response.status_code == 201
    assert payment_response.status_code == 200
    assert payment_response.json()["status"] == "successful"
    assert orders_response.json()[0]["status"] == "paid"
    assert purchased_response.json()[0]["movie_id"] == movie_id


@pytest.mark.asyncio
async def test_cannot_repurchase_movie_after_successful_payment(client, db_session) -> None:
    headers = await admin_headers(client)
    movie_id = await create_movie_fixture(client, headers)
    user_tokens = await register_and_login(client, db_session, "repurchase@example.com")
    user_headers = {"Authorization": f"Bearer {user_tokens['access_token']}"}

    await client.post(f"/api/v1/cart/items/{movie_id}", headers=user_headers)
    order_response = await client.post("/api/v1/orders", headers=user_headers)
    await client.post(f"/api/v1/orders/{order_response.json()['id']}/pay", headers=user_headers)

    repurchase_response = await client.post(f"/api/v1/cart/items/{movie_id}", headers=user_headers)

    assert repurchase_response.status_code == 400


@pytest.mark.asyncio
async def test_admin_can_view_carts_orders_and_payments(client, db_session) -> None:
    admin_auth_headers = await admin_headers(client)
    movie_id = await create_movie_fixture(client, admin_auth_headers)
    user_tokens = await register_and_login(client, db_session, "admin-view@example.com")
    user_headers = {"Authorization": f"Bearer {user_tokens['access_token']}"}

    await client.post(f"/api/v1/cart/items/{movie_id}", headers=user_headers)
    order_response = await client.post("/api/v1/orders", headers=user_headers)
    await client.post(f"/api/v1/orders/{order_response.json()['id']}/pay", headers=user_headers)

    carts_response = await client.get("/api/v1/admin/carts", headers=admin_auth_headers)
    orders_response = await client.get("/api/v1/admin/orders", headers=admin_auth_headers)
    payments_response = await client.get("/api/v1/admin/payments", headers=admin_auth_headers)

    assert carts_response.status_code == 200
    assert orders_response.status_code == 200
    assert payments_response.status_code == 200
    assert len(orders_response.json()) == 1
    assert len(payments_response.json()) == 1


@pytest.mark.asyncio
async def test_movie_delete_is_blocked_for_purchased_and_cart_movies(client, db_session) -> None:
    admin_auth_headers = await admin_headers(client)
    purchased_movie_id = await create_movie_fixture(
        client, admin_auth_headers, name="Purchased Movie"
    )
    cart_movie_id = await create_movie_fixture(client, admin_auth_headers, name="Cart Movie")
    user_tokens = await register_and_login(client, db_session, "delete-guard@example.com")
    user_headers = {"Authorization": f"Bearer {user_tokens['access_token']}"}

    await client.post(f"/api/v1/cart/items/{purchased_movie_id}", headers=user_headers)
    order_response = await client.post("/api/v1/orders", headers=user_headers)
    await client.post(f"/api/v1/orders/{order_response.json()['id']}/pay", headers=user_headers)
    await client.post(f"/api/v1/cart/items/{cart_movie_id}", headers=user_headers)

    purchased_delete_response = await client.delete(
        f"/api/v1/movies/{purchased_movie_id}",
        headers=admin_auth_headers,
    )
    cart_delete_response = await client.delete(
        f"/api/v1/movies/{cart_movie_id}",
        headers=admin_auth_headers,
    )
    notifications_response = await client.get(
        "/api/v1/users/me/notifications",
        headers=admin_auth_headers,
    )

    assert purchased_delete_response.status_code == 409
    assert cart_delete_response.status_code == 409
    assert notifications_response.status_code == 200
    assert any("Deletion blocked" in item["message"] for item in notifications_response.json())
