"""
Schemas Pydantic — contratos de entrada e saída da API.
"""

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, HttpUrl


# ──────────────────────────────────────────────────────────────────
#  ENUMS
# ──────────────────────────────────────────────────────────────────

class TaskStatus(str, Enum):
    PENDING      = "pending"
    DOWNLOADING  = "downloading"
    PROCESSING   = "processing"
    TRANSCRIBING = "transcribing"
    ANALYZING    = "analyzing"
    DONE         = "done"
    ERROR        = "error"


# ──────────────────────────────────────────────────────────────────
#  VIDEO — requisição e resposta
# ──────────────────────────────────────────────────────────────────

class VideoProcessRequest(BaseModel):
    url: str = Field(..., description="URL do vídeo no YouTube")
    num_clips: int = Field(default=10, ge=1, le=30, description="Número de clipes a gerar")
    clip_duration: int = Field(default=60, ge=10, le=180, description="Duração de cada clipe em segundos")
    tracking: bool = Field(default=True, description="Ativar tracking de rostos com MediaPipe")
    subtitles: bool = Field(default=False, description="Gerar legendas word-by-word com Whisper")

    model_config = {
        "json_schema_extra": {
            "example": {
                "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
                "num_clips": 10,
                "clip_duration": 60,
                "tracking": True,
                "subtitles": False,
            }
        }
    }


class VideoProcessResponse(BaseModel):
    task_id: str
    status: TaskStatus
    message: str


# ──────────────────────────────────────────────────────────────────
#  STATUS da tarefa
# ──────────────────────────────────────────────────────────────────

class ClipResult(BaseModel):
    index: int
    filename: str
    path: str
    size_mb: float
    duration_seconds: Optional[float] = None


class TaskStatusResponse(BaseModel):
    task_id: str
    status: TaskStatus
    progress: float = Field(default=0.0, ge=0.0, le=1.0, description="0.0 a 1.0")
    message: str = ""
    clips: List[ClipResult] = []
    ai_analysis: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


# ──────────────────────────────────────────────────────────────────
#  INFO do vídeo (YouTube)
# ──────────────────────────────────────────────────────────────────

class VideoInfoRequest(BaseModel):
    url: str = Field(..., description="URL do vídeo no YouTube")


class VideoInfoResponse(BaseModel):
    title: str
    duration: int
    uploader: str
    view_count: int
    description: str


# ──────────────────────────────────────────────────────────────────
#  TÍTULOS gerados pela IA
# ──────────────────────────────────────────────────────────────────

class TitlesRequest(BaseModel):
    url: str = Field(..., description="URL do vídeo no YouTube")
    count: int = Field(default=5, ge=1, le=20, description="Quantidade de títulos a gerar")


class TitlesResponse(BaseModel):
    video_title: str
    titles: List[str]
    count: int


# ──────────────────────────────────────────────────────────────────
#  TRANSCRIÇÃO
# ──────────────────────────────────────────────────────────────────

class TranscriptionSegment(BaseModel):
    start: float
    end: float
    text: str


class TranscriptionRequest(BaseModel):
    video_path: str = Field(..., description="Caminho absoluto do vídeo já salvo no servidor")
    model_size: str = Field(default="tiny", description="Tamanho do modelo Whisper: tiny | base | small | medium")


class TranscriptionResponse(BaseModel):
    video_path: str
    segments: List[TranscriptionSegment]
    total_segments: int
    ai_analysis: Optional[Dict[str, Any]] = None


# ──────────────────────────────────────────────────────────────────
#  ERRO genérico
# ──────────────────────────────────────────────────────────────────

class ErrorResponse(BaseModel):
    detail: str
    code: Optional[str] = None
