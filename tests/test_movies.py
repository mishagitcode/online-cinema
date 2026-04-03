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

    activate_response = await client.get(f"/api/v1/auth/activate/{activation_token.token}")
    login_response = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )

    assert activate_response.status_code == 200
    assert login_response.status_code == 200
    return login_response.json()


async def admin_headers(client) -> dict[str, str]:
    login_response = await client.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.com", "password": "Admin123!"},
    )
    tokens = login_response.json()
    return {"Authorization": f"Bearer {tokens['access_token']}"}


async def create_movie_fixture(client, headers: dict[str, str]) -> int:
    certification_response = await client.post(
        "/api/v1/certifications",
        json={"name": "PG-13"},
        headers=headers,
    )
    genre_response = await client.post(
        "/api/v1/genres",
        json={"name": "Sci-Fi"},
        headers=headers,
    )
    star_response = await client.post(
        "/api/v1/stars",
        json={"name": "Keanu Reeves"},
        headers=headers,
    )
    director_response = await client.post(
        "/api/v1/directors",
        json={"name": "Lana Wachowski"},
        headers=headers,
    )

    movie_response = await client.post(
        "/api/v1/movies",
        json={
            "name": "The Matrix",
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
async def test_admin_can_create_movie_and_user_can_search_catalog(client, db_session) -> None:
    headers = await admin_headers(client)
    await create_movie_fixture(client, headers)
    user_tokens = await register_and_login(client, db_session, "catalog-user@example.com")

    response = await client.get(
        "/api/v1/movies",
        params={"search": "Wachowski", "genre_id": 1, "sort_by": "imdb", "sort_order": "desc"},
        headers={"Authorization": f"Bearer {user_tokens['access_token']}"},
    )

    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert response.json()["items"][0]["name"] == "The Matrix"


@pytest.mark.asyncio
async def test_favorites_endpoint_returns_only_saved_movies(client, db_session) -> None:
    headers = await admin_headers(client)
    movie_id = await create_movie_fixture(client, headers)
    user_tokens = await register_and_login(client, db_session, "favorite-user@example.com")
    user_headers = {"Authorization": f"Bearer {user_tokens['access_token']}"}

    favorite_response = await client.post(
        f"/api/v1/movies/{movie_id}/favorite", headers=user_headers
    )
    favorites_list_response = await client.get("/api/v1/favorites", headers=user_headers)

    assert favorite_response.status_code == 200
    assert favorites_list_response.status_code == 200
    assert favorites_list_response.json()["total"] == 1
    assert favorites_list_response.json()["items"][0]["is_favorite"] is True


@pytest.mark.asyncio
async def test_reactions_and_ratings_are_reflected_in_movie_details(client, db_session) -> None:
    headers = await admin_headers(client)
    movie_id = await create_movie_fixture(client, headers)
    user_tokens = await register_and_login(client, db_session, "rating-user@example.com")
    user_headers = {"Authorization": f"Bearer {user_tokens['access_token']}"}

    reaction_response = await client.post(
        f"/api/v1/movies/{movie_id}/reaction",
        json={"reaction": "LIKE"},
        headers=user_headers,
    )
    rating_response = await client.post(
        f"/api/v1/movies/{movie_id}/rating",
        json={"score": 9},
        headers=user_headers,
    )
    details_response = await client.get(f"/api/v1/movies/{movie_id}", headers=user_headers)

    assert reaction_response.status_code == 200
    assert rating_response.status_code == 200
    assert details_response.status_code == 200
    assert details_response.json()["likes_count"] == 1
    assert details_response.json()["average_rating"] == 9.0


@pytest.mark.asyncio
async def test_comment_replies_and_likes_create_notifications(client, db_session) -> None:
    headers = await admin_headers(client)
    movie_id = await create_movie_fixture(client, headers)
    first_user_tokens = await register_and_login(client, db_session, "comment-a@example.com")
    second_user_tokens = await register_and_login(client, db_session, "comment-b@example.com")
    first_headers = {"Authorization": f"Bearer {first_user_tokens['access_token']}"}
    second_headers = {"Authorization": f"Bearer {second_user_tokens['access_token']}"}

    comment_response = await client.post(
        f"/api/v1/movies/{movie_id}/comments",
        json={"text": "Great movie"},
        headers=first_headers,
    )
    comment_id = comment_response.json()["id"]

    reply_response = await client.post(
        f"/api/v1/comments/{comment_id}/reply",
        params={"movie_id": movie_id},
        json={"text": "Agreed"},
        headers=second_headers,
    )
    like_response = await client.post(
        f"/api/v1/comments/{comment_id}/like",
        headers=second_headers,
    )
    notifications_response = await client.get(
        "/api/v1/users/me/notifications", headers=first_headers
    )

    assert reply_response.status_code == 201
    assert like_response.status_code == 200
    assert notifications_response.status_code == 200
    assert len(notifications_response.json()) == 2


@pytest.mark.asyncio
async def test_genres_endpoint_includes_movie_counts(client) -> None:
    headers = await admin_headers(client)
    await create_movie_fixture(client, headers)

    response = await client.get("/api/v1/genres")

    assert response.status_code == 200
    assert response.json()[0]["movie_count"] == 1
