from decimal import Decimal
from typing import Any, TypeVar

from fastapi import HTTPException, status
from sqlalchemy import Select, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from online_cinema.db.models import (
    Certification,
    CommentLike,
    Director,
    Favorite,
    Genre,
    Movie,
    MovieComment,
    MovieRating,
    MovieReaction,
    MovieReactionEnum,
    Notification,
    Star,
    User,
)
from online_cinema.db.models.movies import movie_genres
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
    NamedEntityRead,
    NotificationRead,
    PaginatedMovies,
)

MOVIE_RELATIONSHIPS = (
    selectinload(Movie.certification),
    selectinload(Movie.genres),
    selectinload(Movie.directors),
    selectinload(Movie.stars),
    selectinload(Movie.reactions),
    selectinload(Movie.ratings),
)

NamedEntityModel = TypeVar("NamedEntityModel", Genre, Director, Star, Certification)
ManyToManyEntity = TypeVar("ManyToManyEntity", Genre, Director, Star)


def _movie_to_schema(movie: Movie, favorite_movie_ids: set[int]) -> MovieRead:
    likes_count = sum(
        1 for reaction in movie.reactions if reaction.reaction == MovieReactionEnum.LIKE
    )
    dislikes_count = sum(
        1 for reaction in movie.reactions if reaction.reaction == MovieReactionEnum.DISLIKE
    )
    average_rating = None
    if movie.ratings:
        average_rating = round(
            sum(rating.score for rating in movie.ratings) / len(movie.ratings), 2
        )

    return MovieRead(
        id=movie.id,
        uuid=movie.uuid,
        name=movie.name,
        year=movie.year,
        time=movie.time,
        imdb=float(movie.imdb),
        votes=movie.votes,
        meta_score=float(movie.meta_score) if movie.meta_score is not None else None,
        gross=Decimal(movie.gross) if movie.gross is not None else None,
        description=movie.description,
        price=Decimal(movie.price),
        is_available=movie.is_available,
        certification=NamedEntityRead.model_validate(movie.certification),
        genres=[NamedEntityRead.model_validate(item) for item in movie.genres],
        directors=[NamedEntityRead.model_validate(item) for item in movie.directors],
        stars=[NamedEntityRead.model_validate(item) for item in movie.stars],
        likes_count=likes_count,
        dislikes_count=dislikes_count,
        average_rating=average_rating,
        is_favorite=movie.id in favorite_movie_ids,
    )


async def _get_movie_or_404(session: AsyncSession, movie_id: int) -> Movie:
    stmt = select(Movie).options(*MOVIE_RELATIONSHIPS).where(Movie.id == movie_id)
    movie = await session.scalar(stmt)
    if movie is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Movie not found.")
    return movie


async def _get_named_entity_or_404(
    session: AsyncSession,
    model: type[NamedEntityModel],
    entity_id: int,
) -> NamedEntityModel:
    entity = await session.get(model, entity_id)
    if entity is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Entity not found.")
    return entity


async def _resolve_many_to_many(
    session: AsyncSession,
    model: type[ManyToManyEntity],
    entity_ids: list[int],
) -> list[ManyToManyEntity]:
    if not entity_ids:
        return []
    stmt = select(model).where(model.id.in_(entity_ids))
    entities = list((await session.scalars(stmt)).all())
    if len(entities) != len(set(entity_ids)):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="One or more related entities were not found.",
        )
    return entities


