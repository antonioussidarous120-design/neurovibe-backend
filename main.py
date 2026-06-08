# Last updated: 2026-05-07
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from core.config import settings

app = FastAPI(title="NeuroVibe Studio API")

# CORS: only allow explicit origins — never wildcard.
_allowed_origins = settings.get_allowed_origins()

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_origin_regex=r"https://.*\.(lovable\.app|lovableproject\.com|up\.railway\.app)$",
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept"],
)

from modules.upload.router import router as upload_router
from modules.transcription.router import router as transcription_router
from modules.emotion_engine.router import router as emotion_router
from modules.prediction_engine.router import router as prediction_router
from modules.rewrite_engine.router import router as rewrite_router
from modules.timeline.router import router as timeline_router
from modules.pipeline.router import router as pipeline_router
from modules.outreach.router import router as outreach_router
from modules.content.router import router as content_router
from modules.hooks.router import router as hooks_router
from modules.calendar.router import router as calendar_router
from modules.video_analysis.router import router as video_router
from modules.generator.router import router as generator_router
from modules.brand.router import router as brand_router

app.include_router(upload_router,        prefix="/api/upload",     tags=["Upload"])
app.include_router(transcription_router, prefix="/api/transcribe", tags=["Transcription"])
app.include_router(emotion_router,       prefix="/api/analyze",    tags=["Emotion"])
app.include_router(prediction_router,    prefix="/api/predict",    tags=["Prediction"])
app.include_router(rewrite_router,       prefix="/api/rewrite",    tags=["Rewrite"])
app.include_router(timeline_router,      prefix="/api/timeline",   tags=["Timeline"])
app.include_router(pipeline_router,      prefix="/api/pipeline",   tags=["Pipeline"])
app.include_router(outreach_router,      prefix="/api/outreach",   tags=["Outreach"])
app.include_router(content_router,       prefix="/api/content",    tags=["Content"])
app.include_router(hooks_router,         prefix="/api/hooks",      tags=["Hooks"])
app.include_router(calendar_router,      prefix="/api/calendar",   tags=["Calendar"])
app.include_router(video_router,         prefix="/api/video",      tags=["Video Analysis"])
app.include_router(generator_router,     prefix="/api/generator",  tags=["Generator"])
app.include_router(brand_router,         prefix="/api/brand",      tags=["Brand"])

@app.get("/health")
def health():
    db_status = "unknown"
    db_error = None
    try:
        from core.database import get_supabase
        db = get_supabase()
        db.table("jobs").select("id").limit(1).execute()
        db_status = "connected"
    except Exception as e:
        db_status = "error"
        db_error = str(e)
    return {
        "status": "ok",
        "allowed_origins": _allowed_origins,
        "db": db_status,
        "db_error": db_error,
        "supabase_url": settings.SUPABASE_URL[:40] + "..." if settings.SUPABASE_URL else "NOT SET",
    }
