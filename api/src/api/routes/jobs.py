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
from src.utils.logs import logger

router = APIRouter(prefix="/jobs", tags=["Jobs"])

# ──────────────────────────────────────────────────────────────────
#  MEMORY STORE (OFFLINE MODE)
# ──────────────────────────────────────────────────────────────────

# Armazenamento em memória para modo offline
_JOBS_MEMORY: Dict[str, Dict[str, Any]] = {}


# ──────────────────────────────────────────────────────────────────
#  SCHEMAS
# ──────────────────────────────────────────────────────────────────


class JobCreateRequest(BaseModel):
    user_id: str
    source_type: str = "youtube"  # "youtube" | "upload"
    source_url: Optional[str] = None
    num_clips: int = 3
    clip_duration: int = 90
    tracking: bool = True


class JobResponse(BaseModel):
    id: str
    user_id: str
    status: str
    source_type: str
    source_url: Optional[str]
    num_clips: int
    clip_duration: int
    tracking: bool


# ──────────────────────────────────────────────────────────────────
#  FUNÇÕES AUXILIARES
# ──────────────────────────────────────────────────────────────────


def _get_supabase_client():
    """
    Tenta obter o cliente Supabase.
    Se falhar, retorna None e loga o erro.
    """
    try:
        from src.database.supabase_client import get_supabase_admin_client
        return get_supabase_admin_client()
    except Exception as e:
        logger.warning(f"⚠️ Supabase indisponível, usando modo offline: {e}")
        return None


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
    
    Modo OFFLINE: Se Supabase não estiver disponível, armazena em memória.
    """
    job_id = str(uuid.uuid4())
    
    # ── Tenta usar Supabase primeiro ──
    client = _get_supabase_client()
    
    if client is not None:
        try:
            resp = (
                client.table("jobs")
                .insert(
                    {
                        "id": job_id,
                        "user_id": body.user_id,
                        "status": "pending",
                        "source_type": body.source_type,
                        "source_url": body.source_url,
                        "num_clips": body.num_clips,
                        "clip_duration": body.clip_duration,
                        "tracking": body.tracking,
                        "progress": 0,
                        "message": "Aguardando início do pipeline.",
                    }
                )
                .execute()
            )

            if not resp.data:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Banco não retornou dados após inserção do job.",
                )

            job = resp.data[0]
            logger.info(f"✅ Job criado no Supabase: {job_id} | user: {body.user_id}")
            return job
            
        except Exception as e:
            logger.warning(f"⚠️ Falha ao criar job no Supabase, usando fallback em memória: {e}")
    
    # ── FALLBACK: Modo offline (memória) ──
    logger.info(f"📦 Criando job em memória (offline): {job_id}")
    
    job = {
        "id": job_id,
        "user_id": body.user_id,
        "status": "pending",
        "source_type": body.source_type,
        "source_url": body.source_url,
        "num_clips": body.num_clips,
        "clip_duration": body.clip_duration,
        "tracking": body.tracking,
        "progress": 0,
        "message": "Aguardando início do pipeline (offline mode).",
        "created_at": str(uuid.uuid4()),  # Placeholder
    }
    
    # Armazena em memória
    _JOBS_MEMORY[job_id] = job
    
    # Retorna o job criado (sem dados do Supabase)
    logger.info(f"✅ Job criado em memória: {job_id} | user: {body.user_id}")
    
    # Converte para o formato esperado pela resposta
    return {
        "id": job["id"],
        "user_id": job["user_id"],
        "status": job["status"],
        "source_type": job["source_type"],
        "source_url": job["source_url"],
        "num_clips": job["num_clips"],
        "clip_duration": job["clip_duration"],
        "tracking": job["tracking"],
        "progress": job["progress"],
        "message": job["message"],
    }


# ──────────────────────────────────────────────────────────────────
#  LISTAR JOBS DO USUÁRIO
# ──────────────────────────────────────────────────────────────────


@router.get(
    "",
    summary="Lista jobs do usuário",
)
async def listar_jobs(
    user_id: str = Query(..., description="UUID do usuário autenticado"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """
    Lista jobs do usuário.
    Modo OFFLINE: Busca da memória se Supabase não estiver disponível.
    """
    # ── Tenta usar Supabase primeiro ──
    client = _get_supabase_client()
    
    if client is not None:
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
            logger.warning(f"⚠️ Falha ao listar jobs do Supabase, usando fallback em memória: {e}")
    
    # ── FALLBACK: Modo offline (memória) ──
    logger.info(f"📦 Listando jobs em memória (offline) para user: {user_id}")
    
    # Filtra jobs do usuário
    user_jobs = [
        job for job in _JOBS_MEMORY.values()
        if job.get("user_id") == user_id
    ]
    
    # Ordena por created_at (decrescente) - usando o ID como fallback
    user_jobs.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    
    # Aplica paginação
    paginated = user_jobs[offset:offset + limit]
    
    # Remove campos internos se necessário
    result = []
    for job in paginated:
        result.append({
            "id": job.get("id"),
            "user_id": job.get("user_id"),
            "status": job.get("status"),
            "source_type": job.get("source_type"),
            "source_url": job.get("source_url"),
            "num_clips": job.get("num_clips"),
            "clip_duration": job.get("clip_duration"),
            "tracking": job.get("tracking"),
            "progress": job.get("progress", 0),
            "message": job.get("message", ""),
            "created_at": job.get("created_at", ""),
        })
    
    logger.info(f"✅ {len(result)} jobs encontrados em memória para user: {user_id}")
    return result


# ──────────────────────────────────────────────────────────────────
#  FUNÇÃO PARA OBTER JOB POR ID (UTILITÁRIA)
# ──────────────────────────────────────────────────────────────────


def get_job_by_id(job_id: str) -> Optional[Dict[str, Any]]:
    """
    Obtém um job pelo ID (primeiro do Supabase, depois da memória).
    Função utilitária para uso em outros endpoints.
    """
    # Tenta Supabase
    client = _get_supabase_client()
    
    if client is not None:
        try:
            resp = client.table("jobs").select("*").eq("id", job_id).single().execute()
            return resp.data
        except Exception:
            pass
    
    # Busca na memória
    return _JOBS_MEMORY.get(job_id)


# ──────────────────────────────────────────────────────────────────
#  FUNÇÃO PARA ATUALIZAR JOB (UTILITÁRIA)
# ──────────────────────────────────────────────────────────────────


def update_job(job_id: str, **kwargs) -> Optional[Dict[str, Any]]:
    """
    Atualiza um job (primeiro no Supabase, depois na memória).
    Função utilitária para uso em outros endpoints.
    """
    # Tenta Supabase
    client = _get_supabase_client()
    
    if client is not None:
        try:
            client.table("jobs").update(kwargs).eq("id", job_id).execute()
        except Exception as e:
            logger.warning(f"⚠️ Falha ao atualizar job no Supabase: {e}")
    
    # Atualiza na memória
    if job_id in _JOBS_MEMORY:
        _JOBS_MEMORY[job_id].update(kwargs)
        return _JOBS_MEMORY[job_id]
    
    return None


# ──────────────────────────────────────────────────────────────────
#  ENDPOINT DE DEBUG (OPCIONAL)
# ──────────────────────────────────────────────────────────────────


@router.get("/debug", summary="Debug - lista todos os jobs em memória", include_in_schema=False)
async def debug_list_all_jobs():
    """Endpoint para debug - lista todos os jobs em memória."""
    return {
        "total": len(_JOBS_MEMORY),
        "jobs": list(_JOBS_MEMORY.values())
    }