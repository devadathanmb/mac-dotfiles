"""Search results as providers return them and the layout shows them."""

from dataclasses import asdict, dataclass, field
from typing import Any

from .dates import iso_timestamp


@dataclass
class SearchResult:
    title: str
    url: str
    date: str  # ISO date, with time and offset when the provider states them
    text: str  # snippet, highlights, or passages from the page
    providers: list[str] = field(default_factory=list)
    query_ids: list[int] = field(default_factory=list)  # 1-based, into the queries
    page: str | None = None  # saved path of the page `--read` fetched
    page_chars: int = 0
    source: str = ""  # backend that fetched the page

    @classmethod
    def create(
        cls, title: object, url: object, published: object, text: object
    ) -> SearchResult:
        """A result from loosely typed provider fields."""
        return cls(
            title=str(title or "").strip(),
            url=str(url or "").strip(),
            date=iso_timestamp(published),
            text=str(text or "").strip(),
        )

    @classmethod
    def from_json(cls, item: dict[str, Any]) -> SearchResult:
        return cls(
            title=item["title"], url=item["url"], date=item["date"], text=item["text"]
        )

    def to_json(self) -> dict[str, str]:
        """The provider's fields, as cached; layout fields are added later."""
        fields = asdict(self)
        return {key: fields[key] for key in ("title", "url", "date", "text")}
