"""
src/services/storage_service.py

Responsável por:
  1. Fazer upload dos clipes para Supabase Storage (bucket: clips)
  2. Registrar cada clipe na tabela public.clips
  3. Atualizar o status do job na tabela public.jobs
  4. Gerar URL assinada (7 dias) para download pelo app
"""

import mimetypes
from pathlib import Path
from typing import List, Optional

from src.database.supabase_client import get_supabase_admin_client
from src.utils.logs import logger

# URL assinada válida por 7 dias
SIGNED_URL_EXPIRES = 60 * 60 * 24 * 7


# ──────────────────────────────────────────────────────────────────
#  UPLOAD DE UM CLIPE
# ──────────────────────────────────────────────────────────────────

def upload_clipe_storage(
    clip_path: Path,
    user_id: str,
    job_id: str,
    clip_index: int,
) -> Optional[dict]:
    """
    Faz upload de um clipe para clips/{user_id}/{job_id}/{filename}.
    Retorna {"storage_path": ..., "signed_url": ...} ou None.
    """
    if not clip_path.exists():
        logger.error(f"Clipe não encontrado: {clip_path}")
        return None

    client       = get_supabase_admin_client()
    storage_path = f"{user_id}/{job_id}/{clip_path.name}"
    mime_type    = mimetypes.guess_type(str(clip_path))[0] or "video/mp4"

    try:
        with open(clip_path, "rb") as f:
            client.storage.from_("clips").upload(
                path=storage_path,
                file=f,
                file_options={
                    "content-type":  mime_type,
                    "cache-control": "3600",
                    "upsert":        "true",
                },
            )
        logger.info(f"Upload OK → {storage_path}")
    except Exception as e:
        logger.error(f"Erro no upload de {clip_path.name}: {e}")
        return None

    # Gera URL assinada
    try:
        resp       = client.storage.from_("clips").create_signed_url(
            storage_path, SIGNED_URL_EXPIRES
        )
        signed_url = resp.get("signedURL") or resp.get("signed_url", "")
    except Exception as e:
        logger.warning(f"Não foi possível gerar signed URL: {e}")
        signed_url = ""

    return {"storage_path": storage_path, "signed_url": signed_url}


# ──────────────────────────────────────────────────────────────────
#  REGISTRAR CLIPE NO BANCO
# ──────────────────────────────────────────────────────────────────

def registrar_clip_banco(
    user_id: str,
    job_id: str,
    clip_index: int,
    filename: str,
    storage_path: str,
    signed_url: str,
    size_mb: float,
    score: float = 0.0,
    motivo: Optional[str] = None,
) -> Optional[str]:
    """
    Insere registro em public.clips.
    Retorna o UUID do clip criado, ou None em caso de erro.
    """
    client = get_supabase_admin_client()
    try:
        resp = client.table("clips").insert({
            "user_id":      user_id,
            "job_id":       job_id,
            "clip_index":   clip_index,
            "filename":     filename,
            "storage_path": storage_path,
            "public_url":   signed_url,
            "size_mb":      round(size_mb, 2),
            "score":        score,
            "motivo":       motivo or "Clipe gerado automaticamente.",
        }).execute()
        clip_id = resp.data[0]["id"] if resp.data else None
        logger.info(f"Clip registrado: {clip_id}")
        return clip_id
    except Exception as e:
        logger.error(f"Erro ao registrar clip no banco: {e}")
        return None


# ──────────────────────────────────────────────────────────────────
#  ATUALIZAR JOB
# ──────────────────────────────────────────────────────────────────

def atualizar_job_status(
    job_id: str,
    status: str,
    progress: float = 0.0,
    message: str = "",
    error: Optional[str] = None,
    video_title: Optional[str] = None,
):
    """Atualiza o status do job na tabela public.jobs."""
    client = get_supabase_admin_client()
    try:
        dados = {
            "status":   status,
            "progress": round(progress * 100, 1),  # banco guarda 0–100
            "message":  message,
        }
        if error:
            dados["error"] = error
        if video_title:
            dados["video_title"] = video_title

        client.table("jobs").update(dados).eq("id", job_id).execute()
    except Exception as e:
        logger.warning(f"Erro ao atualizar job {job_id}: {e}")


# ──────────────────────────────────────────────────────────────────
#  PROCESSAR E SALVAR TODOS OS CLIPES
# ──────────────────────────────────────────────────────────────────

def processar_e_salvar_clips(
    clips_gerados: list,
    user_id: str,
    job_id: str,
    task_id: str,
) -> list:
    """
    Itera sobre os clipes gerados pelo VideoProcessor:
      - Upload para Supabase Storage
      - Registro na tabela clips
      - Retorna lista de dicts para ClipResult

    Clipes com falha no upload são pulados sem abortar o processo.
    """
    from src.api.task_store import update_task
    from src.api.schemas import TaskStatus

    resultados = []
    total      = len(clips_gerados)

    for i, cp in enumerate(clips_gerados, start=1):
        cp = Path(cp)
        if not cp.exists():
            logger.warning(f"[{task_id}] Clipe ausente no disco: {cp}")
            continue

        size_mb = cp.stat().st_size / (1024 * 1024)

        # Progresso gradual entre 0.85 → 0.98 durante os uploads
        progresso = 0.85 + (i / total) * 0.13
        update_task(
            task_id,
            status=TaskStatus.ANALYZING,
            progress=progresso,
            message=f"Salvando clipe {i}/{total} na nuvem...",
        )

        # 1. Upload para Storage
        resultado = upload_clipe_storage(cp, user_id, job_id, i)
        if not resultado:
            logger.warning(f"[{task_id}] Upload falhou para {cp.name}, pulando.")
            continue

        # 2. Registro no banco
        clip_id = registrar_clip_banco(
            user_id=user_id,
            job_id=job_id,
            clip_index=i,
            filename=cp.name,
            storage_path=resultado["storage_path"],
            signed_url=resultado["signed_url"],
            size_mb=size_mb,
        )

        resultados.append({
            "index":        i,
            "clip_index":   i,
            "filename":     cp.name,
            "path":         str(cp),
            "size_mb":      round(size_mb, 2),
            "storage_path": resultado["storage_path"],
            "public_url":   resultado["signed_url"],
            "clip_id":      clip_id,
        })

    logger.info(f"[{task_id}] {len(resultados)}/{total} clipes salvos no Supabase.")
    return resultados