async def list_movies(
    session: AsyncSession,
    *,
    page: int,
    size: int,
    search: str | None,
    year: int | None,
    imdb_min: float | None,
    imdb_max: float | None,
    genre_id: int | None,
    sort_by: str,
    sort_order: str,
    current_user: User | None,
    favorite_only: bool = False,
) -> PaginatedMovies:
    stmt: Select[Any] = select(Movie).options(*MOVIE_RELATIONSHIPS).distinct()

    if search:
        search_pattern = f"%{search}%"
        stmt = (
            stmt.outerjoin(Movie.stars)
            .outerjoin(Movie.directors)
            .where(
                or_(
                    Movie.name.ilike(search_pattern),
                    Movie.description.ilike(search_pattern),
                    Star.name.ilike(search_pattern),
                    Director.name.ilike(search_pattern),
                )
            )
        )

    if year is not None:
        stmt = stmt.where(Movie.year == year)
    if imdb_min is not None:
        stmt = stmt.where(Movie.imdb >= imdb_min)
    if imdb_max is not None:
        stmt = stmt.where(Movie.imdb <= imdb_max)
    if genre_id is not None:
        stmt = stmt.join(Movie.genres).where(Genre.id == genre_id)
    if favorite_only:
        if current_user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required."
            )
        stmt = stmt.join(Favorite).where(Favorite.user_id == current_user.id)

    sort_mapping = {
        "price": Movie.price,
        "release_date": Movie.year,
        "popularity": Movie.votes,
        "imdb": Movie.imdb,
    }
    sort_column = sort_mapping.get(sort_by, Movie.name)
    stmt = stmt.order_by(sort_column.desc() if sort_order == "desc" else sort_column.asc())

    total = await session.scalar(select(func.count()).select_from(stmt.order_by(None).subquery()))
    movies = list(
        (await session.scalars(stmt.offset((page - 1) * size).limit(size))).unique().all()
    )

    favorite_movie_ids: set[int] = set()
    if current_user is not None and movies:
        favorite_stmt = select(Favorite.movie_id).where(
            Favorite.user_id == current_user.id,
            Favorite.movie_id.in_([movie.id for movie in movies]),
        )
        favorite_movie_ids = set((await session.scalars(favorite_stmt)).all())

    return PaginatedMovies(
        page=page,
        size=size,
        total=total or 0,
        items=[_movie_to_schema(movie, favorite_movie_ids) for movie in movies],
    )


async def get_movie_details(
    session: AsyncSession,
    movie_id: int,
    current_user: User | None,
) -> MovieRead:
    movie = await _get_movie_or_404(session, movie_id)
    favorite_movie_ids: set[int] = set()
    if current_user is not None:
        favorite = await session.scalar(
            select(Favorite).where(
                Favorite.user_id == current_user.id, Favorite.movie_id == movie_id
            )
        )
        if favorite is not None:
            favorite_movie_ids.add(movie_id)
    return _movie_to_schema(movie, favorite_movie_ids)


async def create_movie(session: AsyncSession, payload: MovieCreate) -> MovieRead:
    certification = await _get_named_entity_or_404(session, Certification, payload.certification_id)
    genres = await _resolve_many_to_many(session, Genre, payload.genre_ids)
    directors = await _resolve_many_to_many(session, Director, payload.director_ids)
    stars = await _resolve_many_to_many(session, Star, payload.star_ids)

    movie = Movie(
        name=payload.name,
        year=payload.year,
        time=payload.time,
        imdb=payload.imdb,
        votes=payload.votes,
        meta_score=payload.meta_score,
        gross=payload.gross,
        description=payload.description,
        price=payload.price,
        is_available=payload.is_available,
        certification_id=certification.id,
        genres=list(genres),
        directors=list(directors),
        stars=list(stars),
    )
    session.add(movie)
    await session.commit()
    return await get_movie_details(session, movie.id, current_user=None)


async def update_movie(session: AsyncSession, movie_id: int, payload: MovieUpdate) -> MovieRead:
    movie = await _get_movie_or_404(session, movie_id)
    updates = payload.model_dump(exclude_unset=True)

    if "certification_id" in updates:
        certification = await _get_named_entity_or_404(
            session, Certification, updates["certification_id"]
        )
        movie.certification_id = certification.id

    if "genre_ids" in updates:
        movie.genres = list(await _resolve_many_to_many(session, Genre, updates["genre_ids"] or []))
    if "director_ids" in updates:
        movie.directors = list(
            await _resolve_many_to_many(session, Director, updates["director_ids"] or [])
        )
    if "star_ids" in updates:
        movie.stars = list(await _resolve_many_to_many(session, Star, updates["star_ids"] or []))

    for field_name in (
        "name",
        "year",
        "time",
        "imdb",
        "votes",
        "meta_score",
        "gross",
        "description",
        "price",
        "is_available",
    ):
        if field_name in updates:
            setattr(movie, field_name, updates[field_name])

    await session.commit()
    return await get_movie_details(session, movie.id, current_user=None)


