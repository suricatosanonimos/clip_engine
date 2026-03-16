"""
POST /api/jobs   → cria job no banco e retorna o UUID
GET  /api/jobs   → lista jobs do usuário

O app Flet chama POST /api/jobs antes de POST /api/video/process ou
POST /api/video/upload, para garantir que o job_id exista na tabela
`jobs` antes de qualquer INSERT em `clips` (foreign key constraint).
"""

import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel

from src.database.supabase_client import get_supabase_admin_client
from src.utils.logs import logger

router = APIRouter(prefix="/jobs", tags=["Jobs"])


# ──────────────────────────────────────────────────────────────────
#  SCHEMAS
# ──────────────────────────────────────────────────────────────────

class JobCreateRequest(BaseModel):
    user_id:       str
    source_type:   str = "youtube"          # "youtube" | "upload"
    source_url:    Optional[str] = None
    num_clips:     int  = 3
    clip_duration: int  = 60
    tracking:      bool = True


class JobResponse(BaseModel):
    id:            str
    user_id:       str
    status:        str
    source_type:   str
    source_url:    Optional[str]
    num_clips:     int
    clip_duration: int
    tracking:      bool


# ──────────────────────────────────────────────────────────────────
#  CRIAR JOB
# ──────────────────────────────────────────────────────────────────

@router.post(
    "",
    response_model=JobResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Cria um novo job no banco antes de iniciar o pipeline",
)
async def criar_job(body: JobCreateRequest) -> Dict[str, Any]:
    """
    Insere uma linha em public.jobs e retorna o UUID gerado.
    O app usa esse ID como job_id nas chamadas subsequentes
    (/api/video/process e /api/video/upload), garantindo que a
    foreign key de public.clips seja satisfeita.
    """
    job_id = str(uuid.uuid4())
    client = get_supabase_admin_client()

    try:
        resp = client.table("jobs").insert({
            "id":            job_id,
            "user_id":       body.user_id,
            "status":        "pending",
            "source_type":   body.source_type,
            "source_url":    body.source_url,
            "num_clips":     body.num_clips,
            "clip_duration": body.clip_duration,
            "tracking":      body.tracking,
            "progress":      0,
            "message":       "Aguardando início do pipeline.",
        }).execute()

        if not resp.data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Banco não retornou dados após inserção do job.",
            )

        job = resp.data[0]
        logger.info(f"Job criado: {job_id} | user: {body.user_id}")
        return job

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao criar job: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao criar job: {str(e)[:200]}",
        )


# ──────────────────────────────────────────────────────────────────
#  LISTAR JOBS DO USUÁRIO
# ──────────────────────────────────────────────────────────────────

@router.get(
    "",
    summary="Lista jobs do usuário",
)
async def listar_jobs(
    user_id: str = Query(..., description="UUID do usuário autenticado"),
    limit:   int = Query(20, ge=1, le=100),
    offset:  int = Query(0,  ge=0),
):
    client = get_supabase_admin_client()
    try:
        resp = (
            client.table("jobs")
            .select("*")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .range(offset, offset + limit - 1)
            .execute()
        )
        return resp.data or []
    except Exception as e:
        logger.error(f"Erro ao listar jobs: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao buscar jobs: {str(e)[:200]}",
        )
