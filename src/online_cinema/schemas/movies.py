from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from online_cinema.db.models import MovieReactionEnum


class NamedEntityCreate(BaseModel):
    name: str = Field(min_length=1, max_length=150)


class NamedEntityUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=150)


class NamedEntityRead(BaseModel):
    id: int
    name: str

    model_config = ConfigDict(from_attributes=True)


class MovieCreate(BaseModel):
    name: str
    year: int
    time: int
    imdb: float
    votes: int
    meta_score: float | None = None
    gross: Decimal | None = None
    description: str
    price: Decimal
    certification_id: int
    genre_ids: list[int] = []
    director_ids: list[int] = []
    star_ids: list[int] = []
    is_available: bool = True


class MovieUpdate(BaseModel):
    name: str | None = None
    year: int | None = None
    time: int | None = None
    imdb: float | None = None
    votes: int | None = None
    meta_score: float | None = None
    gross: Decimal | None = None
    description: str | None = None
    price: Decimal | None = None
    certification_id: int | None = None
    genre_ids: list[int] | None = None
    director_ids: list[int] | None = None
    star_ids: list[int] | None = None
    is_available: bool | None = None


class MovieRead(BaseModel):
    id: int
    uuid: str
    name: str
    year: int
    time: int
    imdb: float
    votes: int
    meta_score: float | None = None
    gross: Decimal | None = None
    description: str
    price: Decimal
    is_available: bool
    certification: NamedEntityRead
    genres: list[NamedEntityRead]
    directors: list[NamedEntityRead]
    stars: list[NamedEntityRead]
    likes_count: int = 0
    dislikes_count: int = 0
    average_rating: float | None = None
    is_favorite: bool = False


class PaginatedMovies(BaseModel):
    page: int
    size: int
    total: int
    items: list[MovieRead]


class GenreWithCount(BaseModel):
    id: int
    name: str
    movie_count: int


class MovieReactionRequest(BaseModel):
    reaction: MovieReactionEnum


class MovieRatingRequest(BaseModel):
    score: int = Field(ge=1, le=10)


class CommentCreate(BaseModel):
    text: str = Field(min_length=1)


class CommentRead(BaseModel):
    id: int
    user_id: int
    movie_id: int
    parent_id: int | None
    text: str
    created_at: datetime
    updated_at: datetime
    likes_count: int = 0


class NotificationRead(BaseModel):
    id: int
    message: str
    is_read: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
