"""
GET /api/info        → informações do vídeo (título, duração, views…)
POST /api/info/titles → gera títulos virais com a Brain IA
"""

from fastapi import APIRouter, HTTPException, status

from src.api.schemas import (
    TitlesRequest,
    TitlesResponse,
    VideoInfoRequest,
    VideoInfoResponse,
)
from src.controllers.youtube.get_info_video import GetInfoVideo
from src.utils.logs import logger

router = APIRouter(prefix="/info", tags=["Info"])


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
        fetcher = GetInfoVideo(url=body.url)
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


@router.post(
    "/titles",
    response_model=TitlesResponse,
    summary="Gera títulos virais usando a Brain IA",
)
async def generate_titles(body: TitlesRequest):
    """
    Obtém as informações do vídeo e usa a Brain IA para sugerir títulos.

    Estratégia com fallback automático:
    1. `brain.generate_titles()` — se existir no Brain
    2. `brain.encontrar_melhores_momentos()` — extrai títulos dos momentos
    3. Variações simples do título original (fallback sem IA)
    """
    try:
        fetcher = GetInfoVideo(url=body.url)
        result  = await fetcher.create_titles(num_titles=body.count)

        if "error" in result:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=result["error"],
            )

        return TitlesResponse(
            video_title=result["video_title"],
            titles=result["titles"],
            count=result["count"],
        )

    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Erro ao gerar títulos: {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        )
