"""
src/api/routes/info.py

Rotas para informações de vídeos do YouTube.
─────────────────────────────────────────────────────────────
GET  /api/info        → informações do vídeo (título, duração, views…)
POST /api/info/titles → gera títulos virais com a Brain IA
─────────────────────────────────────────────────────────────
"""

from fastapi import APIRouter, HTTPException, status
from src.api.schemas import (
    TitlesRequest,
    TitlesResponse,
    VideoInfoRequest,
    VideoInfoResponse,
)
from src.controllers.brain import BrainVideoInfo
from src.utils.logs import logger

router = APIRouter(prefix="/info", tags=["Info"])


# ──────────────────────────────────────────────────────────────
#  POST /api/info — Informações do vídeo
# ──────────────────────────────────────────────────────────────

@router.post(
    "/",
    response_model=VideoInfoResponse,
    summary="Retorna informações do vídeo do YouTube",
)
async def get_video_info(body: VideoInfoRequest):
    """
    Consulta título, duração, canal e descrição sem fazer download.
    """
    try:
        fetcher = BrainVideoInfo(url=body.url)
        info = await fetcher.get_info()

        if not info:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Não foi possível obter informações do vídeo.",
            )

        return VideoInfoResponse(**info)

    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Erro ao obter info: {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        )


# ──────────────────────────────────────────────────────────────
#  POST /api/info/titles — Geração de títulos com IA
# ──────────────────────────────────────────────────────────────

@router.post(
    "/titles",
    response_model=TitlesResponse,
    summary="Gera títulos virais usando a Brain IA",
)
async def generate_titles(body: TitlesRequest):
    """
    Obtém as informações do vídeo e usa a Brain IA para sugerir títulos.
    """
    try:
        fetcher = BrainVideoInfo(url=body.url)
        result = await fetcher.create_titles(num_titles=body.count)

        # Verifica se houve erro
        if "error" in result:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=result["error"],
            )

        # Log para debug
        logger.info(f"Resultado da geração de títulos: {result}")

        # Verifica se os campos necessários existem
        video_title = result.get("video_title", "Vídeo sem título")
        titles = result.get("titles", [])
        count = result.get("count", len(titles))

        # Se não tiver títulos, retorna erro
        if not titles:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Não foi possível gerar títulos para este vídeo.",
            )

        return TitlesResponse(
            video_title=video_title,
            titles=titles,
            count=count,
        )

    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Erro ao gerar títulos: {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        )