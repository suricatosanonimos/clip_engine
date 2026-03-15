"""
Schemas Pydantic — contratos de entrada e saída da API.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, EmailStr, Field, validator


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
#  AUTH — mantido exatamente como estava
# ──────────────────────────────────────────────────────────────────

class RegisterUser(BaseModel):
    """Schema para registro de novo usuário"""
    nome:  str      = Field(..., min_length=3, max_length=100, description="Nome completo do usuário")
    email: EmailStr = Field(...,                               description="Email válido do usuário")
    senha: str      = Field(..., min_length=6, max_length=50,  description="Senha com mínimo de 6 caracteres")

    @validator("nome")
    def nome_nao_vazio(cls, v):
        if not v or not v.strip():
            raise ValueError("Nome não pode estar vazio")
        return v.strip()

    @validator("senha")
    def senha_segura(cls, v):
        if len(v) < 6:
            raise ValueError("Senha deve ter pelo menos 6 caracteres")
        return v

    model_config = {
        "json_schema_extra": {
            "example": {
                "nome":  "João Silva",
                "email": "joao@email.com",
                "senha": "123456",
            }
        }
    }


class LoginUser(BaseModel):
    """Schema para login de usuário"""
    email: EmailStr = Field(...,               description="Email do usuário")
    senha: str      = Field(..., min_length=1, description="Senha do usuário")

    model_config = {
        "json_schema_extra": {
            "example": {
                "email": "joao@email.com",
                "senha": "123456",
            }
        }
    }


class UserResponse(BaseModel):
    """Schema para resposta com dados do usuário"""
    id:         str
    email:      str
    nome:       str
    created_at: Optional[datetime] = None
    avatar_url: Optional[str]      = None

    model_config = {
        "from_attributes": True,
        "json_encoders": {datetime: lambda v: v.isoformat()},
    }


class AuthResponse(BaseModel):
    """Schema para resposta de autenticação"""
    success: bool
    message: str
    user:    UserResponse
    session: Optional[Dict[str, Any]] = None


# ──────────────────────────────────────────────────────────────────
#  VIDEO — requisição de processamento
#
#  user_id e job_id são OPCIONAIS:
#    - Se vierem → API usa esses valores e atualiza o banco
#    - Se não vierem → API gera job_id internamente (modo local/teste)
# ──────────────────────────────────────────────────────────────────

class VideoProcessRequest(BaseModel):
    url:           str           = Field(...,              description="URL do YouTube ou URL assinada do Storage")
    user_id:       Optional[str] = Field(None,             description="UUID do usuário autenticado (opcional)")
    job_id:        Optional[str] = Field(None,             description="UUID do job — API cria se não vier")
    num_clips:     int           = Field(default=10,  ge=1, le=30)
    clip_duration: int           = Field(default=60,  ge=10, le=180)
    tracking:      bool          = Field(default=True)
    subtitles:     bool          = Field(default=False)
    source_type:   str           = Field(default="youtube",  description="youtube | upload")
    cor_legenda:   str           = Field(default="white",    description="white | yellow | blue | green")

    model_config = {
        "json_schema_extra": {
            "example": {
                "url":           "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
                "user_id":       "uuid-do-usuario",
                "job_id":        "uuid-do-job",
                "num_clips":     10,
                "clip_duration": 60,
                "tracking":      True,
                "subtitles":     False,
                "source_type":   "youtube",
            }
        }
    }


class VideoProcessResponse(BaseModel):
    task_id: str
    job_id:  str
    status:  TaskStatus
    message: str


# ──────────────────────────────────────────────────────────────────
#  CLIPE — resultado individual
# ──────────────────────────────────────────────────────────────────

class ClipResult(BaseModel):
    index:            int
    filename:         str
    path:             str
    size_mb:          float
    duration_seconds: Optional[float] = None
    storage_path:     Optional[str]   = None
    public_url:       Optional[str]   = None


# ──────────────────────────────────────────────────────────────────
#  CLIPE — galeria do usuário
# ──────────────────────────────────────────────────────────────────

class ClipGaleria(BaseModel):
    id:           str
    job_id:       str
    filename:     str
    storage_path: str
    public_url:   Optional[str]   = None
    size_mb:      Optional[float] = None
    clip_index:   int
    score:        float           = 0.0
    motivo:       Optional[str]   = None
    created_at:   str


# ──────────────────────────────────────────────────────────────────
#  STATUS da tarefa
# ──────────────────────────────────────────────────────────────────

class TaskStatusResponse(BaseModel):
    task_id:     str
    job_id:      Optional[str]            = None
    status:      TaskStatus
    progress:    float                    = Field(default=0.0, ge=0.0, le=1.0)
    message:     str                      = ""
    clips:       List[ClipResult]         = []
    ai_analysis: Optional[Dict[str, Any]] = None
    error:       Optional[str]            = None


# ──────────────────────────────────────────────────────────────────
#  JOBS — criação de job pelo app
# ──────────────────────────────────────────────────────────────────

class JobCreateRequest(BaseModel):
    user_id:       str           = Field(...,             description="UUID do usuário autenticado")
    source_type:   str           = Field(...,             description="youtube | upload")
    source_url:    Optional[str] = Field(None,            description="URL do YouTube")
    num_clips:     int           = Field(default=10,  ge=1, le=30)
    clip_duration: int           = Field(default=60,  ge=10, le=180)
    tracking:      bool          = Field(default=True)


class JobCreateResponse(BaseModel):
    id:          str
    user_id:     str
    status:      str
    source_type: str


# ──────────────────────────────────────────────────────────────────
#  INFO do vídeo (YouTube)
# ──────────────────────────────────────────────────────────────────

class VideoInfoRequest(BaseModel):
    url: str = Field(..., description="URL do vídeo no YouTube")


class VideoInfoResponse(BaseModel):
    title:       str
    duration:    int
    uploader:    str
    view_count:  int
    description: str


# ──────────────────────────────────────────────────────────────────
#  TÍTULOS via IA
# ──────────────────────────────────────────────────────────────────

class TitlesRequest(BaseModel):
    url:   str = Field(...,             description="URL do vídeo no YouTube")
    count: int = Field(default=5, ge=1, le=20, description="Quantidade de títulos a gerar")


class TitlesResponse(BaseModel):
    video_title: str
    titles:      List[str]
    count:       int


# ──────────────────────────────────────────────────────────────────
#  TRANSCRIÇÃO
# ──────────────────────────────────────────────────────────────────

class TranscriptionSegment(BaseModel):
    start: float
    end:   float
    text:  str


class TranscriptionRequest(BaseModel):
    video_path: str = Field(..., description="Caminho absoluto do vídeo no servidor")
    model_size: str = Field(default="tiny", description="tiny | base | small | medium")


class TranscriptionResponse(BaseModel):
    video_path:     str
    segments:       List[TranscriptionSegment]
    total_segments: int
    ai_analysis:    Optional[Dict[str, Any]] = None


# ──────────────────────────────────────────────────────────────────
#  ERRO genérico
# ──────────────────────────────────────────────────────────────────

class ErrorResponse(BaseModel):
    detail: str
    code:   Optional[str] = None
