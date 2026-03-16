"""
src/services/storage_service.py

Responsável por:
  1. Fazer upload dos clipes para Supabase Storage (bucket: clips)
  2. Registrar cada clipe na tabela public.clips
  3. Atualizar o status do job na tabela public.jobs
  4. Gerar URL assinada (7 dias) para download pelo app

FIX: upload via httpx direto com timeout longo (10 min) para
     arquivos grandes (40–200 MB), contornando o timeout padrão
     do SDK supabase-py que estoura em ~60s.
"""

import mimetypes
import os
from pathlib import Path
from typing import List, Optional

import httpx

from src.database.supabase_client import (
    SUPABASE_URL,
    SUPABASE_SERVICE_KEY,
    SUPABASE_ANON_KEY,
    get_supabase_admin_client,
)
from src.utils.logs import logger

# URL assinada válida por 7 dias
SIGNED_URL_EXPIRES = 60 * 60 * 24 * 7

# Timeout para uploads grandes (10 minutos)
_UPLOAD_TIMEOUT = httpx.Timeout(
    connect=30,
    read=600,
    write=600,
    pool=30,
)

# Tamanho de chunk para leitura do arquivo (4 MB)
_CHUNK_SIZE = 4 * 1024 * 1024


def _get_service_key() -> str:
    """Retorna a service role key ou anon key como fallback."""
    return SUPABASE_SERVICE_KEY or SUPABASE_ANON_KEY


# ──────────────────────────────────────────────────────────────────
#  UPLOAD DIRETO VIA HTTPX (contorna timeout do SDK)
# ──────────────────────────────────────────────────────────────────

def _upload_via_httpx(
    clip_path: Path,
    storage_path: str,
    mime_type: str,
    bucket: str = "clips",
) -> bool:
    """
    Faz upload direto para a API REST do Supabase Storage via httpx,
    com timeout de 10 minutos — adequado para arquivos de até ~500 MB.
    Retorna True se bem-sucedido, False caso contrário.
    """
    url     = f"{SUPABASE_URL}/storage/v1/object/{bucket}/{storage_path}"
    headers = {
        "Authorization": f"Bearer {_get_service_key()}",
        "Content-Type":  mime_type,
        "Cache-Control": "3600",
        "x-upsert":      "true",
    }

    try:
        file_size = clip_path.stat().st_size
        logger.info(
            f"Iniciando upload httpx: {clip_path.name} "
            f"({file_size / (1024*1024):.1f} MB) → {bucket}/{storage_path}"
        )

        with open(clip_path, "rb") as f:
            with httpx.Client(timeout=_UPLOAD_TIMEOUT) as client:
                resp = client.put(url, content=f.read(), headers=headers)

        if resp.status_code in (200, 201):
            logger.info(f"Upload OK ({resp.status_code}): {storage_path}")
            return True
        else:
            logger.error(
                f"Upload falhou {resp.status_code}: {resp.text[:200]}"
            )
            return False

    except httpx.TimeoutException as e:
        logger.error(f"Timeout no upload de {clip_path.name}: {e}")
        return False
    except Exception as e:
        logger.error(f"Erro no upload de {clip_path.name}: {e}")
        return False


# ──────────────────────────────────────────────────────────────────
#  GERAR SIGNED URL
# ──────────────────────────────────────────────────────────────────

def _gerar_signed_url(storage_path: str, bucket: str = "clips") -> str:
    """
    Gera uma URL assinada válida por 7 dias via API REST do Supabase.
    Retorna a URL ou string vazia em caso de falha.
    """
    url     = f"{SUPABASE_URL}/storage/v1/object/sign/{bucket}/{storage_path}"
    headers = {
        "Authorization": f"Bearer {_get_service_key()}",
        "Content-Type":  "application/json",
    }
    try:
        with httpx.Client(timeout=httpx.Timeout(30)) as client:
            resp = client.post(url, json={"expiresIn": SIGNED_URL_EXPIRES}, headers=headers)

        if resp.status_code == 200:
            data       = resp.json()
            signed_url = data.get("signedURL") or data.get("signedUrl", "")
            if signed_url and not signed_url.startswith("http"):
                signed_url = f"{SUPABASE_URL}/storage/v1{signed_url}"
            logger.info(f"Signed URL gerada: {storage_path}")
            return signed_url
        else:
            logger.warning(
                f"Falha ao gerar signed URL ({resp.status_code}): {resp.text[:100]}"
            )
            return ""
    except Exception as e:
        logger.warning(f"Erro ao gerar signed URL: {e}")
        return ""


# ──────────────────────────────────────────────────────────────────
#  UPLOAD DE UM CLIPE (interface pública)
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

    storage_path = f"{user_id}/{job_id}/{clip_path.name}"
    mime_type    = mimetypes.guess_type(str(clip_path))[0] or "video/mp4"

    # Upload via httpx direto (timeout longo)
    ok = _upload_via_httpx(clip_path, storage_path, mime_type, bucket="clips")
    if not ok:
        return None

    # Gera signed URL
    signed_url = _gerar_signed_url(storage_path, bucket="clips")

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
        logger.info(f"Clip registrado no banco: {clip_id}")
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
      - Upload para Supabase Storage (via httpx, timeout 10 min)
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
            message=f"Enviando clipe {i}/{total} para a nuvem... ({size_mb:.0f} MB)",
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