async def delete_movie(session: AsyncSession, movie_id: int) -> MessageResponse:
    movie = await session.get(Movie, movie_id)
    if movie is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Movie not found.")

    await session.delete(movie)
    await session.commit()
    return MessageResponse(message="Movie deleted.")


async def create_named_entity(
    session: AsyncSession,
    model: type[NamedEntityModel],
    name: str,
) -> NamedEntityRead:
    entity = model(name=name)
    session.add(entity)
    await session.commit()
    await session.refresh(entity)
    return NamedEntityRead.model_validate(entity)


async def list_named_entities(
    session: AsyncSession,
    model: type[NamedEntityModel],
) -> list[NamedEntityRead]:
    entities = list((await session.scalars(select(model).order_by(model.name))).all())
    return [NamedEntityRead.model_validate(entity) for entity in entities]


async def update_named_entity(
    session: AsyncSession,
    model: type[NamedEntityModel],
    entity_id: int,
    name: str,
) -> NamedEntityRead:
    entity = await _get_named_entity_or_404(session, model, entity_id)
    entity.name = name
    await session.commit()
    return NamedEntityRead.model_validate(entity)


async def delete_named_entity(
    session: AsyncSession,
    model: type[NamedEntityModel],
    entity_id: int,
) -> MessageResponse:
    entity = await _get_named_entity_or_404(session, model, entity_id)
    await session.delete(entity)
    await session.commit()
    return MessageResponse(message="Entity deleted.")


async def list_genres_with_counts(session: AsyncSession) -> list[GenreWithCount]:
    stmt = (
        select(Genre.id, Genre.name, func.count(movie_genres.c.movie_id).label("movie_count"))
        .outerjoin(movie_genres, Genre.id == movie_genres.c.genre_id)
        .group_by(Genre.id, Genre.name)
        .order_by(Genre.name)
    )
    rows = (await session.execute(stmt)).all()
    return [GenreWithCount(id=row.id, name=row.name, movie_count=row.movie_count) for row in rows]


async def add_to_favorites(session: AsyncSession, user: User, movie_id: int) -> MessageResponse:
    await _get_movie_or_404(session, movie_id)
    favorite = await session.scalar(
        select(Favorite).where(Favorite.user_id == user.id, Favorite.movie_id == movie_id)
    )
    if favorite is None:
        session.add(Favorite(user_id=user.id, movie_id=movie_id))
        await session.commit()
    return MessageResponse(message="Movie added to favorites.")


async def remove_from_favorites(
    session: AsyncSession, user: User, movie_id: int
) -> MessageResponse:
    favorite = await session.scalar(
        select(Favorite).where(Favorite.user_id == user.id, Favorite.movie_id == movie_id)
    )
    if favorite is not None:
        await session.delete(favorite)
        await session.commit()
    return MessageResponse(message="Movie removed from favorites.")


async def set_movie_reaction(
    session: AsyncSession,
    user: User,
    movie_id: int,
    payload: MovieReactionRequest,
) -> MessageResponse:
    await _get_movie_or_404(session, movie_id)
    reaction = await session.scalar(
        select(MovieReaction).where(
            MovieReaction.user_id == user.id, MovieReaction.movie_id == movie_id
        )
    )
    if reaction is None:
        session.add(MovieReaction(user_id=user.id, movie_id=movie_id, reaction=payload.reaction))
    else:
        reaction.reaction = payload.reaction
    await session.commit()
    return MessageResponse(message="Movie reaction saved.")


