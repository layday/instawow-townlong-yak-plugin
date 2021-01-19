"An instawow plug-in for Townlong Yak."

from __future__ import annotations

from datetime import datetime, timezone

from instawow.models import Pkg, PkgOptions
import instawow.plugins
from instawow.resolvers import Defn, Strategy, Resolver
from instawow.results import PkgNonexistent, PkgStrategyUnsupported
from typing_extensions import Literal, TypedDict
from yarl import URL


__version__ = '1.0.0'


class TownlongYakApiResponse_Release(TypedDict):
    ch: Literal[0, 1]  # Channel: 0 = retail; 1 = classic
    cv: list[str]  # Compatible game versions, e.g. "9.0.2"
    dl: str  # File download URL


class TownlongYakApiResponse(TypedDict):
    name: str
    summary: str
    author: str
    pi: str  # Persistent project identifier used for updates
    link: str  # Add-on home page
    releases: list[TownlongYakApiResponse_Release]


class TownlongYakResolver(Resolver):
    source = 'townlong-yak'
    name = 'Townlong Yak'
    strategies = frozenset({Strategy.default})

    # Reference: https://www.townlong-yak.com/addons/about/update-api
    api_url = URL('https://www.townlong-yak.com/addons/api/install-bundle')

    @staticmethod
    def get_alias_from_url(value: str) -> str | None:
        url = URL(value)
        if url.host == 'www.townlong-yak.com' and len(url.parts) == 3 and url.parts[1] == 'addons':
            return url.parts[2]

    async def resolve_one(self, defn: Defn, metadata: None) -> Pkg:
        if defn.strategy not in self.strategies:
            raise PkgStrategyUnsupported(defn.strategy)

        async with self.manager.web_client.get(self.api_url / defn.alias) as response:
            if response.status == 404:
                raise PkgNonexistent

            api_metadata: TownlongYakApiResponse = await response.json()

        release = next(
            r for r in api_metadata['releases'] if r['ch'] == self.manager.config.is_classic
        )

        return Pkg(
            source=self.source,
            id=defn.alias,
            slug=defn.alias,
            name=api_metadata['name'],
            description=api_metadata['summary'],
            url=api_metadata['link'],
            download_url=release['dl'],
            date_published=datetime.now(timezone.utc),
            version=URL(release['dl']).name,
            options=PkgOptions(strategy=defn.strategy),
        )


@instawow.plugins.hookimpl
def instawow_add_resolvers() -> tuple[Resolver, ...]:
    return (TownlongYakResolver,)
