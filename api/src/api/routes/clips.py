"""
GET  /api/clips                      → lista clipes do usuário logado
GET  /api/clips/{clip_id}            → detalhes de um clipe
POST /api/clips/{clip_id}/refresh-url → renova signed URL (7 dias)
"""

from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query, status

from src.api.schemas import ClipGaleria
from src.database.supabase_client import get_supabase_admin_client
from src.utils.logs import logger

router = APIRouter(prefix="/clips", tags=["Clips"])

SIGNED_URL_EXPIRES = 60 * 60 * 24 * 7   # 7 dias


@router.get(
    "/",
    response_model=List[ClipGaleria],
    summary="Lista clipes prontos do usuário",
)
async def listar_clips(
    user_id: str           = Query(...,    description="UUID do usuário autenticado"),
    job_id:  Optional[str] = Query(None,  description="Filtrar por job específico"),
    limit:   int           = Query(50,    ge=1, le=200),
    offset:  int           = Query(0,     ge=0),
):
    """
    Retorna os clipes do usuário ordenados do mais recente para o mais antigo.
    Usado pela aba Galeria do app para montar a timeline.
    """
    client = get_supabase_admin_client()
    try:
        query = (
            client.table("clips")
            .select("*")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .range(offset, offset + limit - 1)
        )
        if job_id:
            query = query.eq("job_id", job_id)

        resp  = query.execute()
        clips = resp.data or []

    except Exception as e:
        logger.error(f"Erro ao listar clips: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao buscar clipes: {e}",
        )

    return [
        ClipGaleria(
            id=c["id"],
            job_id=c["job_id"],
            filename=c["filename"],
            storage_path=c["storage_path"],
            public_url=c.get("public_url"),
            size_mb=c.get("size_mb"),
            clip_index=c.get("clip_index", 0),
            score=c.get("score", 0.0),
            motivo=c.get("motivo"),
            created_at=str(c.get("created_at", "")),
        )
        for c in clips
    ]


@router.get(
    "/{clip_id}",
    response_model=ClipGaleria,
    summary="Detalhes de um clipe específico",
)
async def detalhe_clip(clip_id: str):
    client = get_supabase_admin_client()
    try:
        resp = client.table("clips").select("*").eq("id", clip_id).single().execute()
        c    = resp.data
    except Exception:
        raise HTTPException(status_code=404, detail=f"Clipe '{clip_id}' não encontrado.")

    return ClipGaleria(
        id=c["id"], job_id=c["job_id"], filename=c["filename"],
        storage_path=c["storage_path"], public_url=c.get("public_url"),
        size_mb=c.get("size_mb"), clip_index=c.get("clip_index", 0),
        score=c.get("score", 0.0), motivo=c.get("motivo"),
        created_at=str(c.get("created_at", "")),
    )


@router.post(
    "/{clip_id}/refresh-url",
    summary="Renova a URL de download (válida por 7 dias)",
)
async def renovar_url(clip_id: str):
    """Gera nova signed URL e atualiza no banco. Use quando a URL expirar."""
    client = get_supabase_admin_client()

    try:
        resp = client.table("clips").select("storage_path").eq("id", clip_id).single().execute()
        storage_path = resp.data["storage_path"]
    except Exception:
        raise HTTPException(status_code=404, detail=f"Clipe '{clip_id}' não encontrado.")

    try:
        resultado  = client.storage.from_("clips").create_signed_url(
            storage_path, SIGNED_URL_EXPIRES
        )
        signed_url = resultado.get("signedURL") or resultado.get("signed_url", "")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Não foi possível renovar a URL: {e}")

    try:
        client.table("clips").update({"public_url": signed_url}).eq("id", clip_id).execute()
    except Exception as e:
        logger.warning(f"URL renovada mas não salva no banco: {e}")

    return {"clip_id": clip_id, "public_url": signed_url, "expires_in_days": 7}
