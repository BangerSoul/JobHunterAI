import logging
from datetime import datetime
from typing import Any, Dict, List

from core.schemas.job_listing import JobListingCreate

logger = logging.getLogger(__name__)


class DatasetMapper:
    """
    Normalizes inconsistent raw JSON items from various Apify actors into
    the standardized JobHunterAI schema.
    """

    @staticmethod
    def normalize(
        raw_items: List[Dict[str, Any]], provider_name: str = "apify"
    ) -> List[JobListingCreate]:
        normalized = []

        for item in raw_items:
            try:
                # 1. Identity & URLs
                job_id = str(
                    item.get("id")
                    or item.get("jobId")
                    or item.get("job_id")
                    or item.get("hash")
                    or f"ext-{datetime.now().timestamp()}"
                )
                options = item.get("apply_options")
                apply_link = ""
                if isinstance(options, list) and options and isinstance(options[0], dict):
                    apply_link = options[0].get("link") or ""
                job_url = (
                    item.get("link")
                    or item.get("url")
                    or item.get("jobUrl")
                    or apply_link
                    or item.get("share_link")
                    or "#"
                )

                # 2. Core Fields (with aggressive fallback)
                title = (
                    item.get("title")
                    or item.get("jobTitle")
                    or item.get("position")
                    or "Unknown Role"
                )
                company = (
                    item.get("companyName")
                    or item.get("company")
                    or item.get("company_name")
                    or item.get("employer")
                    or "Confidential"
                )
                location = item.get("location") or item.get("city") or "Remote"

                # 3. Descriptions
                raw_desc = (
                    item.get("descriptionText")
                    or item.get("description")
                    or item.get("body")
                    or f"{title} at {company}."
                )

                # 4. Salary Parsing
                sal_raw = item.get("salary") or item.get("salaryRange") or ""

                # 5. Dates
                posted_str = (
                    item.get("postedAt") or item.get("date") or item.get("time")
                )
                posted_dt = None
                if posted_str:
                    try:
                        posted_dt = datetime.fromisoformat(
                            str(posted_str).replace("Z", "+00:00")
                        )
                    except:
                        pass

                normalized.append(
                    JobListingCreate(
                        job_id_raw=job_id,
                        title=title.strip(),
                        company_name=company.strip(),
                        location=location.strip(),
                        work_place_type=item.get("workplaceType", "Onsite"),
                        job_type=item.get("jobType", "Full-Time"),
                        source=item.get("source", provider_name),
                        url=job_url,
                        description_raw=str(raw_desc),
                        description_clean=str(raw_desc)[:500],
                        salary_raw=str(sal_raw) if sal_raw else None,
                    )
                )
            except Exception as e:
                logger.warning(f"Failed to normalize scraper item: {e}")

        return normalized
