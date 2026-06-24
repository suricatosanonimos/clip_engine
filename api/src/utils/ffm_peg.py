"""
Módulo principal para processamento de vídeo.
Versão otimizada com suporte completo a legendas dinâmicas (word-by-word) com borda AZUL e estilo Shorts.
"""

import argparse
import asyncio
import subprocess
import sys
from pathlib import Path
from typing import List, Optional

# Adiciona o diretório raiz ao path
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(ROOT_DIR))

from src.config.settings import Colors
from src.controllers.video_processing import VideoProcessor, TranscriberVideo
from src.services.transcriber import SubtitleGenerator

#
from src.utils.subtitle_constants import *

# Decorador para visualizar o tempo de execição das função
from src.utils.execution_time import execution_time_of_a_function
from src.utils.time_log import time_for_logs


@execution_time_of_a_function
async def process_clip_with_retry(
    subtitle_gen: SubtitleGenerator, 
    clip: Path, 
    audio_path: Optional[Path] = None,
    max_retries: int = 2
) -> Optional[Path]:
    """
    Processa um clipe com tentativas de retry em caso de falha.
    Após gerar as legendas, adiciona o áudio de volta ao clipe.
    
    Args:
        subtitle_gen: Instância do gerador de legendas
        clip: Caminho do clipe de vídeo (SEM ÁUDIO)
        audio_path: Caminho do arquivo de áudio .wav (extraído do original)
        max_retries: Número máximo de tentativas
    
    Returns:
        Caminho do clipe finalizado, ou None em caso de falha
    """
    for attempt in range(max_retries + 1):
        try:
            if attempt > 0:
                print(f"  {Colors.warning(f'🔄 Tentativa {attempt}/{max_retries}...')}")

            # ── Etapa 1: Gerar clipe com legendas ──
            # Passa o áudio .wav para transcrição (não o clipe sem áudio)
            if audio_path and audio_path.exists():
                print(f"  {Colors.info('🎙️ Usando áudio extraído para transcrição...')}")
                final_clip = await subtitle_gen.process_video(
                    str(clip), 
                    audio_path=str(audio_path)  # ← PASSA O ÁUDIO .WAV!
                )
            else:
                print(f"  {Colors.warning('⚠️ Áudio não disponível, tentando transcrição direta...')}")
                final_clip = await subtitle_gen.process_video(str(clip))

            if not final_clip or not Path(final_clip).exists():
                raise Exception("Falha ao gerar clipe com legendas")

            final_clip_path = Path(final_clip)
            
            # ── Etapa 2: Adicionar áudio ao clipe legendado ──
            if audio_path and audio_path.exists():
                print(f"  {Colors.info('🔊 Adicionando áudio ao clipe legendado...')}")
                
                # Cria caminho para o clipe final com áudio
                final_com_audio = final_clip_path.parent / f"com_audio_{final_clip_path.name}"
                
                # Comando FFmpeg para adicionar áudio
                cmd = [
                    "ffmpeg",
                    "-i", str(final_clip_path),      # Vídeo com legenda
                    "-i", str(audio_path),            # Áudio original
                    "-c:v", "copy",                   # Copia vídeo (sem re-encode)
                    "-c:a", "aac",                    # Codec de áudio
                    "-b:a", "192k",                   # Bitrate do áudio
                    "-map", "0:v:0",                  # Pega vídeo do primeiro input
                    "-map", "1:a:0",                  # Pega áudio do segundo input
                    "-shortest",                      # Duração do menor
                    "-y",                             # Sobrescreve
                    str(final_com_audio)
                ]
                
                result = subprocess.run(cmd, capture_output=True, text=True)
                
                if result.returncode == 0 and final_com_audio.exists():
                    # Remove o clipe sem áudio e renomeia o com áudio
                    final_clip_path.unlink()
                    final_com_audio.rename(final_clip_path)
                    print(f"  {Colors.success('✅ Áudio adicionado com sucesso!')}")
                    return final_clip_path
                else:
                    print(f"  {Colors.warning('⚠️ Falha ao adicionar áudio, mantendo clipe sem áudio')}")
                    if result.stderr:
                        print(f"  {Colors.error(f'Erro: {result.stderr[:200]}')}")
                    return final_clip_path
            else:
                print(f"  {Colors.warning('⚠️ Áudio não disponível, mantendo clipe sem áudio')}")
                return final_clip_path

        except Exception as e:
            print(f"  {Colors.error(f'❌ Erro na tentativa {attempt}: {e}')}")

        if attempt < max_retries:
            await asyncio.sleep(2)

    return None


