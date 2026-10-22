import logging
import random
from typing import List, Optional
from urllib.parse import quote

from apify_client import ApifyClientAsync

logger = logging.getLogger(__name__)


def build_actor_run_input(
    actor_id: str, search_query: str, location: str, limit: int
) -> dict:
    """Build Actor input. The johnvc Google Jobs Actor uses query, not queries."""
    actor_key = (actor_id or "").lower()
    if "google-jobs-scraper" in actor_key:
        return {
            "query": search_query,
            "location": location or "",
            "num_results": limit,
            "max_pagination": 1,
        }
    if "google-jobs" in (actor_id or ""):
        return {
            "queries": f"{search_query} in {location}",
            "maxPagesPerQuery": 1,
            "maxResultsPerQuery": limit,
        }
    if "linkedin-jobs" in (actor_id or ""):
        return {
            "queries": f"{search_query} {location}",
            "limit": limit,
        }
    if "indeed" in (actor_id or ""):
        return {
            "position": search_query,
            "location": location,
            "maxItems": limit,
        }
    return {"queries": search_query, "limit": limit}


def map_actor_item(item: dict, fallback_location: str, source_id: str, job_type: str) -> dict:
    """Read the fields this fleet already stores, with johnvc names as fallbacks."""
    options = item.get("apply_options")
    apply_link = ""
    if isinstance(options, list) and options and isinstance(options[0], dict):
        apply_link = options[0].get("link") or ""
    title = item.get("title") or item.get("job_title") or item.get("positionName") or "Role"
    company = (
        item.get("companyName")
        or item.get("company")
        or item.get("company_name")
        or "Company"
    )
    loc = item.get("location") or item.get("city", fallback_location)
    job_url = (
        item.get("url")
        or item.get("link")
        or item.get("jobUrl")
        or apply_link
        or item.get("share_link")
        or "#"
    )
    raw_id = str(
        item.get("id")
        or item.get("jobId")
        or item.get("job_id")
        or f"{source_id}-{random.randint(1000, 9999)}"
    )
    desc = item.get("description") or item.get("descriptionText") or "View listing for details."
    return {
        "job_id_raw": raw_id,
        "title": title.strip(),
        "company_name": company.strip(),
        "location": str(loc),
        "work_place_type": "Onsite",
        "job_type": job_type,
        "source": f"apify:{source_id}",
        "url": job_url,
        "description_raw": str(desc),
        "description_clean": str(desc)[:300],
    }


from core.config.settings import settings
from core.schemas.job_listing import JobListingCreate
from core.scrapers.base import BaseScraper


class ApifyJobScraper(BaseScraper):
    def __init__(self, actor_config: Optional[dict] = None):
        """
        Generic Apify Actor wrapper.
        :param actor_config: Configuration from the YAML registry.
        """
        self.config = actor_config or {
            "id": "google_jobs",
            "name": "Apify Cloud",
            "actor_id": "johnvc/Google-Jobs-Scraper",
        }

    @property
    def name(self) -> str:
        return self.config.get("name", "Apify Cloud")

    async def scrape(
        self,
        search_query: str,
        location: Optional[str] = None,
        limit: int = 10,
        job_type: str = "Full-Time",
    ) -> List[JobListingCreate]:
        log = logger
        from core.providers.apify.registry import registry as apify_registry

        token = settings.APIFY_API_TOKEN.strip() if settings.APIFY_API_TOKEN else ""
        if not token:
            log.warning("APIFY_API_TOKEN unconfigured. Skipping.")
            return []

        actor_id = self.config.get("actor_id")
        target_location = location or "Remote"

        client = ApifyClientAsync(token=token)

        # 1. Determine specialized input based on actor ID
        run_input = build_actor_run_input(actor_id, search_query, target_location, limit)

        try:
            log.info(f"Invoking {self.name} ({actor_id})")
            run = await client.actor(actor_id).call(
                run_input=run_input,
                timeout_secs=self.config.get("timeout_seconds", 120)
            )

            # 2. Extract Dataset ID
            dataset_id = run.get("defaultDatasetId") or run.get("default_dataset_id")
            if not dataset_id:
                log.error(f"No dataset ID for {actor_id}")
                return []

            # 3. Retrieve and Map Items
            dataset_items = await client.dataset(dataset_id).list_items()
            raw_items = []
            if hasattr(dataset_items, "items"): raw_items = dataset_items.items
            elif isinstance(dataset_items, list): raw_items = dataset_items

            jobs = []
            for item in raw_items[:limit]:
                try:
                    jobs.append(
                        JobListingCreate(
                            **map_actor_item(
                                item,
                                target_location,
                                self.config["id"],
                                job_type,
                            )
                        )
                    )
                except:
                    continue

            apify_registry.mark_actor_healthy(self.config["id"])
            log.info(f"{self.name} finished. Found {len(jobs)}")
            return jobs

        except Exception as e:
            log.error(f"{self.name} failed: {e}")
            apify_registry.mark_actor_unhealthy(self.config["id"], str(e))
            return []
