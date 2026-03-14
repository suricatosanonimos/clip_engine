"""
Video Finalizer Module - Adiciona animação final aos vídeos com chroma key.
Remove fundo verde, acelera e combina com o vídeo principal.
"""

import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import List, Optional

# ROOT configuration
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(ROOT_DIR))

from src.config.settings import ConfigFmmpeg

config_fmmpeg = ConfigFmmpeg(preset="medium")
ffmpeg_config = config_fmmpeg.get_config()


class VideoFinalizer:
    """
    Adiciona animação final aos vídeos com efeitos profissionais.

    Características:
    - Remove chroma key (verde limão) e deixa fundo preto
    - Acelera a animação (1.2x)
    - Combina suavemente com o vídeo principal
    - Mantém qualidade original
    """

    def __init__(self):
        """Inicializa o finalizador de vídeos."""
        self.ffmpeg_path = ffmpeg_config["path_ffmpeg"]
        self.ffprobe_path = shutil.which("ffprobe") or "/usr/bin/ffprobe"

        # Diretórios
        self.animations_dir = ROOT_DIR / "assets" / "animations"
        self.input_dir = ROOT_DIR / "processed_videos" / "final_clips"
        self.output_dir = ROOT_DIR / "processed_videos" / "videos_finalizados"
        self.temp_dir = ROOT_DIR / "temp" / "finalizer"

        # Criar diretórios
        for dir_path in [
            self.animations_dir,
            self.input_dir,
            self.output_dir,
            self.temp_dir,
        ]:
            dir_path.mkdir(parents=True, exist_ok=True)

        # Caminho da animação padrão
        self.default_animation = self.animations_dir / "temp_final_tela.mp4"

        print("🎬 VideoFinalizer inicializado")
        print(f"   Animations: {self.animations_dir}")
        print(f"   Input: {self.input_dir}")
        print(f"   Output: {self.output_dir}")

    def _get_video_info(self, video_path: Path) -> dict:
        """Obtém informações do vídeo."""
        cmd = [
            self.ffprobe_path,
            "-v",
            "quiet",
            "-print_format",
            "json",
            "-show_format",
            "-show_streams",
            str(video_path),
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            info = json.loads(result.stdout)

            video_stream = next(
                (s for s in info["streams"] if s["codec_type"] == "video"),
                None,
            )

            audio_stream = next(
                (s for s in info["streams"] if s["codec_type"] == "audio"),
                None,
            )

            if not video_stream:
                return {
                    "duration": 60,
                    "width": 1080,
                    "height": 1920,
                    "fps": 30,
                    "bitrate": "0",
                    "has_audio": False,
                }

            return {
                "duration": float(info["format"]["duration"]),
                "width": int(video_stream["width"]),
                "height": int(video_stream["height"]),
                "fps": eval(video_stream.get("r_frame_rate", "30/1")),
                "bitrate": info["format"].get("bit_rate", "0"),
                "has_audio": audio_stream is not None,
            }
        except Exception as e:
            print(f"⚠️ Erro ao obter info do vídeo: {e}")
            return {
                "duration": 60,
                "width": 1080,
                "height": 1920,
                "fps": 30,
                "bitrate": "0",
                "has_audio": False,
            }

    def _check_audio_stream(self, video_path: Path) -> bool:
        """Verifica se o vídeo tem stream de áudio."""
        cmd = [
            self.ffprobe_path,
            "-v",
            "quiet",
            "-select_streams",
            "a",
            "-show_entries",
            "stream=codec_type",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(video_path),
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            return bool(result.stdout.strip())
        except:
            return False

    def _remove_chroma_key(
        self, animation_path: Path, speed: float = 1.2
    ) -> Optional[Path]:
        """
        Remove o chroma key (verde) da animação e deixa fundo preto.

        Args:
            animation_path: Caminho da animação com fundo verde
            speed: Fator de aceleração (1.2 = 20% mais rápido)

        Returns:
            Caminho da animação processada
        """
        print("🎨 Removendo chroma key e acelerando...")

        output = self.temp_dir / f"processed_{animation_path.name}"

        # Verifica se a animação tem áudio
        has_audio = self._check_audio_stream(animation_path)

        # CORREÇÃO: Filtro para remover chroma key com valores ajustados
        # color=0x00FF00: verde limão
        # similarity=0.2: sensibilidade (0.01-0.1 é muito sensível, 0.2-0.3 funciona melhor)
        # blend=0.0: sem mistura (fundo preto)
        color_filter = "colorkey=0x00FF00:0.3:0.0"

        # Filtro para acelerar o vídeo
        speed_value = 1 / speed
        speed_filter = f"setpts={speed_value}*PTS"

        # Comando base
        if not has_audio:
            print("   ℹ️ Animação sem áudio, processando apenas vídeo")
            command = [
                self.ffmpeg_path,
                "-i",
                str(animation_path),
                "-vf",
                f"{color_filter}, {speed_filter}",
                "-c:v",
                "libx264",
                "-preset",
                "medium",
                "-crf",
                "18",
                "-an",
                "-y",
                str(output),
            ]
        else:
            # Com filtro de áudio (atempo)
            audio_speed = f"atempo={speed}"
            command = [
                self.ffmpeg_path,
                "-i",
                str(animation_path),
                "-vf",
                f"{color_filter}, {speed_filter}",
                "-af",
                audio_speed,
                "-c:v",
                "libx264",
                "-preset",
                "medium",
                "-crf",
                "18",
                "-c:a",
                "aac",
                "-b:a",
                "192k",
                "-y",
                str(output),
            ]

        try:
            print(f"   Executando remoção de chroma...")
            result = subprocess.run(command, check=True, capture_output=True, text=True)

            if output.exists():
                info = self._get_video_info(output)
                print(
                    f'   ✅ Chroma removido | Duração: {info["duration"]:.1f}s | Fundo preto'
                )
                return output
            else:
                print("   ❌ Arquivo de saída não foi criado")
        except subprocess.CalledProcessError as e:
            print(f"❌ Erro ao processar animação: {e.stderr}")
            print("   Tentando método alternativo...")

            # Método alternativo
            return self._remove_chroma_key_alternative(animation_path, speed)

        return None

    def _remove_chroma_key_alternative(
        self, animation_path: Path, speed: float = 1.2
    ) -> Optional[Path]:
        """
        Método alternativo para remover chroma key com colorchannelmixer.
        """
        print("   🔧 Usando método alternativo com colorchannelmixer...")

        output = self.temp_dir / f"processed_{animation_path.name}"
        has_audio = self._check_audio_stream(animation_path)
        speed_value = 1 / speed

        # Método alternativo: colorchannelmixer para isolar o verde e torná-lo preto
        # Isso é mais agressivo e funciona melhor para verdes uniformes
        color_filter = "colorchannelmixer=.3:.4:.3:0:.3:.4:.3:0:.3:.4:.3:0"

        command = [
            self.ffmpeg_path,
            "-i",
            str(animation_path),
            "-vf",
            f"{color_filter}, setpts={speed_value}*PTS",
            "-c:v",
            "libx264",
            "-preset",
            "medium",
            "-crf",
            "18",
            "-an" if not has_audio else "-c:a",
            "aac" if has_audio else "",
            "-b:a",
            "192k" if has_audio else "",
            "-y",
            str(output),
        ]

        # Remove argumentos vazios
        command = [arg for arg in command if arg]

        try:
            subprocess.run(command, check=True, capture_output=True)

            if output.exists():
                info = self._get_video_info(output)
                print(
                    f'   ✅ Chroma removido (alternativo) | Duração: {info["duration"]:.1f}s'
                )
                return output
        except Exception as e:
            print(f"   ❌ Erro no método alternativo: {e}")

        return None

    def _concatenate_videos(
        self, video_path: Path, animation_path: Path
    ) -> Optional[Path]:
        """
        Concatena o vídeo principal com a animação.

        Args:
            video_path: Vídeo principal
            animation_path: Animação processada

        Returns:
            Caminho do vídeo final
        """
        print("🔗 Concatenando vídeos...")

        output = self.output_dir / f"final_{video_path.name}"

        # Verifica se a animação tem áudio
        anim_has_audio = self._check_audio_stream(animation_path)
        video_has_audio = self._check_audio_stream(video_path)

        # Cria arquivo de lista para concatenação
        list_file = self.temp_dir / "concat_list.txt"
        with open(list_file, "w") as f:
            f.write(f"file '{video_path}'\n")
            f.write(f"file '{animation_path}'\n")

        # Se a animação não tem áudio, precisamos recodificar para manter sync
        if not anim_has_audio and video_has_audio:
            print("   ℹ️ Animação sem áudio, recodificando para manter sync...")
            command = [
                self.ffmpeg_path,
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(list_file),
                "-c:v",
                "libx264",
                "-preset",
                "medium",
                "-crf",
                "18",
                "-c:a",
                "aac",
                "-b:a",
                "192k",
                "-y",
                str(output),
            ]
        else:
            # Concatenação normal sem recodificar
            command = [
                self.ffmpeg_path,
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(list_file),
                "-c",
                "copy",
                "-y",
                str(output),
            ]

        try:
            print(f"   Executando concatenação...")
            result = subprocess.run(command, check=True, capture_output=True, text=True)

            if output.exists():
                info = self._get_video_info(output)
                size_mb = output.stat().st_size / (1024 * 1024)
                print(
                    f'   ✅ Vídeo finalizado: {size_mb:.1f} MB | Duração: {info["duration"]:.1f}s'
                )
                return output
            else:
                print("   ❌ Arquivo final não foi criado")
        except subprocess.CalledProcessError as e:
            print(f"❌ Erro na concatenação: {e.stderr}")
        finally:
            if list_file.exists():
                list_file.unlink()

        return None

    def add_ending_animation(
        self,
        video_path: Path,
        animation_path: Optional[Path] = None,
        speed: float = 1.2,
    ) -> Optional[Path]:
        """
        Adiciona animação final ao vídeo.

        Args:
            video_path: Caminho do vídeo principal
            animation_path: Caminho da animação (opcional)
            speed: Velocidade da animação (1.2 = 20% mais rápido)

        Returns:
            Caminho do vídeo finalizado
        """
        print("\n" + "=" * 60)
        print(f"🎬 FINALIZANDO VÍDEO: {video_path.name}")
        print("=" * 60)

        # Verifica se o vídeo existe
        if not video_path.exists():
            print("❌ Vídeo não encontrado")
            return None

        # Usa animação padrão se não for especificada
        if not animation_path:
            animation_path = self.default_animation

        if not animation_path.exists():
            print(f"❌ Animação não encontrada: {animation_path}")
            return None

        # Obtém informações do vídeo
        video_info = self._get_video_info(video_path)
        print("📊 Vídeo original:")
        print(f'   Duração: {video_info["duration"]:.1f}s')
        print(f'   Resolução: {video_info["width"]}x{video_info["height"]}')
        print(f'   FPS: {video_info["fps"]:.2f}')
        print(f'   Áudio: {"Sim" if video_info["has_audio"] else "Não"}')

        # Passo 1: Remove chroma key e acelera
        processed_anim = self._remove_chroma_key(animation_path, speed)
        if not processed_anim:
            print("❌ Falha ao processar animação")
            return None

        # Passo 2: Concatena os vídeos
        final_video = self._concatenate_videos(video_path, processed_anim)

        # Limpeza
        if processed_anim and processed_anim.exists():
            processed_anim.unlink()

        if final_video:
            print("\n✅ VÍDEO FINALIZADO COM SUCESSO!")
            print(f"   📁 {final_video}")

        return final_video

    def process_batch(
        self,
        pattern: str = "final_*.mp4",
        animation_path: Optional[Path] = None,
        speed: float = 1.2,
    ) -> List[Path]:
        """
        Processa múltiplos vídeos em lote.

        Args:
            pattern: Padrão para buscar vídeos
            animation_path: Caminho da animação
            speed: Velocidade da animação

        Returns:
            Lista de vídeos processados
        """
        videos = list(self.input_dir.glob(pattern))

        if not videos:
            print(f"❌ Nenhum vídeo encontrado: {pattern}")
            return []

        print("\n" + "=" * 60)
        print("📦 PROCESSAMENTO EM LOTE")
        print(f"   {len(videos)} vídeos encontrados")
        print("=" * 60)

        processed = []
        for i, video in enumerate(videos, 1):
            print(f"\n[{i}/{len(videos)}]")
            result = self.add_ending_animation(video, animation_path, speed)
            if result:
                processed.append(result)

        print("\n" + "=" * 60)
        print("✅ PROCESSAMENTO EM LOTE CONCLUÍDO!")
        print(f"   {len(processed)}/{len(videos)} vídeos finalizados")
        print("=" * 60)

        return processed


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Adiciona animação final aos vídeos")
    parser.add_argument("--video", type=str, help="Nome do vídeo específico")
    parser.add_argument("--animation", type=str, help="Nome da animação (opcional)")
    parser.add_argument(
        "--pattern",
        type=str,
        default="final_*.mp4",
        help='Padrão para busca (ex: "final_*.mp4")',
    )
    parser.add_argument(
        "--speed",
        type=float,
        default=1.2,
        help="Velocidade da animação (1.2 = 20% mais rápido)",
    )

    args = parser.parse_args()

    finalizer = VideoFinalizer()

    # Caminho da animação
    animation_path = None
    if args.animation:
        animation_path = finalizer.animations_dir / args.animation

    if args.video:
        # Processa vídeo específico
        video_path = finalizer.input_dir / args.video
        if not video_path.exists():
            print(f"❌ Vídeo não encontrado: {video_path}")
        else:
            finalizer.add_ending_animation(video_path, animation_path, args.speed)
    else:
        # Processa lote
        finalizer.process_batch(args.pattern, animation_path, args.speed)
