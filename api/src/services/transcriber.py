"""
src/services/transcriber.py

Gera legendas word-by-word via Whisper e renderiza no vídeo com FFmpeg/ASS.
Versão OTIMIZADA - mantém qualidade e velocidade.
"""

import asyncio
import json
import logging
import os
import re
import shutil
import subprocess
import sys
from datetime import timedelta
from pathlib import Path
from typing import Dict, List, Optional

# ── Configuração de Path ──────────────────────────────────────
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT_DIR))

from src.controllers.whisper.model import model
from src.utils.subtitle_constants import *

# ── Logger ──────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


class SubtitleGenerator:
    """
    Classe responsável por gerar legendas word-by-word em vídeos.

    Fluxo:
        1. Extrai informações do vídeo (duração, resolução)
        2. Transcreve o áudio com Whisper (palavra por palavra)
        3. Gera arquivo .ass com legendas estilizadas
        4. Renderiza as legendas no vídeo com FFmpeg
    """

    def __init__(
        self,
        ffmpeg_path: str = "ffmpeg",
        ffprobe_path: Optional[str] = None,
        use_gpu: bool = False,
        cor_legenda: str = DEFAULT_COR,
        fast_mode: bool = True,
    ):
        """
        Inicializa o gerador de legendas.

        Args:
            ffmpeg_path: Caminho do executável FFmpeg
            ffprobe_path: Caminho do executável FFprobe
            use_gpu: Se True, usa GPU para transcrição (mais rápido)
            cor_legenda: Cor das legendas (white, yellow, blue, green)
            fast_mode: Se True, usa presets rápidos no FFmpeg
        """
        # ── Configuração de executáveis ──
        self.ffmpeg_path = ffmpeg_path
        self.ffprobe_path = ffprobe_path or shutil.which("ffprobe") or "ffprobe"
        self.use_gpu = use_gpu
        self.fast_mode = fast_mode

        # ── Configuração de cores ──
        # Normaliza o nome da cor para a chave interna
        cor_normalizada = COR_MAP.get(cor_legenda.lower(), DEFAULT_COR)
        self.cor_legenda = cor_normalizada
        self.cor_primary = COLORS[cor_normalizada]  # Cor principal da legenda

        # Cor de destaque para palavras longas (amarelo ou branco)
        self.cor_destaque = (
            COLORS["yellow"] if cor_normalizada != "yellow" else COLORS["white"]
        )

        # ── Diretórios de saída ──
        self.output_dir = ROOT_DIR / "processed_videos"
        self.final_clips_dir = self.output_dir / "final_clips"
        self.final_clips_dir.mkdir(parents=True, exist_ok=True)

        # ── Cache do Whisper ──
        self.cache_dir = os.path.expanduser("~/.cache/whisper-models/")
        os.makedirs(self.cache_dir, exist_ok=True)

        # ── Modo offline (evita downloads desnecessários) ──
        # os.environ["HF_HUB_OFFLINE"] = "1"
        # os.environ["TRANSFORMERS_OFFLINE"] = "1"

        # ── Compila padrões regex para censura e emojis ──
        self._compile_patterns()

        logger.info(
            f"SubtitleGenerator inicializado: cor={self.cor_legenda}, fast_mode={fast_mode}"
        )

    # ──────────────────────────────────────────────────────────────
    #  PADRÕES REGEX (Censura e Emojis)
    # ──────────────────────────────────────────────────────────────

    def _compile_patterns(self):
        """
        Compila padrões regex para:
            - Censura de palavras ofensivas (BAD_WORDS)
            - Inserção de emojis contextuais (EMOJI_WORDS)
        """
        # ── Palavras ofensivas (censura) ──
        self.bad_words_map = {}
        bad_patterns = []
        for bad, fixed in BAD_WORDS.items():
            bad_patterns.append(rf"\b{re.escape(bad)}\b")
            self.bad_words_map[bad.lower()] = fixed
        self.bad_words_pattern = (
            re.compile("|".join(bad_patterns), re.IGNORECASE) if bad_patterns else None
        )

        # ── Emojis contextuais ──
        self.emoji_map = {}
        emoji_patterns = []
        for word, emoji in EMOJI_WORDS.items():
            emoji_patterns.append(rf"\b{re.escape(word)}\b")
            self.emoji_map[word.lower()] = emoji
        self.emoji_pattern = (
            re.compile("|".join(emoji_patterns), re.IGNORECASE)
            if emoji_patterns
            else None
        )

    # ──────────────────────────────────────────────────────────────
    #  PROCESSAMENTO DE TEXTO
    # ──────────────────────────────────────────────────────────────

    def _process_text(self, text: str) -> str:
        """
        Processa o texto aplicando:
            1. Inserção de emojis contextuais
            2. Censura de palavras ofensivas
            3. Remoção de emojis duplicados

        Args:
            text: Texto original

        Returns:
            Texto processado
        """
        # ── Aplica emojis ──
        if self.emoji_pattern:
            text = self.emoji_pattern.sub(
                lambda m: f"{m.group(0)} {self.emoji_map.get(m.group(0).lower(), '')}",
                text,
            )

        # ── Aplica censura ──
        if self.bad_words_pattern:
            text = self.bad_words_pattern.sub(
                lambda m: self.bad_words_map.get(m.group(0).lower(), m.group(0)),
                text,
            )

        # ── Remove emojis duplicados ──
        text = re.sub(r"([❤️🔥😊✨😂🚀💪💰🎯])\s+\1", r"\1", text)

        return text

    # ──────────────────────────────────────────────────────────────
    #  FORMATAÇÃO DE TEMPO (ASS)
    # ──────────────────────────────────────────────────────────────

    def _format_time_ass(self, seconds: float) -> str:
        """
        Formata tempo no formato ASS: H:MM:SS.CS

        Args:
            seconds: Tempo em segundos

        Returns:
            String formatada para ASS
        """
        td = timedelta(seconds=seconds)
        total = int(td.total_seconds())
        h = total // 3600
        m = (total % 3600) // 60
        s = total % 60
        cs = int(td.microseconds / 10000)  # Centésimos de segundo
        return f"{h}:{m:02d}:{s:02d}.{cs:02d}"

    # ──────────────────────────────────────────────────────────────
    #  HEADER ASS (ESTILOS)
    # ──────────────────────────────────────────────────────────────

    def _generate_ass_header(self, width: int, height: int) -> str:
        """
        Gera o cabeçalho do arquivo .ass com os estilos configurados.

        Args:
            width: Largura do vídeo
            height: Altura do vídeo

        Returns:
            Cabeçalho ASS completo
        """
        # ── Tamanhos dinâmicos baseados na resolução ──
        font_size = int(height * 0.08)  # 8% da altura
        margin_vertical = int(height * 0.25)  # 25% da altura (posição)
        outline_size = max(2, int(font_size * 0.1))  # Borda proporcional

        return f"""[Script Info]
ScriptType: v4.00+
PlayResX: {width}
PlayResY: {height}
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Impact,{font_size},{self.cor_primary},&H000000FF,{COLORS['black']},&H00000000,-1,0,0,0,100,100,2,0,1,{outline_size},0,2,30,30,{margin_vertical},1
"""

    # ──────────────────────────────────────────────────────────────
    #  FFMPEG HELPERS
    # ──────────────────────────────────────────────────────────────

    async def get_video_resolution(self, path: Path) -> tuple:
        """
        Obtém a resolução do vídeo usando FFprobe.

        Args:
            path: Caminho do vídeo

        Returns:
            Tupla (width, height)
        """
        cmd = [
            self.ffprobe_path,
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=width,height",
            "-of",
            "json",
            str(path),
        ]
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        data = json.loads(stdout)
        return data["streams"][0]["width"], data["streams"][0]["height"]

    async def get_video_duration(self, path: Path) -> float:
        """
        Obtém a duração do vídeo usando FFprobe.

        Args:
            path: Caminho do vídeo

        Returns:
            Duração em segundos
        """
        cmd = [
            self.ffprobe_path,
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "json",
            str(path),
        ]
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        data = json.loads(stdout)
        return float(data["format"]["duration"])

    # ──────────────────────────────────────────────────────────────
    #  TRANSCRIÇÃO (WHISPER)
    # ──────────────────────────────────────────────────────────────

    async def transcribe_word_by_word(self, path: Path) -> List[Dict]:
        """
        Transcreve o áudio do vídeo usando Whisper com timestamps por palavra.

        Args:
            path: Caminho do arquivo de áudio (.wav) ou vídeo

        Returns:
            Lista de dicionários com: start, end, text
        """
        logger.info(f"Transcrevendo: {path.name}")
        loop = asyncio.get_event_loop()

        # ── Carrega o modelo Whisper (lazy loading) ──
        whisper_instance = model()

        # ── Executa a transcrição em thread separada ──
        segments, _ = await loop.run_in_executor(
            None,
            lambda: whisper_instance.transcribe(
                str(path),
                beam_size=5,  # Melhor qualidade
                word_timestamps=True,  # Timestamps por palavra
                best_of=5,  # Melhor resultado
                language="pt",  # Português
                initial_prompt="Áudio em português do Brasil",
                temperature=0.0,  # Determinístico
                condition_on_previous_text=False,  # Evita repetições
            ),
        )

        # ── Processa os segmentos e extrai palavras ──
        word_list = []

        for segment in segments:
            # Verifica se o segmento tem palavras individuais
            if hasattr(segment, "words") and segment.words:
                for word in segment.words:
                    # Verifica se word tem os atributos necessários
                    if (
                        hasattr(word, "start")
                        and hasattr(word, "end")
                        and hasattr(word, "word")
                    ):
                        text = self._process_text(word.word.strip()).upper()

                        # ── Aplica destaque para palavras longas ou com pontuação ──
                        if len(text) > 6 or any(x in text for x in ["!", "?", "$"]):
                            text = f"{{\\c{self.cor_destaque}}}{text}{{\\c}}"

                        word_list.append(
                            {"start": word.start, "end": word.end, "text": text}
                        )
            else:
                # ── Fallback: usa o texto completo do segmento ──
                logger.warning(
                    f"Segmento sem palavras individuais, usando texto completo"
                )
                if (
                    hasattr(segment, "start")
                    and hasattr(segment, "end")
                    and hasattr(segment, "text")
                ):
                    text = self._process_text(segment.text.strip()).upper()
                    word_list.append(
                        {"start": segment.start, "end": segment.end, "text": text}
                    )

        logger.info(f"✅ Transcrição concluída: {len(word_list)} palavras/segmentos")
        return word_list

    # ──────────────────────────────────────────────────────────────
    #  PARÂMETROS FFMPEG
    # ──────────────────────────────────────────────────────────────

    def _get_ffmpeg_params(self) -> List[str]:
        """
        Retorna os parâmetros do FFmpeg baseados no modo (rápido ou qualidade).

        Returns:
            Lista de parâmetros para o FFmpeg
        """
        if self.fast_mode:
            # ── MODO RÁPIDO ──
            # Prioriza velocidade mantendo boa qualidade
            return [
                "-c:v",
                "libx264",
                "-preset",
                "veryfast",
                "-crf",
                "23",
                "-c:a",
                "copy",
            ]
        else:
            # ── MODO QUALIDADE ──
            # Prioriza qualidade máxima (mais lento)
            return ["-c:v", "libx264", "-preset", "slow", "-crf", "18", "-c:a", "copy"]

    # ──────────────────────────────────────────────────────────────
    #  PROCESSAMENTO PRINCIPAL
    # ──────────────────────────────────────────────────────────────

    async def process_video(
        self,
        input_path: str,
        audio_path: Optional[str] = None,  # ← NOVO: caminho do áudio separado
        cor_legenda: Optional[str] = None,
    ) -> Optional[Path]:
        """
        Processa o vídeo: transcreve e renderiza legendas.

        Fluxo:
            1. Valida o arquivo de entrada
            2. Obtém duração e resolução
            3. Transcreve o áudio com Whisper (usa audio_path se fornecido)
            4. Gera arquivo .ass com legendas
            5. Renderiza as legendas no vídeo com FFmpeg
            6. Remove arquivos temporários

        Args:
            input_path: Caminho do vídeo de entrada (para renderizar legendas)
            audio_path: Caminho do áudio para transcrição (opcional - se não fornecido, usa o vídeo)
            cor_legenda: Cor da legenda (opcional, sobrescreve a padrão)

        Returns:
            Caminho do vídeo com legendas, ou None em caso de falha
        """
        # ── 1. VALIDAÇÃO DO ARQUIVO ──
        path = Path(input_path)
        if not path.exists():
            logger.error(f"Arquivo não encontrado: {path}")
            return None

        # ── 2. DETERMINA O CAMINHO PARA TRANSCRIÇÃO ──
        # Se audio_path foi fornecido, usa ele. Senão, usa o próprio vídeo.
        transcricao_path = Path(audio_path) if audio_path else path

        if not transcricao_path.exists():
            logger.error(f"Áudio para transcrição não encontrado: {transcricao_path}")
            # Tenta usar o vídeo como fallback
            transcricao_path = path
            logger.warning(
                f"Usando vídeo como fallback para transcrição: {transcricao_path}"
            )

        # ── 3. CONFIGURAÇÃO DE CORES ──
        if cor_legenda:
            cor_key = COR_MAP.get(cor_legenda.lower(), DEFAULT_COR)
            cor_primary = COLORS[cor_key]
            cor_destaque = COLORS["yellow"] if cor_key != "yellow" else COLORS["white"]
        else:
            cor_primary = self.cor_primary
            cor_destaque = self.cor_destaque

        try:
            # ── 4. OBTÉM INFORMAÇÕES DO VÍDEO ──
            logger.info(f"📹 Processando vídeo: {path.name}")

            duration = await self.get_video_duration(path)
            logger.info(f"⏱️  Duração: {duration:.1f}s")

            width, height = await self.get_video_resolution(path)
            logger.info(f"📐 Resolução: {width}x{height}")

            # ── 5. TRANSCRIÇÃO ──
            logger.info(f"🎙️ Transcrevendo áudio: {transcricao_path.name}")
            words = await self.transcribe_word_by_word(transcricao_path)
            logger.info(f"📝 Transcrição: {len(words)} palavras/segmentos")

            if not words:
                logger.warning("⚠️ Nenhuma palavra/segmento transcrito!")
                return None

            # ── 6. GERA ARQUIVO .ASS ──
            ass_path = path.with_suffix(".ass")
            with open(ass_path, "w", encoding="utf-8") as f:
                # Escreve o cabeçalho com estilos
                f.write(self._generate_ass_header(width, height))

                # Escreve os eventos (legendas)
                f.write(
                    "\n[Events]\nFormat: Layer, Start, End, Style, Name, "
                    "MarginL, MarginR, MarginV, Effect, Text\n"
                )
                for w in words:
                    start = self._format_time_ass(w["start"])
                    end = self._format_time_ass(w["end"])
                    f.write(f"Dialogue: 0,{start},{end},Default,,0,0,0,,{w['text']}\n")

            # ── 7. RENDERIZA LEGENDAS COM FFMPEG ──
            output_path = self.final_clips_dir / f"legendado_{path.name}"

            # Escapa caracteres especiais no caminho do .ass
            escaped_ass = (
                str(ass_path.absolute()).replace(":", "\\:").replace("\\", "/")
            )

            # Monta o comando FFmpeg
            ffmpeg_cmd = [
                self.ffmpeg_path,
                "-y",  # Sobrescreve arquivo existente
                "-i",
                str(path),  # Vídeo de entrada
                "-vf",
                f"ass='{escaped_ass}'",  # Filtro de legendas
                *self._get_ffmpeg_params(),  # Parâmetros de codec
                str(output_path),  # Arquivo de saída
            ]

            logger.info("🎬 Renderizando legenda...")

            # Executa o FFmpeg
            proc = await asyncio.create_subprocess_exec(
                *ffmpeg_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            _, stderr = await proc.communicate()

            # ── 8. VERIFICA RESULTADO ──
            if proc.returncode == 0:
                size_mb = output_path.stat().st_size / (1024 * 1024)
                logger.info(
                    f"✅ Vídeo legendado: {output_path.name} ({size_mb:.1f} MB)"
                )

                # Remove arquivo .ass temporário
                if ass_path.exists():
                    os.remove(ass_path)

                return output_path
            else:
                error_msg = stderr.decode()[-500:]
                logger.error(f"FFmpeg erro: {error_msg}")
                return None

        except Exception as e:
            logger.error(f"❌ Erro ao processar {path.name}: {e}")
            import traceback

            traceback.print_exc()
            return None
