"""Fixture tests for the johnvc Google Jobs drop-in.

These tests use recorded rows. They do not call Apify.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("AI_PROVIDER", "ollama")

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from core.providers.scrapers.apify_mapper import ApifyRequestMapper, ScrapeRequest
from core.providers.scrapers.dataset_mapper import DatasetMapper
from core.scraper import build_apify_run_input, normalize_scraped_job
from core.scrapers.apify_scraper import build_actor_run_input, map_actor_item

APPLY_ROW: dict[str, object] = {
    "title": "Backend Engineer",
    "job_title": "Backend Engineer",
    "company_name": "Northwind Labs",
    "location": "Berlin, Germany",
    "description": "Build APIs.",
    "job_id": "gj-1001",
    "share_link": "https://www.google.com/search?q=job-1001",
    "apply_options": [{"title": "Apply", "link": "https://jobs.example.com/1001"}],
}

SHARE_ROW: dict[str, object] = {
    "title": "Data Analyst",
    "company_name": "Harbor Co",
    "location": "London, UK",
    "description": "Analyze reports.",
    "job_id": "gj-1002",
    "share_link": "https://www.google.com/search?q=job-1002",
    "apply_options": [],
}


def test_fleet_input_uses_the_johnvc_schema() -> None:
    """The scrape fleet sends the fields johnvc/Google-Jobs-Scraper accepts."""
    payload = build_actor_run_input(
        "johnvc/Google-Jobs-Scraper", "Backend Engineer", "Berlin", 10
    )
    assert payload == {
        "query": "Backend Engineer",
        "location": "Berlin",
        "num_results": 10,
        "max_pagination": 1,
    }


def test_old_google_jobs_slug_keeps_its_input() -> None:
    """An override of the removed slug still builds the old input."""
    payload = build_actor_run_input(
        "toolsnmoreapi/google-jobs", "Backend Engineer", "Berlin", 10
    )
    assert payload["queries"] == "Backend Engineer in Berlin"
    assert "query" not in payload


def test_fleet_mapper_reads_johnvc_rows() -> None:
    """Recorded johnvc rows fill company, url, and id on the fleet scraper."""
    first = map_actor_item(APPLY_ROW, "Remote", "google_jobs", "Full-Time")
    second = map_actor_item(SHARE_ROW, "Remote", "google_jobs", "Full-Time")

    assert first["title"] == "Backend Engineer"
    assert first["company_name"] == "Northwind Labs"
    assert first["location"] == "Berlin, Germany"
    assert first["job_id_raw"] == "gj-1001"
    assert first["url"] == "https://jobs.example.com/1001"

    assert second["company_name"] == "Harbor Co"
    assert second["job_id_raw"] == "gj-1002"
    assert second["url"] == "https://www.google.com/search?q=job-1002"


def test_smoke_scraper_normalizer_reads_johnvc_rows() -> None:
    """The smoke-test scraper maps the same recorded rows."""
    run_input = build_apify_run_input(
        "johnvc/Google-Jobs-Scraper", "Backend Engineer", "Berlin", 25
    )
    assert run_input == {
        "query": "Backend Engineer",
        "location": "Berlin",
        "num_results": 25,
        "max_pagination": 1,
    }
    assert build_apify_run_input("toolsnmoreapi/google-jobs", "Analyst", "", 5) == {
        "queries": "Analyst",
        "maxPagesPerQuery": 1,
    }

    first = normalize_scraped_job(APPLY_ROW, "apify:google_jobs")
    second = normalize_scraped_job(SHARE_ROW, "apify:google_jobs")
    assert first["title"] == "Backend Engineer"
    assert first["company_name"] == "Northwind Labs"
    assert first["url"] == "https://jobs.example.com/1001"
    assert second["url"] == "https://www.google.com/search?q=job-1002"


def test_dataset_mapper_reads_johnvc_rows() -> None:
    """ApifyProvider's dataset mapper fills id, company, and url from johnvc rows."""
    listings = DatasetMapper.normalize([APPLY_ROW, SHARE_ROW])
    assert listings[0].job_id_raw == "gj-1001"
    assert listings[0].title == "Backend Engineer"
    assert listings[0].company_name == "Northwind Labs"
    assert listings[0].location == "Berlin, Germany"
    assert listings[0].url == "https://jobs.example.com/1001"
    assert listings[0].salary_min is None
    assert listings[0].date_posted is None
    assert listings[1].job_id_raw == "gj-1002"
    assert listings[1].company_name == "Harbor Co"
    assert listings[1].url == "https://www.google.com/search?q=job-1002"


def test_provider_mapper_uses_the_johnvc_schema() -> None:
    """ApifyProvider sends johnvc input and leaves the old slug on its old input."""
    request = ScrapeRequest(query="Backend Engineer", location="Berlin", limit=10)
    johnvc = ApifyRequestMapper.to_actor_input("johnvc/Google-Jobs-Scraper", request)
    legacy = ApifyRequestMapper.to_actor_input("apify/google-jobs-scraper", request)

    assert johnvc == {
        "query": "Backend Engineer",
        "location": "Berlin",
        "num_results": 10,
        "max_pagination": 1,
    }
    assert legacy["queries"] == "Backend Engineer in Berlin"
    assert "query" not in legacy