@execution_time_of_a_function
async def process_subtitles_batch(
    clips: List[Path],
    subtitle_gen: SubtitleGenerator,
    video_original_path: Path,
    batch_size: int = 3,
) -> List[Path]:
    """
    Processa legendas em lotes para melhor performance.
    Para cada clipe, extrai áudio do vídeo ORIGINAL, gera legendas e adiciona áudio de volta.
    
    Args:
        clips: Lista de clipes gerados (SEM ÁUDIO)
        subtitle_gen: Instância do gerador de legendas
        video_original_path: Caminho do vídeo original (COM ÁUDIO)
        batch_size: Tamanho do lote para processamento paralelo
    
    Returns:
        Lista de clipes finalizados com legendas e áudio
    """
    clips_com_legendas = []
    total_clips = len(clips)

    print(f"\n{Colors.bold('📊 Processando em lotes de')} {batch_size} clipes")
    print(f"{Colors.bold('=' * 60)}")

    for i in range(0, total_clips, batch_size):
        batch = clips[i : i + batch_size]
        batch_num = i // batch_size + 1
        total_batches = (total_clips + batch_size - 1) // batch_size

        print(f"\n{Colors.bold(f'📦 Lote {batch_num}/{total_batches}')}")
        print(f"{Colors.bold('-' * 40)}")

        # ── Para cada clipe, extrai áudio do vídeo ORIGINAL ──
        clips_com_audio = []
        for clip in batch:
            # Usa o vídeo ORIGINAL para extrair áudio
            transcriber = TranscriberVideo(video_original_path)
            
            # Extrai áudio do vídeo original (não do clipe)
            audio_path = transcriber.extract_audio()
            
            if audio_path:
                clips_com_audio.append((clip, audio_path, transcriber))
                print(f"  {Colors.success(f'🎵 Áudio extraído do original:')} {audio_path.name}")
            else:
                print(f"  {Colors.warning(f'⚠️ Falha ao extrair áudio do original para:')} {clip.name}")
                clips_com_audio.append((clip, None, transcriber))

        # ── Cria tarefas para processamento paralelo ──
        tasks = []
        for clip, audio_path, _ in clips_com_audio:
            tasks.append(process_clip_with_retry(subtitle_gen, clip, audio_path))

        # ── Executa tarefas do lote em paralelo ──
        batch_results = await asyncio.gather(*tasks)

        # ── Processa resultados do lote e limpa áudio ──
        for (clip, audio_path, transcriber), result in zip(clips_com_audio, batch_results):
            # Limpa áudio temporário
            if audio_path and audio_path.exists():
                transcriber.cleanup_audio(audio_path)
                print(f"  {Colors.info('🗑️ Áudio removido:')} {audio_path.name}")

            if result:
                clips_com_legendas.append(result)
                size_mb = result.stat().st_size / (1024 * 1024)
                print(
                    f"  {Colors.success(f'✅ Clipe finalizado:')} {result.name} ({size_mb:.1f} MB)"
                )
            else:
                print(f"  {Colors.error(f'❌ Falha no clipe:')} {clip.name}")

        # ── Pequena pausa entre lotes ──
        if i + batch_size < total_clips:
            print(f"\n  {Colors.info('⏳ Aguardando 2s antes do próximo lote...')}")
            await asyncio.sleep(2)

    return clips_com_legendas


def print_status_header(title: str, char: str = "="):
    """Imprime cabeçalho de status formatado."""
    print(f"\n{Colors.bold(char * 60)}")
    print(f"{Colors.bold(f'📊 {title}')}")
    print(f"{Colors.bold(char * 60)}")


def print_file_list(files: List[Path], label: str = "Arquivos"):
    """Imprime lista formatada de arquivos com tamanhos."""
    if not files:
        print(f"{Colors.warning('⚠️ Nenhum arquivo encontrado')}")
        return

    print(f"\n{Colors.info(f'📁 {label}:')}")
    total_size = 0
    for file in files:
        size = file.stat().st_size / (1024 * 1024)
        total_size += size
        icon = "🎬" if "final" in file.name else "📼"
        print(f"  {icon} {file.name} ({size:.1f} MB)")
    print(f"\n{Colors.bold(f'📊 Total: {total_size:.1f} MB')}")


