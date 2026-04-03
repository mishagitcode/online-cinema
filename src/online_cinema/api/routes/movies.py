from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from online_cinema.api.dependencies.auth import get_current_active_user, require_roles
from online_cinema.db.models import Certification, Director, Genre, Star, User, UserGroupEnum
from online_cinema.db.session import get_db_session
from online_cinema.schemas.auth import MessageResponse
from online_cinema.schemas.movies import (
    CommentCreate,
    CommentRead,
    GenreWithCount,
    MovieCreate,
    MovieRatingRequest,
    MovieReactionRequest,
    MovieRead,
    MovieUpdate,
    NamedEntityCreate,
    NamedEntityRead,
    NamedEntityUpdate,
    PaginatedMovies,
)
from online_cinema.services.movies import (
    add_comment,
    add_to_favorites,
    create_movie,
    create_named_entity,
    delete_movie,
    delete_named_entity,
    get_movie_details,
    like_comment,
    list_comments,
    list_genres_with_counts,
    list_movies,
    list_named_entities,
    remove_from_favorites,
    set_movie_rating,
    set_movie_reaction,
    update_movie,
    update_named_entity,
)

router = APIRouter()
moderator_dependency = Depends(require_roles(UserGroupEnum.MODERATOR, UserGroupEnum.ADMIN))


@router.get("/movies", response_model=PaginatedMovies)
async def get_movies(
    page: int = Query(default=1, ge=1),
    size: int = Query(default=10, ge=1, le=100),
    search: str | None = Query(default=None),
    year: int | None = Query(default=None),
    imdb_min: float | None = Query(default=None),
    imdb_max: float | None = Query(default=None),
    genre_id: int | None = Query(default=None),
    sort_by: str = Query(default="name"),
    sort_order: str = Query(default="asc"),
    session: AsyncSession = Depends(get_db_session),
    current_user: User | None = Depends(get_current_active_user),
) -> PaginatedMovies:
    return await list_movies(
        session=session,
        page=page,
        size=size,
        search=search,
        year=year,
        imdb_min=imdb_min,
        imdb_max=imdb_max,
        genre_id=genre_id,
        sort_by=sort_by,
        sort_order=sort_order,
        current_user=current_user,
    )


@router.get("/movies/{movie_id}", response_model=MovieRead)
async def get_movie(
    movie_id: int,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_active_user),
) -> MovieRead:
    return await get_movie_details(session, movie_id, current_user)


@router.post(
    "/movies",
    response_model=MovieRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[moderator_dependency],
)
async def create_movie_endpoint(
    payload: MovieCreate,
    session: AsyncSession = Depends(get_db_session),
) -> MovieRead:
    return await create_movie(session, payload)


@router.patch(
    "/movies/{movie_id}",
    response_model=MovieRead,
    dependencies=[moderator_dependency],
)
async def update_movie_endpoint(
    movie_id: int,
    payload: MovieUpdate,
    session: AsyncSession = Depends(get_db_session),
) -> MovieRead:
    return await update_movie(session, movie_id, payload)


@router.delete(
    "/movies/{movie_id}",
    response_model=MessageResponse,
    dependencies=[moderator_dependency],
)
async def delete_movie_endpoint(
    movie_id: int,
    session: AsyncSession = Depends(get_db_session),
) -> MessageResponse:
    return await delete_movie(session, movie_id)


@router.get("/favorites", response_model=PaginatedMovies)
async def get_favorites(
    page: int = Query(default=1, ge=1),
    size: int = Query(default=10, ge=1, le=100),
    search: str | None = Query(default=None),
    year: int | None = Query(default=None),
    imdb_min: float | None = Query(default=None),
    imdb_max: float | None = Query(default=None),
    genre_id: int | None = Query(default=None),
    sort_by: str = Query(default="name"),
    sort_order: str = Query(default="asc"),
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_active_user),
) -> PaginatedMovies:
    return await list_movies(
        session=session,
        page=page,
        size=size,
        search=search,
        year=year,
        imdb_min=imdb_min,
        imdb_max=imdb_max,
        genre_id=genre_id,
        sort_by=sort_by,
        sort_order=sort_order,
        current_user=current_user,
        favorite_only=True,
    )


@router.post("/movies/{movie_id}/favorite", response_model=MessageResponse)
async def favorite_movie(
    movie_id: int,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_active_user),
) -> MessageResponse:
    return await add_to_favorites(session, current_user, movie_id)


@router.delete("/movies/{movie_id}/favorite", response_model=MessageResponse)
async def unfavorite_movie(
    movie_id: int,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_active_user),
) -> MessageResponse:
    return await remove_from_favorites(session, current_user, movie_id)


@router.post("/movies/{movie_id}/reaction", response_model=MessageResponse)
async def react_to_movie(
    movie_id: int,
    payload: MovieReactionRequest,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_active_user),
) -> MessageResponse:
    return await set_movie_reaction(session, current_user, movie_id, payload)


@router.post("/movies/{movie_id}/rating", response_model=MessageResponse)
async def rate_movie(
    movie_id: int,
    payload: MovieRatingRequest,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_active_user),
) -> MessageResponse:
    return await set_movie_rating(session, current_user, movie_id, payload)


@router.get("/movies/{movie_id}/comments", response_model=list[CommentRead])
async def get_movie_comments(
    movie_id: int,
    session: AsyncSession = Depends(get_db_session),
) -> list[CommentRead]:
    return await list_comments(session, movie_id)


