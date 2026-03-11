from supabase import create_client, Client
from core.config import settings
import functools

@functools.lru_cache(maxsize=1)
def get_supabase() -> Client:
    return create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY)
