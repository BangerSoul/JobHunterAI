import os
import json
from pathlib import Path
from typing import Dict, List, Optional, Any, Union

from pydantic import Field, field_validator, model_validator, AliasChoices
from pydantic_settings import BaseSettings, SettingsConfigDict

# Get the path to the .env file in the project root
project_root = Path(__file__).resolve().parent.parent.parent
env_path = project_root / ".env"


class Settings(BaseSettings):
    """
    Centralized configuration management for JobHunterAI.
    Loads settings from environment variables and .env file.
    """
    model_config = SettingsConfigDict(
        env_file=str(env_path),
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # --- Authoritative Environment State ---
    ENVIRONMENT: str = Field(
        default="development",
        validation_alias=AliasChoices("ENVIRONMENT", "NODE_ENV", "APP_ENV"),
        description="Deployment environment (development, production, testing)"
    )
    VERSION: str = "1.0.0"
    DEBUG: bool = Field(default=True, description="Enable debug logging and Swagger UI")
    PORT: int = Field(default=8000, description="Server port")
    LOG_DIR: str = Field(default="logs", description="Directory for system logs")
    DATABASE_URL: str = Field(
        default="sqlite+aiosqlite:///jobhunter.db",
        description="Database connection string (Postgres recommended for production)"
    )

    # --- AI Provider Configuration ---
    AI_PROVIDER: str = Field(
        default="groq",
        description="Primary AI provider (groq, gemini, openai, openrouter, ollama, auto)"
    )

    # Dynamic Routing Configuration (Used when AI_PROVIDER='auto')
    DEFAULT_AI_PROVIDER: str = Field(default="groq")
    FALLBACK_AI_PROVIDER: str = Field(default="gemini")
    LOCAL_AI_PROVIDER: str = Field(default="ollama")

    GROQ_API_KEY: Optional[str] = None
    GROQ_MODEL: str = "llama-3.3-70b-versatile"

    GEMINI_API_KEY: Optional[str] = None
    GEMINI_MODEL: str = "gemini-1.5-flash"

    OPENAI_API_KEY: Optional[str] = None
    OPENAI_MODEL: str = "gpt-4o"

    OPENROUTER_API_KEY: Optional[str] = None
    OPENROUTER_MODEL: str = "meta-llama/llama-3.3-70b-instruct:free"

    OLLAMA_HOST: str = "http://localhost:11434/v1"
    OLLAMA_MODEL: str = "qwen2.5-coder:7b"

    # --- Scraper Configuration ---
    APIFY_ENABLED: bool = True
    APIFY_API_TOKEN: Optional[str] = None
    APIFY_ACTOR_ID: str = "johnvc/Google-Jobs-Scraper"
    APIFY_MAX_CONCURRENT_RUNS: int = 3
    APIFY_RUN_TIMEOUT_SECONDS: int = 120
    APIFY_HEALTH_CHECK_INTERVAL_MINUTES: int = 60
    APIFY_ACTORS_CONFIG_PATH: str = "config/apify_actors.yaml"
    APIFY_FALLBACK_TO_SAMPLE: bool = True
    HUNTER_API_KEY: Optional[str] = None

    # --- Security & CORS ---
    CORS_ORIGINS: Union[List[str], str] = Field(
        default=["*"],
        description="Allowed CORS origins. Supports comma-separated string, JSON array, or list."
    )

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Any) -> List[str]:
        if isinstance(v, str):
            v = v.strip()
            if v.startswith("[") and v.endswith("]"):
                try:
                    return json.loads(v)
                except json.JSONDecodeError:
                    return [v]
            return [i.strip() for i in v.split(",") if i.strip()]
        return v

    @model_validator(mode="after")
    def validate_security_and_ai(self) -> "Settings":
        # 1. CORS Production Check
        if self.is_production:
            if "*" in self.CORS_ORIGINS:
                raise ValueError("CORS_ORIGINS cannot contain '*' in production environment.")

        # 2. AI Provider Validation
        allowed_providers = ["groq", "gemini", "openai", "openrouter", "ollama", "auto"]
        provider = self.AI_PROVIDER.lower()
        if provider not in allowed_providers:
            raise ValueError(f"AI_PROVIDER must be one of {allowed_providers}")

        # 3. Cloud Provider Key Checks
        # When AI_PROVIDER is 'auto', we don't fail immediately as it handles fallback.
        # But for specific cloud providers, we require the key.
        if provider == "groq" and not self.GROQ_API_KEY:
            raise ValueError("GROQ_API_KEY is required when AI_PROVIDER='groq'")
        if provider == "gemini" and not self.GEMINI_API_KEY:
            raise ValueError("GEMINI_API_KEY is required when AI_PROVIDER='gemini'")
        if provider == "openai" and not self.OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY is required when AI_PROVIDER='openai'")
        if provider == "openrouter" and not self.OPENROUTER_API_KEY:
            raise ValueError("OPENROUTER_API_KEY is required when AI_PROVIDER='openrouter'")

        return self

    # --- Matching & ATS Intelligence ---
    MATCHING_CONFIG_VERSION: str = "1.0.0"
    MATCHING_WEIGHTS: Dict[str, float] = {
        "skills": 0.35,
        "experience": 0.25,
        "education": 0.10,
        "keywords": 0.15,
        "location": 0.10,
        "salary": 0.05,
    }

    @field_validator("MATCHING_WEIGHTS")
    @classmethod
    def validate_weights(cls, v):
        total = sum(v.values())
        if not (0.99 <= total <= 1.01 or 99 <= total <= 101):
            raise ValueError(f"MATCHING_WEIGHTS must sum to 1.0 or 100 (current: {total})")
        return v

    # --- Properties ---
    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT.lower() == "production"

    @property
    def is_development(self) -> bool:
        return self.ENVIRONMENT.lower() == "development"


# Singleton instance
settings = Settings()
