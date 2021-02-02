"An instawow plug-in for Townlong Yak."

from __future__ import annotations

from datetime import datetime, timezone

from instawow.manager import cache_response
from instawow.models import Pkg, PkgOptions
import instawow.plugins
from instawow.resolvers import Defn, Strategy, Resolver
from instawow.results import PkgNonexistent, PkgStrategyUnsupported, PkgFileUnavailable
from typing_extensions import Literal, TypedDict
from yarl import URL


__version__ = '1.1.0'


class WowUpHubAddon(TypedDict):
    id: int
    repository: str  # Home page URL
    repository_name: str  # Add-on name
    source: str
    description: str  # Includes HTML
    homepage: str  # Source URL
    image_url: str
    owner_image_url: str
    owner_name: str  # Author
    total_download_count: int  # Always 0 for Townlong Yak
    funding_links: list[str]
    releases: list[WowUpHubAddon_Release]


class WowUpHubAddon_Release(TypedDict):
    body: str  # Changelog?  Includes HTML
    download_count: int  # Always 0 for Townlong Yak
    download_url: str
    external_id: str  # Source ID
    game_version: str  # TOC-style game version, e.g. "90002" for 9.0.2
    id: int
    name: str  # Cf. GH API
    prerelease: bool
    published_at: str
    tag_name: str  # Cf. GH API
    url: str  # Same as download URL for TY
    game_type: Literal['retail', 'classic']


class WowUpHubAddons(TypedDict):
    addons: list[WowUpHubAddon]


class TownlongYakResolver(Resolver):
    source = 'townlong-yak'
    name = 'Townlong Yak (via WowUp.Hub)'
    strategies = frozenset({Strategy.default})

    _api_url = 'https://hub.dev.wowup.io/addons/author/foxlit'

    @staticmethod
    def get_alias_from_url(value: str) -> str | None:
        url = URL(value)
        if url.host == 'www.townlong-yak.com' and len(url.parts) > 2 and url.parts[1] == 'addons':
            return url.parts[2]

    async def _synchronise(self) -> dict[str, WowUpHubAddon]:
        async with self.manager.locks['load Townlong Yak catalogue']:
            foxlit_addons: WowUpHubAddons = await cache_response(
                self.manager,
                self._api_url,
                {'minutes': 15},
                label=f'Synchronising {self.name} catalogue',
            )
            return {URL(a['repository']).name: a for a in foxlit_addons['addons']}

    async def resolve_one(self, defn: Defn, metadata: None) -> Pkg:
        if defn.strategy not in self.strategies:
            raise PkgStrategyUnsupported(defn.strategy)

        addons = await self._synchronise()
        try:
            addon = addons[defn.alias]
        except KeyError:
            raise PkgNonexistent

        try:
            file = next(
                r
                for r in addon['releases']
                if not r['prerelease'] and r['game_type'] == self.manager.config.game_flavour
            )
        except StopIteration:
            raise PkgFileUnavailable

        return Pkg(
            source=self.source,
            id=defn.alias,
            slug=defn.alias,
            name=addon['repository_name'],
            description=addon['description'],
            url=addon['repository'],
            download_url=file['download_url'],
            date_published=datetime.now(timezone.utc),
            version=file['tag_name'],
            options=PkgOptions(strategy=defn.strategy),
        )


@instawow.plugins.hookimpl
def instawow_add_resolvers() -> tuple[Resolver, ...]:
    return (TownlongYakResolver,)
