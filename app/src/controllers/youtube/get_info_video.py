import asyncio
from typing import Any, Dict, Optional

import yt_dlp
from src.services.brain_IA import Brain


class GetInfoVideo:
    def __init__(self, url: Optional[str] = None) -> None:
        self.url = url

    async def get_info(self) -> Dict[str, Any]:
        try:

            def get_info_sync(url: str) -> Dict[str, Any]:
                with yt_dlp.YoutubeDL({"quiet": True}) as ydl:
                    return ydl.extract_info(url, download=False)  # type: ignore

            info = await asyncio.to_thread(get_info_sync, str(self.url))

            if info:
                # Processa a descrição
                description = info.get("description", "")
                if description and len(description) > 1000:
                    description = description[:1000] + "..."

                return {
                    "title": info.get("title", ""),
                    "duration": info.get("duration", 0),
                    "uploader": info.get("uploader", ""),
                    "view_count": info.get("view_count", 0),
                    "description": description,
                }
            else:
                return {}

        except Exception as e:
            raise Exception(f"Erro ao obter informações do vídeo: {str(e)}")

    async def create_titles(self, num_titles: int = 5) -> Dict[str, Any]:
        """
        Cria títulos para o vídeo usando IA

        Args:
            num_titles: Número de títulos para gerar (padrão: 5)
        """
        try:
            # Obtém informações completas do vídeo
            info = await self.get_info()

            if not info:
                return {"error": "Não foi possível obter informações do vídeo"}

            # Inicializa a Brain IA
            brain_ia = Brain()

            # Passa o dicionário COMPLETO, não apenas a description
            titles = brain_ia.generate_titles(info, count=num_titles)

            return {
                "success": True,
                "video_title": info.get("title", ""),
                "titles": titles,
                "count": len(titles),
            }

        except Exception as e:
            raise Exception(f"Erro ao criar títulos: {str(e)}")
