from pydantic_settings import BaseSettings
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
    ALLOWED_ORIGINS: List[str] = ["*"]

    class Config:
        env_file = ".env"
        extra = "allow"

settings = Settings()
