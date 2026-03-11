from pydantic_settings import BaseSettings
from typing import List

class Settings(BaseSettings):
    SUPABASE_URL: str
    SUPABASE_SERVICE_ROLE_KEY: str
    SUPABASE_ANON_KEY: str
    SUPABASE_JWT_SECRET: str
    OPENAI_API_KEY: str
    OPENAI_MODEL: str = "gpt-4o"
    OPENAI_TRANSCRIPTION_MODEL: str = "whisper-1"
    HUGGINGFACE_MODEL: str = "j-hartmann/emotion-english-distilroberta-base"
    USE_HUGGINGFACE: bool = False
    SUPABASE_BUCKET: str = "neurovibe-uploads"
    MAX_UPLOAD_SIZE_MB: int = 500
    MAX_SEGMENT_DURATION_SEC: float = 30.0
    WORDS_PER_SECOND: float = 2.5
    DROP_MOMENT_THRESHOLD: float = 0.65
    ALLOWED_ORIGINS: List[str] = ["http://localhost:3000"]

    class Config:
        env_file = ".env"

settings = Settings()