async def set_movie_rating(
    session: AsyncSession,
    user: User,
    movie_id: int,
    payload: MovieRatingRequest,
) -> MessageResponse:
    await _get_movie_or_404(session, movie_id)
    rating = await session.scalar(
        select(MovieRating).where(MovieRating.user_id == user.id, MovieRating.movie_id == movie_id)
    )
    if rating is None:
        session.add(MovieRating(user_id=user.id, movie_id=movie_id, score=payload.score))
    else:
        rating.score = payload.score
    await session.commit()
    return MessageResponse(message="Movie rating saved.")


async def list_comments(session: AsyncSession, movie_id: int) -> list[CommentRead]:
    await _get_movie_or_404(session, movie_id)
    stmt = (
        select(MovieComment)
        .options(selectinload(MovieComment.likes))
        .where(MovieComment.movie_id == movie_id)
        .order_by(MovieComment.created_at.asc())
    )
    comments = list((await session.scalars(stmt)).all())
    return [
        CommentRead(
            id=comment.id,
            user_id=comment.user_id,
            movie_id=comment.movie_id,
            parent_id=comment.parent_id,
            text=comment.text,
            created_at=comment.created_at,
            updated_at=comment.updated_at,
            likes_count=len(comment.likes),
        )
        for comment in comments
    ]


async def add_comment(
    session: AsyncSession,
    user: User,
    movie_id: int,
    payload: CommentCreate,
    *,
    parent_id: int | None = None,
) -> CommentRead:
    await _get_movie_or_404(session, movie_id)

    parent_comment = None
    if parent_id is not None:
        parent_comment = await session.get(MovieComment, parent_id)
        if parent_comment is None or parent_comment.movie_id != movie_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Parent comment not found."
            )

    comment = MovieComment(
        user_id=user.id, movie_id=movie_id, parent_id=parent_id, text=payload.text
    )
    session.add(comment)
    await session.flush()

    if parent_comment is not None and parent_comment.user_id != user.id:
        session.add(
            Notification(
                user_id=parent_comment.user_id,
                message=f"Your comment received a reply on movie {movie_id}.",
            )
        )

    await session.commit()
    return CommentRead(
        id=comment.id,
        user_id=comment.user_id,
        movie_id=comment.movie_id,
        parent_id=comment.parent_id,
        text=comment.text,
        created_at=comment.created_at,
        updated_at=comment.updated_at,
        likes_count=0,
    )


async def like_comment(session: AsyncSession, user: User, comment_id: int) -> MessageResponse:
    comment = await session.scalar(
        select(MovieComment)
        .options(selectinload(MovieComment.likes))
        .where(MovieComment.id == comment_id)
    )
    if comment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Comment not found.")

    existing_like = await session.scalar(
        select(CommentLike).where(
            CommentLike.user_id == user.id, CommentLike.comment_id == comment_id
        )
    )
    if existing_like is None:
        session.add(CommentLike(user_id=user.id, comment_id=comment_id))
        if comment.user_id != user.id:
            session.add(
                Notification(
                    user_id=comment.user_id,
                    message=f"Your comment received a like on movie {comment.movie_id}.",
                )
            )
        await session.commit()

    return MessageResponse(message="Comment liked.")


async def list_notifications(session: AsyncSession, user: User) -> list[NotificationRead]:
    notifications = list(
        (
            await session.scalars(
                select(Notification)
                .where(Notification.user_id == user.id)
                .order_by(Notification.created_at.desc())
            )
        ).all()
    )
    return [NotificationRead.model_validate(notification) for notification in notifications]


async def mark_notification_read(
    session: AsyncSession,
    user: User,
    notification_id: int,
) -> MessageResponse:
    notification = await session.scalar(
        select(Notification).where(
            Notification.id == notification_id,
            Notification.user_id == user.id,
        )
    )
    if notification is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found.")
    notification.is_read = True
    await session.commit()
    return MessageResponse(message="Notification marked as read.")
