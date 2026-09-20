"""Small helpers for building provider payloads in tests."""

from datetime import UTC, datetime

from app.providers.search.base import ProviderStatus, SearchProvider, SearchResultItem


def result(url: str, title: str | None = None, snippet: str | None = None) -> SearchResultItem:
    return SearchResultItem(
        title=title,
        url=url,
        snippet=snippet,
        source_engine="test-engine",
        discovered_at=datetime.now(UTC),
        position=1,
        raw={"url": url, "title": title},
    )


class FakeSearchProvider(SearchProvider):
    """Returns canned results; records the queries it was asked to run."""

    name = "fake"

    def __init__(self, results_by_query: dict[str, list[SearchResultItem]] | None = None,
                 default: list[SearchResultItem] | None = None,
                 failing: bool = False):
        self.results_by_query = results_by_query or {}
        self.default = default or []
        self.failing = failing
        self.queries: list[str] = []

    async def search(self, query: str, *, limit: int = 20):
        self.queries.append(query)
        if self.failing:
            from app.core.errors import ProviderError

            raise ProviderError("search backend unavailable")
        return self.results_by_query.get(query, self.default)[:limit]

    async def status(self):
        return ProviderStatus(self.name, True, "fake provider")
