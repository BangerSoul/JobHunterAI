from typing import Optional

from pydantic import BaseModel, Field

from core.config.settings import settings


class ApifyConfig(BaseModel):
    """Configuration for the Apify scraper provider."""

    api_token: Optional[str] = Field(default=None)
    default_actor_id: str = Field(default="johnvc/Google-Jobs-Scraper")

    # Run parameters
    timeout_secs: int = Field(default=300, ge=1)
    memory_mbytes: int = Field(default=2048, ge=256)
    max_items: int = Field(default=50, ge=1)

    @classmethod
    def from_settings(cls):
        """Loads configuration from global application settings."""
        return cls(
            api_token=settings.APIFY_API_TOKEN, default_actor_id=settings.APIFY_ACTOR_ID
        )
