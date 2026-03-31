from pydantic_settings import BaseSettings

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
    ALLOWED_ORIGINS: str = "*"
    WORDS_PER_SECOND: float = 2.5
    MAX_SEGMENT_WORDS: int = 50
    MIN_SEGMENT_WORDS: int = 10

    class Config:
        env_file = ".env"
        extra = "allow"

settings = Settings()
