from pydantic import BaseModel, Field
from typing import Optional, List, Dict
from enum import Enum

class ContentType(str, Enum):
    video = "video"
    script = "script"

class JobStatus(str, Enum):
    pending = "pending"
    transcribing = "transcribing"
    analyzing = "analyzing"
    predicting = "predicting"
    rewriting = "rewriting"
    complete = "complete"
    failed = "failed"

class TranscriptSegment(BaseModel):
    time_start: float
    time_end: float
    text: str

class EmotionScores(BaseModel):
    curiosity: float = Field(ge=0.0, le=1.0)
    warmth: float = Field(ge=0.0, le=1.0)
    trust: float = Field(ge=0.0, le=1.0)
    excitement: float = Field(ge=0.0, le=1.0)
    boredom_risk: float = Field(ge=0.0, le=1.0)

class ScoredSegment(BaseModel):
    segment_id: str
    time_start: float
    time_end: float
    text: str
    scores: EmotionScores
    segment_score: float
    is_drop_moment: bool
    drop_reason: Optional[str] = None

class DropMoment(BaseModel):
    time_start: float
    time_end: float
    reason: str
    segment_id: str

class PredictionResponse(BaseModel):
    job_id: str
    engagement_score: float
    watch_time_probability: float
    share_likelihood: float
    conversion_likelihood: float
    drop_moments: List[DropMoment]

class TimelinePoint(BaseModel):
    time_start: float
    time_end: float
    score: float
    dominant_emotion: str
    is_drop_moment: bool

class TimelineResponse(BaseModel):
    job_id: str
    points: List[TimelinePoint]
    overall_score: float
