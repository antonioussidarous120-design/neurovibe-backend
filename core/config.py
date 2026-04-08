from pydantic_settings import BaseSettings
from pydantic import field_validator

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
    ALLOWED_ORIGINS: str = "*"
    WORDS_PER_SECOND: float = 2.5
    MAX_SEGMENT_WORDS: int = 50
    MIN_SEGMENT_WORDS: int = 10

    @field_validator("ASSEMBLYAI_API_KEY", mode="before")
    @classmethod
    def strip_assemblyai_key(cls, v: str) -> str:
        return v.strip() if isinstance(v, str) else v

    class Config:
        env_file = ".env"
        extra = "allow"

settings = Settings()
