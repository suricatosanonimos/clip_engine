import os
import sys
import json
import asyncio
from pathlib import Path
from moviepy import VideoFileClip, concatenate_videoclips

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

        clips_to_concat.append(main_clip)
        final_video = concatenate_videoclips(clips_to_concat, method="compose")

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

# --- FLUXO PRINCIPAL DE EXECUÇÃO ---
async def main():
    # 1. Configurações de caminhos
    caminho_video = "/home/dev/Code/clip_engine/processed_videos/final_clips/exemple.mp4"

    if not Path(caminho_video).exists():
        print(f"❌ Vídeo de entrada não encontrado: {caminho_video}")
        return

    # 2. Chama a Transcrição + IA (Processo Assíncrono)
    print("🤖 Iniciando Processamento de IA (Whisper + Brain)...")
    analise_ia = await process_video_with_ai(video_input=caminho_video)

    if analise_ia:
        print("\n--- MOMENTOS ESCOLHIDOS PELA IA ---")
        for momento in analise_ia.get("momentos", []):
            print(f"ID {momento['id']} [{momento['inicio']} -> {momento['fim']}]: {momento['texto'][:50]}...")

        # 3. Define o caminho do JSON gerado (baseado no nome do vídeo)
        # O process_video_with_ai salva como ai_analysis_nome_do_video.json
        caminho_json_ia = Path(caminho_video).with_name(f"ai_analysis_{Path(caminho_video).stem}.json")

        # 4. Inicia a Montagem do Vídeo
        if caminho_json_ia.exists():
            assembler = VideoAssembler(ai_results_path=str(caminho_json_ia))
            assembler.create_final_cut(original_video_path=caminho_video)
        else:
            print(f"⚠️ Erro: Arquivo de análise não encontrado em: {caminho_json_ia}")
    else:
        print("❌ A IA não retornou momentos válidos.")

if __name__ == "__main__":
    # Roda o loop de eventos assíncrono
    asyncio.run(main())
