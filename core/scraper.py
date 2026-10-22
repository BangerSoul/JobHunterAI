import logging
import os
from typing import Any, Dict, List

from core.ai.smart_router import route
from core.config.settings import settings

logger = logging.getLogger("jobhunterai.scraper")


def first_apply_link(job: Dict[str, Any]) -> str:
    """Return the first apply link on a johnvc Google Jobs row."""
    options = job.get("apply_options")
    if isinstance(options, list) and options and isinstance(options[0], dict):
        link = options[0].get("link")
        if isinstance(link, str):
            return link
    return ""


def build_apify_run_input(
    actor_id: str, query: str, location: str, limit: int
) -> Dict[str, Any]:
    """Build Actor input. johnvc Google Jobs is a different schema from the removed Actor."""
    if "google-jobs-scraper" in actor_id.lower():
        return {
            "query": query,
            "location": location or "",
            "num_results": limit,
            "max_pagination": 1,
        }
    if "google-jobs" in actor_id:
        return {"queries": query, "maxPagesPerQuery": 1}
    return {"queries": query}


def normalize_scraped_job(job: Dict[str, Any], source: str) -> Dict[str, Any]:
    """Map one scraped row onto the fields /scrape already returns."""
    return {
        "title": job.get("title") or job.get("job_title") or "Unknown Title",
        "company_name": job.get("company_name") or job.get("company") or "Unknown Company",
        "location": job.get("location") or "Remote",
        "url": job.get("url")
        or job.get("job_url")
        or first_apply_link(job)
        or job.get("share_link")
        or "#",
        "source": source,
        "description_raw": job.get("description") or job.get("description_raw") or "",
    }


from core.providers.apify.registry import registry as apify_registry
from core.providers.apify.selector import selector as apify_selector

# --- Cloud Primary ---
async def apify_scrape(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Uses Apify Actor Registry to discover jobs dynamically."""
    from apify_client import ApifyClient

    token = settings.APIFY_API_TOKEN
    if not token:
        raise ValueError("APIFY_API_TOKEN not configured")

    client = ApifyClient(token)
    query = payload.get("query", "Software Engineer")
    location = payload.get("location", "Remote")

    # Select best actor
    actor_meta = apify_selector.select_actor(query, location)
    if not actor_meta or not actor_meta.get("actor_id"):
        logger.warning("No suitable Apify actor found in registry.")
        return None

    actor_id = actor_meta["actor_id"]
    limit = int(payload.get("limit") or actor_meta.get("max_results") or 10)

    try:
        run_input = build_apify_run_input(actor_id, query, location, limit)

        logger.info(f"Dynamic Dispatch -> Apify Actor: {actor_id}")
        run = client.actor(actor_id).call(run_input=run_input)
        results = list(client.dataset(run["defaultDatasetId"]).iterate_items())

        if not results:
            return None

        apify_registry.mark_actor_healthy(actor_meta["id"])
        return {"source": f"apify:{actor_meta['id']}", "data": results}
    except Exception as e:
        logger.error(f"Apify Actor {actor_id} failed: {str(e)}")
        apify_registry.mark_actor_unhealthy(actor_meta["id"], str(e))
        raise e


apify_scrape.required_envs = ["APIFY_API_TOKEN"]


def get_sample_jobs() -> List[Dict[str, Any]]:
    """Returns realistic mock jobs when scraping is blocked."""
    return [
        {
            "title": "Backend Engineer (Sample)",
            "company_name": "JobHunterAI Demo",
            "location": "Remote",
            "source": "sample_fallback",
            "url": "https://example.com/demo-job-1",
            "description_raw": "This is a sample job returned because the scraping service is currently being rate-limited.",
        },
        {
            "title": "Full Stack Developer (Sample)",
            "company_name": "Cloud Systems",
            "location": "New York, NY",
            "source": "sample_fallback",
            "url": "https://example.com/demo-job-2",
            "description_raw": "Experience the JobHunterAI interface with this mock data. Try again in a few minutes.",
        },
    ]


# --- Local Fallback ---
async def local_scrape(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Uses python-jobspy for local scraping with anti-bot resilience and backoff."""
    max_retries = 2
    for attempt in range(max_retries + 1):
        try:
            import asyncio
            import random

            from jobspy import scrape_jobs

            # Jittered delay for retries
            if attempt > 0:
                delay = 5 * attempt + random.uniform(1, 3)
                logger.info(
                    f"Retrying local scrape in {delay:.2f}s (Attempt {attempt+1}/{max_retries+1})"
                )
                await asyncio.sleep(delay)

            # Reduced sites to minimize 403 blocks
            jobs = scrape_jobs(
                site_name=["linkedin", "indeed"],
                search_term=payload.get("query", "Software Engineer"),
                location=payload.get("location", "Remote"),
                results_wanted=payload.get("limit", 10),
            )

            if jobs is None or jobs.empty:
                if attempt == max_retries:
                    logger.warning(
                        "JobSpy returned empty results after retries. Serving sample fallback."
                    )
                    return {"source": "sample_fallback", "data": get_sample_jobs()}
                continue

            return {"source": "jobspy", "data": jobs.to_dict("records")}
        except Exception as e:
            err_str = str(e)
            if "403" in err_str or "blocked" in err_str.lower():
                logger.warning(f"Local jobspy blocked (403) on attempt {attempt+1}")
                if attempt < max_retries:
                    continue

            logger.warning(
                f"Local jobspy scrape failed: {e}. Falling back to sample data."
            )
            return {"source": "sample_fallback", "data": get_sample_jobs()}

    return {"source": "sample_fallback", "data": get_sample_jobs()}


local_scrape.safe_placeholder = {"source": "error", "data": []}


# --- Public API ---
async def scrape_jobs(payload: Dict[str, Any]) -> Dict[str, Any]:

    async def apify_tier(**kwargs):
        return await apify_scrape(payload)
    apify_tier.required_envs = ["APIFY_API_TOKEN"]

    async def jobspy_tier(**kwargs):
        return await local_scrape(payload)
    jobspy_tier.required_envs = []

    res = await route(apify_tier, jobspy_tier)

    # Simple Normalization
    normalized = []
    raw_data = res.get("data", [])
    for job in raw_data:
        normalized.append(normalize_scraped_job(job, res.get("source", "unknown")))

    return {"source": res.get("source"), "data": normalized}