@router.post(
    "/movies/{movie_id}/comments",
    response_model=CommentRead,
    status_code=status.HTTP_201_CREATED,
)
async def comment_on_movie(
    movie_id: int,
    payload: CommentCreate,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_active_user),
) -> CommentRead:
    return await add_comment(session, current_user, movie_id, payload)


@router.post(
    "/comments/{comment_id}/reply", response_model=CommentRead, status_code=status.HTTP_201_CREATED
)
async def reply_to_comment(
    comment_id: int,
    movie_id: int,
    payload: CommentCreate,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_active_user),
) -> CommentRead:
    return await add_comment(session, current_user, movie_id, payload, parent_id=comment_id)


@router.post("/comments/{comment_id}/like", response_model=MessageResponse)
async def like_movie_comment(
    comment_id: int,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_active_user),
) -> MessageResponse:
    return await like_comment(session, current_user, comment_id)


@router.get("/genres", response_model=list[GenreWithCount])
async def get_genres(session: AsyncSession = Depends(get_db_session)) -> list[GenreWithCount]:
    return await list_genres_with_counts(session)


@router.get("/certifications", response_model=list[NamedEntityRead])
async def get_certifications(
    session: AsyncSession = Depends(get_db_session),
) -> list[NamedEntityRead]:
    return await list_named_entities(session, Certification)


@router.get("/stars", response_model=list[NamedEntityRead])
async def get_stars(session: AsyncSession = Depends(get_db_session)) -> list[NamedEntityRead]:
    return await list_named_entities(session, Star)


@router.get("/directors", response_model=list[NamedEntityRead])
async def get_directors(session: AsyncSession = Depends(get_db_session)) -> list[NamedEntityRead]:
    return await list_named_entities(session, Director)


@router.post("/genres", response_model=NamedEntityRead, dependencies=[moderator_dependency])
async def create_genre(
    payload: NamedEntityCreate,
    session: AsyncSession = Depends(get_db_session),
) -> NamedEntityRead:
    return await create_named_entity(session, Genre, payload.name)


@router.patch(
    "/genres/{genre_id}", response_model=NamedEntityRead, dependencies=[moderator_dependency]
)
async def update_genre(
    genre_id: int,
    payload: NamedEntityUpdate,
    session: AsyncSession = Depends(get_db_session),
) -> NamedEntityRead:
    return await update_named_entity(session, Genre, genre_id, payload.name)


@router.delete(
    "/genres/{genre_id}", response_model=MessageResponse, dependencies=[moderator_dependency]
)
async def delete_genre(
    genre_id: int,
    session: AsyncSession = Depends(get_db_session),
) -> MessageResponse:
    return await delete_named_entity(session, Genre, genre_id)


@router.post("/certifications", response_model=NamedEntityRead, dependencies=[moderator_dependency])
async def create_certification(
    payload: NamedEntityCreate,
    session: AsyncSession = Depends(get_db_session),
) -> NamedEntityRead:
    return await create_named_entity(session, Certification, payload.name)


@router.post("/stars", response_model=NamedEntityRead, dependencies=[moderator_dependency])
async def create_star(
    payload: NamedEntityCreate,
    session: AsyncSession = Depends(get_db_session),
) -> NamedEntityRead:
    return await create_named_entity(session, Star, payload.name)


@router.post("/directors", response_model=NamedEntityRead, dependencies=[moderator_dependency])
async def create_director(
    payload: NamedEntityCreate,
    session: AsyncSession = Depends(get_db_session),
) -> NamedEntityRead:
    return await create_named_entity(session, Director, payload.name)


@router.patch(
    "/certifications/{entity_id}",
    response_model=NamedEntityRead,
    dependencies=[moderator_dependency],
)
async def update_certification(
    entity_id: int,
    payload: NamedEntityUpdate,
    session: AsyncSession = Depends(get_db_session),
) -> NamedEntityRead:
    return await update_named_entity(session, Certification, entity_id, payload.name)


@router.patch(
    "/stars/{entity_id}", response_model=NamedEntityRead, dependencies=[moderator_dependency]
)
async def update_star(
    entity_id: int,
    payload: NamedEntityUpdate,
    session: AsyncSession = Depends(get_db_session),
) -> NamedEntityRead:
    return await update_named_entity(session, Star, entity_id, payload.name)


@router.patch(
    "/directors/{entity_id}", response_model=NamedEntityRead, dependencies=[moderator_dependency]
)
async def update_director(
    entity_id: int,
    payload: NamedEntityUpdate,
    session: AsyncSession = Depends(get_db_session),
) -> NamedEntityRead:
    return await update_named_entity(session, Director, entity_id, payload.name)


@router.delete(
    "/certifications/{entity_id}",
    response_model=MessageResponse,
    dependencies=[moderator_dependency],
)
async def delete_certification(
    entity_id: int,
    session: AsyncSession = Depends(get_db_session),
) -> MessageResponse:
    return await delete_named_entity(session, Certification, entity_id)


@router.delete(
    "/stars/{entity_id}", response_model=MessageResponse, dependencies=[moderator_dependency]
)
async def delete_star(
    entity_id: int,
    session: AsyncSession = Depends(get_db_session),
) -> MessageResponse:
    return await delete_named_entity(session, Star, entity_id)


@router.delete(
    "/directors/{entity_id}", response_model=MessageResponse, dependencies=[moderator_dependency]
)
async def delete_director(
    entity_id: int,
    session: AsyncSession = Depends(get_db_session),
) -> MessageResponse:
    return await delete_named_entity(session, Director, entity_id)
