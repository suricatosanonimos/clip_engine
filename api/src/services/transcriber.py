import asyncio
import json
import logging
import os
import re
import shutil
import sys
from datetime import timedelta
from pathlib import Path
from typing import Dict, List, Optional

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(ROOT_DIR))

from src.utils.execution_time import execution_time_of_a_function

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


class SubtitleGenerator:
    COLORS = {
        "white": "&H00FFFFFF&",
        "yellow": "&H0000FFFF&",
        "blue_b": "&H00FF5500&",
        "black": "&H00000000&",
    }

    # Palavras que serão censuradas
    BAD_WORDS = {
        "suicidio": "sui***",
        "morte": "mo**e",
        "matar": "ma**r",
        "puta": "p**a",
        "caralho": "ca****o",
        "porra": "p***a",
        "viado": "vi***",
        "bicha": "bi***",
        "vagabundo": "vaga****o",
        "vagabunda": "vaga****a",
        "cú": "c*",
    }

    # Palavras que receberão EMOJIS (não ofensivas)
    EMOJI_WORDS = {
        # Emoções positivas
        "amor": "❤️",
        "amo": "❤️",
        "paixão": "🔥",
        "apaixonado": "🔥",
        "feliz": "😊",
        "felicidade": "✨",
        "alegria": "🎉",
        "rir": "😂",
        "risos": "😂",
        "kkk": "😂",
        "kkkk": "😂",
        "haha": "😄",
        "gargalhada": "🤣",
        # Dinheiro/sucesso
        "dinheiro": "💰",
        "rico": "💸",
        "riqueza": "💎",
        "sucesso": "🚀",
        "vencer": "🏆",
        "vitória": "🥇",
        "ganhar": "🎯",
        # Comida/bebida
        "comida": "🍔",
        "fome": "🍽️",
        "comer": "🍕",
        "bebida": "🥤",
        "café": "☕",
        "cerveja": "🍺",
        # Intensificadores
        "muito": "⚡",
        "demais": "💥",
        "caramba": "😮",
        "nossa": "😲",
        "uau": "✨",
        # Gírias positivas
        "top": "👑",
        "brabo": "🐐",
        "craque": "⭐",
        "gênio": "🧠",
        "mito": "🏛️",
        "lenda": "📜",
        # Música/dança
        "música": "🎵",
        "dançar": "💃",
        "funk": "🎧",
        "trap": "🎤",
        "beat": "🥁",
        # Esportes
        "gol": "⚽",
        "jogar": "🎮",
        "jogo": "🎲",
        "time": "⚡",
        # Lugares
        "casa": "🏠",
        "praia": "🏖️",
        "festa": "🎊",
        "role": "🎪",
        "balada": "🪩",
        # Animais (quando usados como gíria)
        "cachorro": "🐶",
        "gato": "🐱",
        "leão": "🦁",
        "tubarão": "🦈",
        # Expressões comuns
        "deus": "🙏",
        "amém": "🙌",
        "fé": "✨",
        "sorte": "🍀",
        "azar": "💔",
        "força": "💪",
        "foco": "🎯",
    }

    def __init__(
        self,
        ffmpeg_path: str = "ffmpeg",
        ffprobe_path: Optional[str] = None,
        use_gpu: bool = False,
    ):
        self.ffmpeg_path = ffmpeg_path
        self.ffprobe_path = ffprobe_path or shutil.which("ffprobe") or "ffprobe"
        self.use_gpu = use_gpu
        self._model = None
        self.output_dir = Path("processed_videos")
        self.final_clips_dir = self.output_dir / "final_clips"
        self.final_clips_dir.mkdir(parents=True, exist_ok=True)

        # Configura cache permanente
        self.cache_dir = os.path.expanduser("~/.cache/whisper-models/")
        os.makedirs(self.cache_dir, exist_ok=True)

        # Força modo OFFLINE
        os.environ["HF_HUB_OFFLINE"] = "1"
        os.environ["TRANSFORMERS_OFFLINE"] = "1"

        # Compila padrões
        self._compile_patterns()

    def _compile_patterns(self):
        """Compila padrões regex para emojis e censura."""
        # Padrão para CENSURA (mantendo seu código)
        bad_patterns = []
        self.bad_words_map = {}

        for bad, fixed in self.BAD_WORDS.items():
            bad_patterns.append(rf"\b{re.escape(bad)}\b")
            self.bad_words_map[bad.lower()] = fixed

        if bad_patterns:
            self.bad_words_pattern = re.compile("|".join(bad_patterns), re.IGNORECASE)
        else:
            self.bad_words_pattern = None

        # Padrão para EMOJIS
        emoji_patterns = []
        self.emoji_map = {}

        for word, emoji in self.EMOJI_WORDS.items():
            emoji_patterns.append(rf"\b{re.escape(word)}\b")
            self.emoji_map[word.lower()] = emoji

        if emoji_patterns:
            self.emoji_pattern = re.compile("|".join(emoji_patterns), re.IGNORECASE)
        else:
            self.emoji_pattern = None

    def _process_text(self, text: str) -> str:
        """Processa o texto: primeiro aplica emojis, depois censura."""
        original_text = text

        # PASSO 1: Adiciona EMOJIS
        if self.emoji_pattern:

            def add_emoji(match):
                word = match.group(0).lower()
                emoji = self.emoji_map.get(word, "")
                # Mantém a palavra original + adiciona emoji no final
                return f"{match.group(0)} {emoji}"

            text = self.emoji_pattern.sub(add_emoji, text)

        # PASSO 2: Censura palavras ofensivas
        if self.bad_words_pattern:

            def censor_word(match):
                word = match.group(0).lower()
                return self.bad_words_map.get(word, word)

            text = self.bad_words_pattern.sub(censor_word, text)

        # PASSO 3: Remove emojis duplicados (caso tenha dois seguidos)
        text = re.sub(r"([❤️🔥😊✨😂🚀💪💰🎯])\s+\1", r"\1", text)

        return text

    @property
    def model(self):
        if self._model is None:
            from faster_whisper import WhisperModel

            logger.info(f"📁 Modo OFFLINE ativado")
            logger.info(f"📁 Cache: {self.cache_dir}")

            # Verifica se os arquivos realmente existem
            model_bin = None
            for root, dirs, files in os.walk(self.cache_dir):
                for file in files:
                    if file.endswith(".bin"):
                        model_bin = os.path.join(root, file)
                        break
                if model_bin:
                    break

            if model_bin:
                logger.info(f"✅ Modelo encontrado: {model_bin}")
                logger.info(
                    f"✅ Tamanho: {os.path.getsize(model_bin) / (1024*1024):.1f} MB"
                )
            else:
                logger.error("❌ NENHUM ARQUIVO .bin ENCONTRADO!")
                logger.error("❌ O modelo NÃO foi baixado corretamente!")
                for root, dirs, files in os.walk(self.cache_dir):
                    for file in files:
                        logger.error(f"   Arquivo: {os.path.join(root, file)}")

            logger.info(f"Carregando Whisper tiny em modo OFFLINE...")
            self._model = WhisperModel(
                "tiny",
                device="cpu",
                compute_type="int8",
                download_root=self.cache_dir,
                local_files_only=True,
            )
        return self._model

    def _format_time_ass(self, seconds: float) -> str:
        td = timedelta(seconds=seconds)
        total_seconds = int(td.total_seconds())
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        secs = total_seconds % 60
        centiseconds = int(td.microseconds / 10000)
        return f"{hours}:{minutes:02d}:{secs:02d}.{centiseconds:02d}"

    def _generate_ass_header(self, width: int, height: int) -> str:
        font_size = int(height * 0.08)
        m_v = int(height * 0.25)
        outline_size = max(2, int(font_size * 0.1))

        return f"""[Script Info]
ScriptType: v4.00+
PlayResX: {width}
PlayResY: {height}
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Impact,{font_size},{self.COLORS['white']},&H000000FF,{self.COLORS['blue_b']},&H00000000,-1,0,0,0,100,100,2,0,1,{outline_size},0,2,30,30,{m_v},1
"""

    async def get_video_resolution(self, path: Path) -> tuple:
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
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await process.communicate()
        data = json.loads(stdout)
        return (
            data["streams"][0]["width"],
            data["streams"][0]["height"],
        )

    async def get_video_duration(self, path: Path) -> float:
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
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await process.communicate()
        data = json.loads(stdout)
        return float(data["format"]["duration"])

    async def transcribe_word_by_word(self, path: Path) -> List[Dict]:
        logger.info(f"Transcrevendo: {path.name}")
        loop = asyncio.get_event_loop()

        # Parâmetros otimizados
        segments, _ = await loop.run_in_executor(
            None,
            lambda: self.model.transcribe(
                str(path),
                beam_size=5,
                word_timestamps=True,
                best_of=5,
                initial_prompt="Português, entrevista, conversa informal, pt-br",
                temperature=0.0,
                condition_on_previous_text=False,
            ),
        )

        word_list = []
        for segment in segments:
            for word in segment.words:
                # Processa o texto com emojis e censura
                processed_text = self._process_text(word.word.strip())
                processed_text = processed_text.upper()

                # Destaque em Amarelo para palavras longas
                if len(processed_text) > 6 or any(
                    x in processed_text for x in ["!", "?", "$"]
                ):
                    processed_text = (
                        f"{{\\c{self.COLORS['yellow']}}}{processed_text}{{\\c}}"
                    )

                word_list.append(
                    {
                        "start": word.start,
                        "end": word.end,
                        "text": processed_text,
                    }
                )
        return word_list

    def _get_ffmpeg_params(self) -> List[str]:
        base = ["-preset", "ultrafast", "-crf", "18"]

        if self.use_gpu:
            try:
                return ["-c:v", "h264_qsv", "-preset", "veryfast", "-crf", "18"]
            except:
                logger.warning("GPU não disponível, usando CPU")
                return ["-c:v", "libx264"] + base
        else:
            return ["-c:v", "libx264"] + base

    async def process_video(self, input_path: str):
        path = Path(input_path)
        if not path.exists():
            return

        duration = await self.get_video_duration(path)
        logger.info(f"Vídeo: {duration:.1f}s | Iniciando processamento...")

        width, height = await self.get_video_resolution(path)
        words = await self.transcribe_word_by_word(path)

        logger.info(f"Transcrição: {len(words)} palavras encontradas")

        ass_path = path.with_suffix(".ass")
        with open(ass_path, "w", encoding="utf-8") as f:
            f.write(self._generate_ass_header(width, height))
            f.write(
                "\n[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
            )

            for w in words:
                start = self._format_time_ass(w["start"])
                end = self._format_time_ass(w["end"])
                f.write(f"Dialogue: 0,{start},{end},Default,,0,0,0,,{w['text']}\n")

        output_path = self.final_clips_dir / f"final_{path.name}"
        escaped_ass = str(ass_path.absolute()).replace(":", "\\:").replace("\\", "/")

        ffmpeg_params = self._get_ffmpeg_params()
        ffmpeg_cmd = [
            self.ffmpeg_path,
            "-y",
            "-i",
            str(path),
            "-vf",
            f"ass='{escaped_ass}'",
            *ffmpeg_params,
            "-c:a",
            "copy",
            str(output_path),
        ]

        logger.info(f"Renderizando com CRF 23...")
        process = await asyncio.create_subprocess_exec(
            *ffmpeg_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await process.communicate()

        if process.returncode == 0:
            logger.info(f"✅ Sucesso: {output_path}")
            if ass_path.exists():
                os.remove(ass_path)
        else:
            logger.error("Erro no FFmpeg")


if __name__ == "__main__":
    video_teste = "/home/dev/Code/clip_engine/processed_videos/raw_clips/YTDown.com_YouTube_Media_oXm20zRKq_0_001_1080p_clip_01.mp4"

    if not Path(video_teste).exists():
        logger.error(f"Vídeo {video_teste} não encontrado!")
        sys.exit(1)

    async def run():
        generator = SubtitleGenerator(use_gpu=False)
        await generator.process_video(video_teste)

    asyncio.run(run())
