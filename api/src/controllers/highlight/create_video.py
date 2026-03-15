# /home/dev/Code/clip_engine/api/src/controllers/highlight/create_video.py
import asyncio
import json
import os
import sys
from pathlib import Path

from moviepy import VideoFileClip, afx, concatenate_videoclips, vfx

# Path de pastas raiz
ROOT_DIR = Path(__file__).resolve().parent.parent.parent.parent
sys.path.append(str(ROOT_DIR))

# Importação da sua função de transcrição
from src.controllers.highlight.transcription import process_video_with_ai


class GenerateFinalVideo:
    """
    Responsável pela etapa final de pós-produção dos vídeos.
    """

    def __init__(self) -> None:
        self.final_video_in = ROOT_DIR / "processed_videos" / "final_clips"
        self.final_video_in.mkdir(parents=True, exist_ok=True)

    def normalizes_path(self, full_path: str) -> str:
        return Path(full_path).name

    def path_exist(self, filename: str) -> bool:
        full_path = self.final_video_in / filename
        return full_path.exists()


class VideoAssembler(GenerateFinalVideo):
    """
    Corta momentos de impacto e os concatena como introdução (hook) do vídeo principal.
    """

    def __init__(self, ai_results_path: str):
        super().__init__()
        self.ai_results_path = Path(ai_results_path)

    def _parse_timestamp(self, timestamp_str: str) -> float:
        try:
            m, s = map(int, timestamp_str.split(":"))
            return float(m * 60 + s)
        except ValueError:
            return float(timestamp_str)

    def create_final_cut(self, original_video_path: str):
        video_path = Path(original_video_path)
        if not video_path.exists():
            print(f"❌ Erro: Vídeo original não encontrado em {original_video_path}")
            return

        with open(self.ai_results_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        momentos = data.get("momentos", [])
        print(f"🎬 Iniciando montagem final de: {video_path.name}")

        main_clip = VideoFileClip(str(video_path))
        clips_to_concat = []

        print("⚡ Extraindo momentos de impacto para a introdução...")
        for momento in momentos:
            start_t = self._parse_timestamp(momento["inicio"])
            end_t = self._parse_timestamp(momento["fim"])

            # subclipped para MoviePy 2.x
            sub_clip = main_clip.subclipped(start_t, end_t)
            clips_to_concat.append(sub_clip)

        # Adicionar efeito de transição no video principal
        time_transition = 1.00

        try:
            main_clip_with_transition = main_clip.with_effects(
                [vfx.CrossFadeIn(duration=time_transition)]
            )
            clips_to_concat.append(main_clip_with_transition)

            clips_to_concat.append(main_clip)

        except Exception as e:
            print(f"{e.__class__.__name__}: Error with_effects [create_video.py] ")

        final_video = concatenate_videoclips(
            clips_to_concat, method="compose", padding=-time_transition
        )
        output_name = f"FINAL_HOOK_{video_path.name}"
        output_path = self.final_video_in / output_name

        print(f"🚀 Renderizando vídeo final: {output_name}")
        final_video.write_videofile(
            str(output_path),
            codec="libx264",
            audio_codec="aac",
            fps=24,
            preset="ultrafast",
            threads=4,
        )

        main_clip.close()
        final_video.close()
        print(f"✅ Vídeo finalizado com sucesso em: {output_path}")

