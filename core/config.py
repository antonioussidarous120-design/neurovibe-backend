from pydantic_settings import BaseSettings
from pydantic import field_validator
import json
from typing import List

class Settings(BaseSettings):
    SUPABASE_URL: str
    SUPABASE_KEY: str = ""
    SUPABASE_ANON_KEY: str = ""
    SUPABASE_SERVICE_ROLE_KEY: str = ""
    SUPABASE_JWT_SECRET: str = ""
    SUPABASE_BUCKET: str = "neurovibe-uploads"
    OPENAI_API_KEY: str
    OPENAI_MODEL: str = "gpt-4o"
    ASSEMBLYAI_API_KEY: str = ""
    GOOGLE_APPLICATION_CREDENTIALS: str = ""
    GOOGLE_CLOUD_PROJECT: str = ""
    GOOGLE_CLOUD_BUCKET: str = ""
    ALLOWED_ORIGINS: str = '["http://localhost:3000"]'
    WORDS_PER_SECOND: float = 2.5
    MAX_SEGMENT_WORDS: int = 50
    MIN_SEGMENT_WORDS: int = 10

    @field_validator("ASSEMBLYAI_API_KEY", mode="before")
    @classmethod
    def strip_assemblyai_key(cls, v: str) -> str:
        return v.strip() if isinstance(v, str) else v

    def get_allowed_origins(self) -> List[str]:
        """Parse ALLOWED_ORIGINS — supports JSON array or comma-separated string.
        Never returns wildcard '*'."""
        raw = self.ALLOWED_ORIGINS.strip()
        if raw.startswith("["):
            try:
                origins = json.loads(raw)
            except json.JSONDecodeError:
                origins = [raw]
        else:
            origins = [o.strip() for o in raw.split(",") if o.strip()]
        # Remove any wildcard entries to prevent accidental open CORS
        safe = [o for o in origins if o != "*"]
        if not safe:
            safe = ["http://localhost:3000"]
        return safe

    class Config:
        env_file = ".env"
        extra = "allow"

settings = Settings()

# Single authoritative test-user constant — import this everywhere instead of
# copy-pasting the raw UUID string.
TEST_USER_ID = "00000000-0000-0000-0000-000000000001"
