"""
src/controllers/video_processing/transcriber_video.py

Responsável por extrair e gerenciar áudio de vídeos para transcrição.
Esta classe é um wrapper/adaptador que conecta o VideoProcessor ao SubtitleGenerator.
"""

import subprocess
import sys
from pathlib import Path
from typing import Optional

ROOT_DIR = Path(__file__).resolve().parent.parent.parent.parent
sys.path.append(str(ROOT_DIR))

from src.services.transcriber import SubtitleGenerator
from src.utils.time_log import time_for_logs


class TranscriberVideo:
    """
    Classe para extração e gerenciamento de áudio de vídeos.

    Responsabilidades:
        1. Extrair áudio de arquivos de vídeo usando FFmpeg
        2. Gerenciar o ciclo de vida do arquivo de áudio (criação e limpeza)
        3. Servir como ponte entre VideoProcessor e SubtitleGenerator

    Attributes:
        video_path (Path): Caminho do arquivo de vídeo original
        subtitle_generator (SubtitleGenerator): Instância do gerador de legendas (lazy-loaded)
    """

    def __init__(self, video_path: Path):
        """
        Inicializa o transcriber para um vídeo específico.

        Args:
            video_path (Path): Caminho do arquivo de vídeo a ser transcrito

        Note:
            O SubtitleGenerator é inicializado com lazy_load=True para evitar
            carregar o modelo Whisper na memória desnecessariamente.
        """
        self.video_path = video_path

        # ── Inicializa o gerador de legendas com carregamento preguiçoso ──
        # fast_mode=True: O modelo Whisper só será carregado quando necessário
        # Isso economiza memória RAM e tempo de inicialização
        self.subtitle_generator = SubtitleGenerator(fast_mode=True)

    def extract_audio(self) -> Optional[Path]:
        """
        Extrai o áudio do vídeo para um arquivo WAV usando FFmpeg.

        O áudio é extraído com qualidade máxima (-q:a 0) e salvo no mesmo
        diretório do vídeo com extensão .wav.

        Returns:
            Optional[Path]: Caminho do arquivo de áudio extraído, ou None se falhar.

        Comando FFmpeg utilizado:
            ffmpeg -i video.mp4 -q:a 0 -map a -y video.wav

            -i: arquivo de entrada
            -q:a 0: qualidade máxima do áudio (0 = melhor)
            -map a: mapeia apenas as streams de áudio
            -y: sobrescreve arquivo existente sem perguntar

        Raises:
            subprocess.CalledProcessError: Se o FFmpeg falhar (capturado internamente)
        """
        # ── Define o caminho do arquivo de áudio .wav ──
        # Substitui a extensão do vídeo (.mp4, .mov, etc.) por .wav
        audio_path = Path(self.video_path).with_suffix(".wav")

        # ── Comando FFmpeg para extração de áudio ──
        cmd = [
            "ffmpeg",  # Comando do FFmpeg
            "-i",  # Flag de input
            str(self.video_path),  # Caminho do vídeo de entrada
            "-q:a",  # Qualidade do áudio (codec)
            "0",  # 0 = melhor qualidade (lossless)
            "-map",  # Mapeia streams específicas
            "a",  # Apenas streams de áudio
            "-y",  # Sobrescreve arquivo existente
            str(audio_path),  # Caminho de saída (.wav)
        ]

        try:
            # ── Executa o comando FFmpeg ──
            # check=True: Levanta exceção se o comando falhar
            # capture_output=True: Captura stdout/stderr para debug
            subprocess.run(cmd, check=True, capture_output=True)

            # ── Verifica se o arquivo foi criado ──
            # Retorna o caminho se existir, senão None
            return audio_path if audio_path.exists() else None

        except subprocess.CalledProcessError as e:
            # ── Tratamento de erro do FFmpeg ──
            # Exibe mensagem com timestamp e retorna None
            print(f"{time_for_logs()} Erro ao extrair áudio: {e}")
            return None

    def cleanup_audio(self, audio_path: Path):
        """
        Remove o arquivo de áudio temporário para liberar espaço em disco.

        Args:
            audio_path (Path): Caminho do arquivo de áudio a ser removido

        Note:
            Esta função deve ser chamada após a transcrição ser concluída,
            para evitar acumular arquivos temporários.

        Exemplo de uso:
            transcriber = TranscriberVideo(video_path)
            audio = transcriber.extract_audio()
            if audio:
                try:
                    # ... processa a transcrição ...
                    pass
                finally:
                    transcriber.cleanup_audio(audio)  # Limpeza garantida
        """
        # ── Verifica se o arquivo existe antes de remover ──
        if audio_path.exists():
            # ── Remove o arquivo (unlink = delete) ──
            audio_path.unlink()
            # Opcional: Log de limpeza (descomente se necessário)
            print(f"{time_for_logs()} 🗑️ Áudio removido: {audio_path.name}")
