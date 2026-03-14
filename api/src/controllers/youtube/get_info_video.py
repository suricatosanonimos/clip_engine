"""
src/controllers/youtube/get_info_video.py

Busca informações e gera títulos de vídeos do YouTube.
Correção: Brain não possui generate_titles — títulos são gerados via
encontrar_melhores_momentos() ou diretamente pelo modelo de linguagem
já embutido no Brain (dependendo da sua implementação).
"""

import asyncio
from typing import Any, Dict, List, Optional

import yt_dlp

from src.services.brain_IA import Brain
from src.utils.logs import logger


class GetInfoVideo:
    def __init__(self, url: Optional[str] = None) -> None:
        self.url = url

    # ──────────────────────────────────────────────────────────────
    #  INFO BÁSICA
    # ──────────────────────────────────────────────────────────────

    async def get_info(self) -> Dict[str, Any]:
        """Retorna metadados do vídeo sem fazer download."""
        try:
            def _sync(url: str) -> Dict[str, Any]:
                with yt_dlp.YoutubeDL({"quiet": True}) as ydl:
                    return ydl.extract_info(url, download=False)  # type: ignore

            info = await asyncio.to_thread(_sync, str(self.url))

            if not info:
                return {}

            description = info.get("description", "") or ""
            if len(description) > 1000:
                description = description[:1000] + "..."

            return {
                "title":       info.get("title", ""),
                "duration":    info.get("duration", 0),
                "uploader":    info.get("uploader", ""),
                "view_count":  info.get("view_count", 0),
                "description": description,
            }

        except Exception as e:
            raise Exception(f"Erro ao obter informações do vídeo: {e}")

    # ──────────────────────────────────────────────────────────────
    #  GERAÇÃO DE TÍTULOS
    # ──────────────────────────────────────────────────────────────

    async def create_titles(self, num_titles: int = 5) -> Dict[str, Any]:
        """
        Gera títulos virais usando a Brain IA.

        Estratégia:
          1. Tenta chamar brain.generate_titles() se existir.
          2. Fallback: usa brain.encontrar_melhores_momentos() passando
             a descrição como transcrição fake para extrair sugestões.
          3. Fallback final: retorna títulos baseados no título original.
        """
        try:
            info = await self.get_info()
            if not info:
                return {"error": "Não foi possível obter informações do vídeo"}

            brain = Brain()
            titles: List[str] = []

            # ── Tentativa 1: método generate_titles (pode existir em versões futuras)
            if hasattr(brain, "generate_titles"):
                try:
                    titles = brain.generate_titles(info, count=num_titles)
                except Exception as e:
                    logger.warning(f"generate_titles falhou: {e}")

            # ── Tentativa 2: encontrar_melhores_momentos com descrição como contexto
            if not titles and hasattr(brain, "encontrar_melhores_momentos"):
                try:
                    descricao = info.get("description", "") or info.get("title", "")
                    # Monta segmentos fake para a Brain processar o texto
                    segmentos_fake = [
                        {"start": 0.0, "end": 10.0, "text": descricao}
                    ]
                    resultado = brain.encontrar_melhores_momentos(
                        segmentos_fake, duracao_total=10.0
                    )

                    # Extrai títulos do resultado da IA
                    if isinstance(resultado, dict):
                        # Se Brain retornar campo "titles" ou "titulos"
                        titles = (
                            resultado.get("titles")
                            or resultado.get("titulos")
                            or []
                        )
                        # Se não, monta a partir dos momentos sugeridos
                        if not titles:
                            momentos = resultado.get("momentos", [])
                            titles = [
                                m.get("titulo") or m.get("title") or m.get("text", "")
                                for m in momentos
                                if m.get("titulo") or m.get("title") or m.get("text")
                            ]
                    elif isinstance(resultado, list):
                        titles = [
                            item.get("titulo") or item.get("title") or str(item)
                            for item in resultado
                        ]
                except Exception as e:
                    logger.warning(f"encontrar_melhores_momentos para títulos falhou: {e}")

            # ── Fallback final: variações simples do título original
            if not titles:
                titulo_original = info.get("title", "Vídeo")
                titles = _gerar_titulos_fallback(titulo_original, num_titles)
                logger.info("Usando fallback de títulos (Brain IA indisponível).")

            # Limita ao número pedido
            titles = [t for t in titles if t][:num_titles]

            return {
                "success":     True,
                "video_title": info.get("title", ""),
                "titles":      titles,
                "count":       len(titles),
            }

        except Exception as e:
            raise Exception(f"Erro ao criar títulos: {e}")


# ──────────────────────────────────────────────────────────────────
#  FALLBACK — títulos simples sem IA
# ──────────────────────────────────────────────────────────────────

def _gerar_titulos_fallback(titulo: str, count: int) -> List[str]:
    """
    Gera variações simples do título quando a Brain IA não retorna nada.
    Substitua por uma chamada real quando o método generate_titles
    for implementado no Brain.
    """
    templates = [
        f"{titulo}",
        f"🔥 {titulo}",
        f"{titulo} | Resumo completo",
        f"Você precisa ver: {titulo}",
        f"{titulo} — os melhores momentos",
        f"O que ninguém te conta sobre: {titulo}",
        f"{titulo} | Análise detalhada",
        f"IMPERDÍVEL: {titulo}",
    ]
    return templates[:count]
