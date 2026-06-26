"""
src/controllers/brain/get_info_video.py

Busca informações e gera títulos de vídeos do YouTube usando Brain IA.
"""

import asyncio
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import yt_dlp

# ── Configuração de Path ──────────────────────────────────────
ROOT_DIR = Path(__file__).resolve().parent.parent.parent.parent
sys.path.append(str(ROOT_DIR))

from src.services.brain_IA import Brain
from src.utils.logs import logger


class BrainVideoInfo:
    """
    Classe especializada para buscar informações de vídeos do YouTube
    e gerar títulos usando a Brain IA.
    """

    def __init__(self, url: Optional[str] = None) -> None:
        self.url = url
        self._brain = None

    @property
    def brain(self) -> Brain:
        """Lazy loading do Brain"""
        if self._brain is None:
            self._brain = Brain()
        return self._brain

    # ──────────────────────────────────────────────────────────────
    #  INFO BÁSICA DO VÍDEO
    # ──────────────────────────────────────────────────────────────

    async def get_info(self) -> Dict[str, Any]:
        """Retorna metadados do vídeo sem fazer download."""
        try:

            def _sync(url: str) -> Dict[str, Any]:
                ydl_opts = {
                    "quiet": True,
                    "no_warnings": True,
                    "extract_flat": False,
                }
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    return ydl.extract_info(url, download=False)

            info = await asyncio.to_thread(_sync, str(self.url))

            if not info:
                return {}

            description = info.get("description", "") or ""
            if len(description) > 1000:
                description = description[:1000] + "..."

            return {
                "title": info.get("title", ""),
                "duration": info.get("duration", 0),
                "uploader": info.get("uploader", ""),
                "view_count": info.get("view_count", 0),
                "description": description,
                "thumbnail": info.get("thumbnail", ""),
            }

        except Exception as e:
            logger.error(f"Erro ao obter informações do vídeo: {e}")
            raise Exception(f"Erro ao obter informações do vídeo: {e}")

    # ──────────────────────────────────────────────────────────────
    #  GERAÇÃO DE TÍTULOS
    # ──────────────────────────────────────────────────────────────

    async def create_titles(self, num_titles: int = 5) -> Dict[str, Any]:
        """
        Gera títulos virais usando a Brain IA.
        """
        try:
            info = await self.get_info()
            if not info:
                return {
                    "error": "Não foi possível obter informações do vídeo",
                    "video_title": "",
                    "titles": [],
                    "count": 0,
                    "success": False,
                }

            video_title = info.get("title", "Vídeo sem título")
            description = info.get("description", "")

            logger.info(f"Gerando {num_titles} títulos para: {video_title}")

            # Tenta gerar títulos com IA
            result = self.brain.generate_titles(
                video_title=video_title,
                description=description,
                count=num_titles,
                duration=info.get("duration", 0),
                uploader=info.get("uploader", ""),
            )

            titles = result.get("titles", [])

            # Se não conseguiu gerar, usa fallback
            if not titles:
                logger.info("Usando fallback de títulos")
                titles = self._fallback_titulos(video_title, num_titles)

            return {
                "success": True,
                "video_title": video_title,
                "titles": titles[:num_titles],
                "count": len(titles[:num_titles]),
            }

        except Exception as e:
            logger.error(f"Erro ao criar títulos: {e}")
            return {
                "error": str(e),
                "video_title": "Vídeo",
                "titles": [],
                "count": 0,
                "success": False,
            }

    # ──────────────────────────────────────────────────────────────
    #  FALLBACK
    # ──────────────────────────────────────────────────────────────

    def _fallback_titulos(self, video_title: str, count: int) -> List[str]:
        """Gera títulos de fallback sem IA"""
        templates = [
            f"{video_title}",
            f"🔥 {video_title}",
            f"{video_title} - Você precisa ver isso!",
            f"O que ninguém te contou sobre {video_title}",
            f"{video_title} - Os melhores momentos",
            f"Como {video_title} está mudando tudo",
            f"{video_title} - Resumo completo",
        ]

        titulos = []
        seen = set()

        for template in templates:
            if template.lower() not in seen:
                seen.add(template.lower())
                titulos.append(template)
            if len(titulos) >= count:
                break

        return titulos


# ──────────────────────────────────────────────────────────────────
#  CLASSE PRINCIPAL (compatibilidade)
# ──────────────────────────────────────────────────────────────────


class GetInfoVideo(BrainVideoInfo):
    """Classe para compatibilidade com o código existente."""

    pass


if __name__ == "__main__":
    test = BrainVideoInfo(url="https://youtu.be/zOK8jUXIWRQ?is=KxpzECvmh6xOLLq-")
    print(asyncio.run(test.create_titles(num_titles=3)))
