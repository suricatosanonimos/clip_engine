"""
src/controllers/highlight/subtitle_generator.py

Gera legendas word-by-word via Whisper e renderiza no vídeo com FFmpeg/ASS.
Aceita cor da legenda como parâmetro (white | yellow | blue | green).
"""

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

ROOT_DIR = Path(__file__).resolve().parent.parent.parent.parent
sys.path.append(str(ROOT_DIR))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


class SubtitleGenerator:

    # ── Cores ASS ──────────────────────────────────────────────────
    # Formato ASS: &HAABBGGRR& (alpha, blue, green, red — invertido)
    # Correção: o "blue_b" original era &H00FF5500 = laranja/âmbar no ASS
    # porque 55=R, 00=G, FF=B → invertido = azul intenso no display
    # Aqui usamos nomes claros com os valores corretos
    COLORS = {
        "white":  "&H00FFFFFF&",   # branco puro
        "yellow": "&H0000FFFF&",   # amarelo vibrante (0=A, 0=B, FF=G, FF=R → amarelo)
        "blue":   "&H00FF5500&",   # azul vivo (FF=B, 55=G, 00=R no ASS)
        "green":  "&H0055FF55&",   # verde vibrante
        "black":  "&H00000000&",   # preto
    }

    # Mapeamento de nomes do app → chave interna
    COR_MAP = {
        "white":  "white",
        "yellow": "yellow",
        "blue":   "blue",
        "green":  "green",
        "branco": "white",
        "amarelo":"yellow",
        "azul":   "blue",
        "verde":  "green",
    }

    # Cor padrão — branco com destaque amarelo nas palavras longas
    DEFAULT_COR = "white"

    # ── Censura ───────────────────────────────────────────────────
    BAD_WORDS = {
        "suicidio": "sui***",  "morte": "mo**e",    "matar": "ma**r",
        "puta":     "p**a",    "caralho": "ca****o", "porra": "p***a",
        "viado":    "vi***",   "bicha": "bi***",     "vagabundo": "vaga****o",
        "vagabunda":"vaga****a","cú": "c*",
    }

    # ── Emojis ────────────────────────────────────────────────────
    EMOJI_WORDS = {
        "amor": "❤️",   "amo": "❤️",    "paixão": "🔥",  "apaixonado": "🔥",
        "feliz":"😊",    "felicidade":"✨","alegria":"🎉", "rir":"😂",
        "risos":"😂",    "kkk":"😂",      "kkkk":"😂",     "haha":"😄",
        "gargalhada":"🤣","dinheiro":"💰","rico":"💸",     "riqueza":"💎",
        "sucesso":"🚀",  "vencer":"🏆",   "vitória":"🥇",  "ganhar":"🎯",
        "comida":"🍔",   "fome":"🍽️",    "comer":"🍕",    "bebida":"🥤",
        "café":"☕",     "cerveja":"🍺",  "muito":"⚡",    "demais":"💥",
        "caramba":"😮",  "nossa":"😲",    "uau":"✨",       "top":"👑",
        "brabo":"🐐",    "craque":"⭐",   "gênio":"🧠",    "mito":"🏛️",
        "lenda":"📜",    "música":"🎵",   "dançar":"💃",   "funk":"🎧",
        "trap":"🎤",     "beat":"🥁",     "gol":"⚽",       "jogar":"🎮",
        "jogo":"🎲",     "casa":"🏠",     "praia":"🏖️",   "festa":"🎊",
        "role":"🎪",     "balada":"🪩",   "cachorro":"🐶", "gato":"🐱",
        "leão":"🦁",     "tubarão":"🦈", "deus":"🙏",     "amém":"🙌",
        "fé":"✨",        "sorte":"🍀",    "azar":"💔",     "força":"💪",
        "foco":"🎯",
    }

    def __init__(
        self,
        ffmpeg_path:  str            = "ffmpeg",
        ffprobe_path: Optional[str]  = None,
        use_gpu:      bool           = False,
        cor_legenda:  str            = DEFAULT_COR,   # ← NOVO parâmetro
    ):
        self.ffmpeg_path  = ffmpeg_path
        self.ffprobe_path = ffprobe_path or shutil.which("ffprobe") or "ffprobe"
        self.use_gpu      = use_gpu

        # Resolve cor — aceita nome do app ou chave interna
        cor_normalizada  = self.COR_MAP.get(cor_legenda.lower(), self.DEFAULT_COR)
        self.cor_legenda  = cor_normalizada
        self.cor_primary  = self.COLORS[cor_normalizada]
        # Cor de destaque: se a cor principal não é amarelo, usa amarelo;
        # se já é amarelo, usa branco para contraste
        self.cor_destaque = (
            self.COLORS["yellow"] if cor_normalizada != "yellow"
            else self.COLORS["white"]
        )

        self._model = None
        self.output_dir      = ROOT_DIR / "processed_videos"
        self.final_clips_dir = self.output_dir / "final_clips"
        self.final_clips_dir.mkdir(parents=True, exist_ok=True)

        self.cache_dir = os.path.expanduser("~/.cache/whisper-models/")
        os.makedirs(self.cache_dir, exist_ok=True)

        os.environ["HF_HUB_OFFLINE"]       = "1"
        os.environ["TRANSFORMERS_OFFLINE"]  = "1"

        self._compile_patterns()

    # ── Padrões regex ──────────────────────────────────────────────

    def _compile_patterns(self):
        self.bad_words_map = {}
        bad_patterns       = []
        for bad, fixed in self.BAD_WORDS.items():
            bad_patterns.append(rf"\b{re.escape(bad)}\b")
            self.bad_words_map[bad.lower()] = fixed
        self.bad_words_pattern = (
            re.compile("|".join(bad_patterns), re.IGNORECASE) if bad_patterns else None
        )

        self.emoji_map    = {}
        emoji_patterns    = []
        for word, emoji in self.EMOJI_WORDS.items():
            emoji_patterns.append(rf"\b{re.escape(word)}\b")
            self.emoji_map[word.lower()] = emoji
        self.emoji_pattern = (
            re.compile("|".join(emoji_patterns), re.IGNORECASE) if emoji_patterns else None
        )

    # ── Processamento de texto ─────────────────────────────────────

    def _process_text(self, text: str) -> str:
        if self.emoji_pattern:
            text = self.emoji_pattern.sub(
                lambda m: f"{m.group(0)} {self.emoji_map.get(m.group(0).lower(), '')}",
                text,
            )
        if self.bad_words_pattern:
            text = self.bad_words_pattern.sub(
                lambda m: self.bad_words_map.get(m.group(0).lower(), m.group(0)),
                text,
            )
        text = re.sub(r"([❤️🔥😊✨😂🚀💪💰🎯])\s+\1", r"\1", text)
        return text

    # ── Modelo Whisper ─────────────────────────────────────────────

    @property
    def model(self):
        if self._model is None:
            from faster_whisper import WhisperModel
            logger.info("Carregando Whisper tiny (OFFLINE)...")
            self._model = WhisperModel(
                "tiny", device="cpu", compute_type="int8",
                download_root=self.cache_dir, local_files_only=True,
            )
        return self._model

    # ── Formatação de tempo ASS ────────────────────────────────────

    def _format_time_ass(self, seconds: float) -> str:
        td           = timedelta(seconds=seconds)
        total        = int(td.total_seconds())
        h            = total // 3600
        m            = (total % 3600) // 60
        s            = total % 60
        cs           = int(td.microseconds / 10000)
        return f"{h}:{m:02d}:{s:02d}.{cs:02d}"

    # ── Header ASS com a cor selecionada ──────────────────────────

    def _generate_ass_header(self, width: int, height: int) -> str:
        font_size    = int(height * 0.08)
        m_v          = int(height * 0.25)
        outline_size = max(2, int(font_size * 0.1))

        # Contorno sempre preto para legibilidade independente da cor
        return f"""[Script Info]
ScriptType: v4.00+
PlayResX: {width}
PlayResY: {height}
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Impact,{font_size},{self.cor_primary},&H000000FF,{self.COLORS['black']},&H00000000,-1,0,0,0,100,100,2,0,1,{outline_size},0,2,30,30,{m_v},1
"""

    # ── ffprobe helpers ────────────────────────────────────────────

    async def get_video_resolution(self, path: Path) -> tuple:
        cmd = [
            self.ffprobe_path, "-v", "error", "-select_streams", "v:0",
            "-show_entries", "stream=width,height", "-of", "json", str(path),
        ]
        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        data = json.loads(stdout)
        return data["streams"][0]["width"], data["streams"][0]["height"]

    async def get_video_duration(self, path: Path) -> float:
        cmd = [
            self.ffprobe_path, "-v", "error",
            "-show_entries", "format=duration", "-of", "json", str(path),
        ]
        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        data = json.loads(stdout)
        return float(data["format"]["duration"])

    # ── Transcrição ────────────────────────────────────────────────

    async def transcribe_word_by_word(self, path: Path) -> List[Dict]:
        logger.info(f"Transcrevendo: {path.name}")
        loop = asyncio.get_event_loop()
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
                text = self._process_text(word.word.strip()).upper()

                # Destaque na cor de contraste para palavras longas/expressivas
                if len(text) > 6 or any(x in text for x in ["!", "?", "$"]):
                    text = f"{{\\c{self.cor_destaque}}}{text}{{\\c}}"

                word_list.append({"start": word.start, "end": word.end, "text": text})
        return word_list

    # ── Parâmetros FFmpeg ──────────────────────────────────────────

    def _get_ffmpeg_params(self) -> List[str]:
        base = ["-preset", "fast", "-crf", "23"]
        if self.use_gpu:
            try:
                return ["-c:v", "h264_qsv", "-preset", "veryfast", "-crf", "18"]
            except Exception:
                pass
        return ["-c:v", "libx264"] + base

    # ── Processa vídeo: transcreve + renderiza legenda ─────────────

    async def process_video(self, input_path: str, cor_legenda: str = None) -> Optional[Path]:
        """
        Transcreve o vídeo com Whisper e queima as legendas no arquivo.
        Retorna o path do vídeo com legenda, ou None em caso de erro.

        Args:
            input_path:  caminho do clipe gerado pelo VideoProcessor
            cor_legenda: sobrescreve a cor definida no __init__ (opcional)
        """
        path = Path(input_path)
        if not path.exists():
            logger.error(f"Arquivo não encontrado: {path}")
            return None

        # Permite sobrescrever a cor por clipe se necessário
        if cor_legenda:
            cor_key         = self.COR_MAP.get(cor_legenda.lower(), self.DEFAULT_COR)
            cor_primary     = self.COLORS[cor_key]
            cor_destaque    = (
                self.COLORS["yellow"] if cor_key != "yellow" else self.COLORS["white"]
            )
        else:
            cor_primary  = self.cor_primary
            cor_destaque = self.cor_destaque

        try:
            duration          = await self.get_video_duration(path)
            logger.info(f"Vídeo: {duration:.1f}s — gerando legendas...")

            width, height = await self.get_video_resolution(path)
            words         = await self.transcribe_word_by_word(path)
            logger.info(f"Transcrição: {len(words)} palavras")

            # Gera arquivo .ass
            ass_path = path.with_suffix(".ass")
            with open(ass_path, "w", encoding="utf-8") as f:
                f.write(self._generate_ass_header(width, height))
                f.write(
                    "\n[Events]\nFormat: Layer, Start, End, Style, Name, "
                    "MarginL, MarginR, MarginV, Effect, Text\n"
                )
                for w in words:
                    start = self._format_time_ass(w["start"])
                    end   = self._format_time_ass(w["end"])
                    f.write(f"Dialogue: 0,{start},{end},Default,,0,0,0,,{w['text']}\n")

            output_path  = self.final_clips_dir / f"final_{path.name}"
            escaped_ass  = str(ass_path.absolute()).replace(":", "\\:").replace("\\", "/")
            ffmpeg_params = self._get_ffmpeg_params()

            ffmpeg_cmd = [
                self.ffmpeg_path, "-y", "-i", str(path),
                "-vf", f"ass='{escaped_ass}'",
                *ffmpeg_params,
                "-c:a", "copy",
                str(output_path),
            ]

            logger.info("Renderizando legenda...")
            proc = await asyncio.create_subprocess_exec(
                *ffmpeg_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            _, stderr = await proc.communicate()

            if proc.returncode == 0:
                logger.info(f"✅ Legenda renderizada: {output_path}")
                if ass_path.exists():
                    os.remove(ass_path)
                return output_path
            else:
                logger.error(f"FFmpeg erro: {stderr.decode()[-300:]}")
                return None

        except Exception as e:
            logger.error(f"Erro ao gerar legenda para {path.name}: {e}")
            return None
