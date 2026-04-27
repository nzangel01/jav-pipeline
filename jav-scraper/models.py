from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Actor:
    name: str
    thumb: Optional[str] = None
    role: Optional[str] = None


@dataclass
class Movie:
    id: str = ""
    title: str = ""
    original_title: str = ""
    plot: str = ""
    tagline: str = ""
    year: str = ""
    release_date: str = ""
    runtime: str = ""
    rating: float = 0.0
    votes: int = 0
    mpaa: str = ""
    studio: str = ""
    director: str = ""
    series: str = ""
    actors: list[Actor] = field(default_factory=list)
    genres: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    cover_url: str = ""
    fanart_urls: list[str] = field(default_factory=list)
    trailer: str = ""
    source: str = ""
