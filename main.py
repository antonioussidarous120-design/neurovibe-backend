from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="NeuroVibe Studio API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
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

@app.get("/health")
def health(): return {"status": "ok"}