@execution_time_of_a_function
async def main():
    parser = argparse.ArgumentParser(
        description="Processador de vídeos para YouTube Shorts com legendas inteligentes",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemplos de uso:
  python ffm_peg.py --video meu_video.mp4
  python ffm_peg.py --video meu_video.mp4 --num-shots 15 --duration 45
  python ffm_peg.py --video meu_video.mp4 --no-tracking --no-subtitles
  python ffm_peg.py --video meu_video.mp4 --batch-size 4 --retries 3
        """,
    )

    # Argumentos principais
    parser.add_argument(
        "--video",
        required=True,
        help="Nome do arquivo de vídeo a processar",
    )
    parser.add_argument(
        "--num-shots",
        type=int,
        default=10,
        help="Número de clipes a gerar (padrão: 10)",
    )
    parser.add_argument(
        "--duration",
        type=int,
        default=60,
        help="Duração de cada clipe em segundos (padrão: 60)",
    )

    # Opções de processamento
    parser.add_argument(
        "--no-tracking",
        action="store_true",
        help="Desativa tracking de rostos (usa apenas FFmpeg)",
    )
    parser.add_argument(
        "--no-subtitles",
        action="store_true",
        help="Pula geração de legendas",
    )

    # Opções avançadas de legendas
    parser.add_argument(
        "--batch-size",
        type=int,
        default=3,
        help="Número de clipes processados em paralelo (padrão: 3)",
    )
    parser.add_argument(
        "--retries",
        type=int,
        default=2,
        help="Número de tentativas por clipe em caso de falha (padrão: 2)",
    )
    parser.add_argument(
        "--no-lazy",
        action="store_true",
        help="Carrega Whisper na inicialização (mais lento, mas primeira legenda mais rápida)",
    )

    args = parser.parse_args()

    # Validações
    if args.num_shots <= 0:
        print(f"{Colors.error('❌ num-shots deve ser maior que 0')}")
        return

    if args.duration <= 0:
        print(f"{Colors.error('❌ duration deve ser maior que 0')}")
        return

    if args.batch_size <= 0:
        print(f"{Colors.error('❌ batch-size deve ser maior que 0')}")
        args.batch_size = 3

    # ── Caminho do vídeo original ──
    video_original_path = ROOT_DIR / "downloads" / args.video
    print(f"{Colors.info('📹 Vídeo original:')} {video_original_path}")

    # Verifica se o vídeo original existe
    if not video_original_path.exists():
        print(f"{Colors.error(f'❌ Vídeo original não encontrado: {video_original_path}')}")
        print(f"  {Colors.info('💡 Certifique-se de que o vídeo está na pasta downloads/')}")
        return

    # Inicializa processador de vídeo
    processor = VideoProcessor(num_shots=args.num_shots)
    processor.clip_duration = args.duration

    # HEADER PRINCIPAL
    print(f"\n{Colors.bold('=' * 70)}")
    print(f"{Colors.bold('🎯 PERFECT SPEAKER TRACKER - YOUTUBE SHORTS')}")
    print(f"{Colors.bold('=' * 70)}")

    # Configuração
    print(f"\n{Colors.bold('⚙️ CONFIGURAÇÃO:')}")
    print(f"  {Colors.info('📹 Vídeo:')} {args.video}")
    print(f"  {Colors.info('🎬 Clipes:')} {args.num_shots} x {args.duration}s")
    print(f"  {Colors.info('🔍 Zoom:')} Reduzido (+ contexto)")
    print(
        f"  {Colors.info('🎯 Modo tracking:')} {'Ativado' if not args.no_tracking else 'Desativado'}"
    )
    print(
        f"  {Colors.info('📝 Legendas:')} {'Ativadas' if not args.no_subtitles else 'Desativadas'}"
    )

    if not args.no_subtitles:
        print(
            f"  {Colors.info('🎨 Estilo legendas:')} Impact (Centro-Inferior) + Borda AZUL + Word-by-Word"
        )
        print(f"  {Colors.info('🛡️ Censura:')} Palavras ofensivas bloqueadas")
        print(f"  {Colors.info('📦 Batch size:')} {args.batch_size}")
        print(f"  {Colors.info('🔄 Retries:')} {args.retries}")

    print(f"{Colors.bold('=' * 70)}")

    # PRIMEIRA ETAPA: Gerar os clipes
    print(f"\n{Colors.bold('🎬 PRIMEIRA ETAPA: GERANDO CLIPES')}")
    print(f"{Colors.bold('=' * 70)}")

    start_time = asyncio.get_event_loop().time()
    clips = await processor.process(
        video_name=args.video,
        tracking=not args.no_tracking,
    )
    elapsed_time = asyncio.get_event_loop().time() - start_time

    # Resumo primeira etapa
    print_status_header("RESUMO DA PRIMEIRA ETAPA")
    print(f"  {Colors.success('✅ Clipes gerados:')} {len(clips)}/{args.num_shots}")
    print(f"  {Colors.info('⏱️ Tempo total:')} {elapsed_time:.1f}s")

    if clips:
        print_file_list(clips, "CLIPES BRUTOS GERADOS (SEM ÁUDIO)")
    else:
        print(f"\n{Colors.error('❌ Nenhum clipe foi gerado!')}")
        return

    # SEGUNDA ETAPA: Transcrever os clipes (se não for pulado)
    if not args.no_subtitles and clips:
        print(f"\n{Colors.bold('🎬 SEGUNDA ETAPA: GERANDO LEGENDAS')}")
        print(f"{Colors.bold('=' * 70)}")
        print(f"  {Colors.info('🎨 Estilo:')} Impact + Borda AZUL + Destaque Amarelo")
        print(f"  {Colors.info('🛡️ Proteção:')} Palavras ofensivas censuradas")
        print(f"  {Colors.info('🔄 Modo:')} Extrai áudio do ORIGINAL → Gera legenda → Adiciona áudio de volta")
        print(f"{Colors.bold('-' * 70)}")

        # Mostra preview das palavras censuradas
        print(f"\n  {Colors.info('📋 Palavras protegidas:')}")
        bad_words_sample = list(BAD_WORDS.keys())[:5]
        for word in bad_words_sample:
            censored = BAD_WORDS[word]
            print(f"  • {word} → {censored} ⚠️")

        # Inicializa o gerador de legendas
        subtitle_gen = SubtitleGenerator()

        # Processa legendas em lotes (com áudio do vídeo ORIGINAL)
        start_time = asyncio.get_event_loop().time()
        clips_com_legendas = await process_subtitles_batch(
            clips, 
            subtitle_gen, 
            video_original_path,
            batch_size=args.batch_size
        )
        elapsed_time = asyncio.get_event_loop().time() - start_time

        # Status final das legendas
        print_status_header("STATUS DAS LEGENDAS")
        print(
            f"  {Colors.success('✅ Clipes com legendas e áudio:')} {len(clips_com_legendas)}/{len(clips)}"
        )
        print(f"  {Colors.info('⏱️ Tempo transcrição:')} {elapsed_time:.1f}s")

        if clips_com_legendas:
            print_file_list(clips_com_legendas, "CLIPES FINAIS COM LEGENDAS + ÁUDIO")
        else:
            print(f"\n{Colors.warning('⚠️ Nenhuma legenda foi gerada!')}")

    # FOOTER FINAL
    print(f"\n{Colors.bold('=' * 70)}")
    print(f"{Colors.success('✅ PROCESSAMENTO CONCLUÍDO COM SUCESSO!')}")
    print(f"{Colors.bold('=' * 70)}")

    # Localização dos arquivos
    print(f"\n{Colors.info('📁 ARQUIVOS GERADOS:')}")
    print(
        f"  {Colors.info('📼 Clipes brutos (sem áudio):')} {ROOT_DIR}/processed_videos/raw_clips/"
    )
    print(
        f"  {Colors.info('🎬 Clipes finais (com legendas + áudio):')} {ROOT_DIR}/processed_videos/final_clips/"
    )

    print(f"\n{Colors.bold('✨ Obrigado por usar o Perfect Speaker Tracker!')}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print(f"\n\n{Colors.warning('⚠️ Processamento interrompido pelo usuário.')}")
        sys.exit(0)
    except Exception as e:
        print(f"\n{Colors.error(f'❌ Erro fatal: {e}')}")
        import traceback
        traceback.print_exc()
        sys.exit(1)