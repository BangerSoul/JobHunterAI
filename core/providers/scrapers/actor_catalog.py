from typing import Any, Dict, List, Set

from pydantic import BaseModel


class ActorMetadata(BaseModel):
    """Metadata about a specific Apify actor."""

    id: str
    name: str
    supported_sources: List[str]
    supported_countries: List[str]
    capabilities: Set[str]
    estimated_usd_per_1k: float = 2.0  # Default heuristic cost


# Canonical catalog of Apify actors supported by JobHunterAI
APIFY_ACTOR_CATALOG: Dict[str, ActorMetadata] = {
    "johnvc/Google-Jobs-Scraper": ActorMetadata(
        id="johnvc/Google-Jobs-Scraper",
        name="Google Jobs Scraper",
        supported_sources=["Google Jobs"],
        supported_countries=["global"],
        capabilities={"keyword_search", "location_search", "pagination"},
        estimated_usd_per_1k=3.50,
    ),
    "curious_coder/linkedin-jobs-scraper": ActorMetadata(
        id="curious_coder/linkedin-jobs-scraper",
        name="LinkedIn Jobs Scraper",
        supported_sources=["LinkedIn"],
        supported_countries=["global"],
        capabilities={"keyword_search", "location_search", "pagination"},
        estimated_usd_per_1k=5.00,
    ),
}


def get_actor_metadata(actor_id: str) -> ActorMetadata:
    """Retrieves metadata for a specific actor ID."""
    return APIFY_ACTOR_CATALOG.get(
        actor_id,
        ActorMetadata(
            id=actor_id,
            name=actor_id,
            supported_sources=["Generic"],
            supported_countries=["global"],
            capabilities=set(),
        ),
    )
