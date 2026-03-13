"""
Módulo principal para processamento de vídeo.
Versão otimizada com suporte completo a legendas dinâmicas (word-by-word) com borda AZUL e estilo Shorts.
"""

import argparse
import asyncio
import sys
from pathlib import Path
from typing import List, Optional

# Adiciona o diretório raiz ao path
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(ROOT_DIR))

from src.config.settings import Colors
from src.controllers.video_processing import VideoProcessor
from src.services.transcriber import SubtitleGenerator

# Decorador para visualizar o tempo de execição das função
from src.utils.execution_time import execution_time_of_a_function
from src.utils.time_log import time_for_logs


@execution_time_of_a_function
async def process_clip_with_retry(
    subtitle_gen: SubtitleGenerator, clip: Path, max_retries: int = 2
) -> Optional[Path]:
    """
    Processa um clipe com tentativas de retry em caso de falha.

    Args:
        subtitle_gen: Instância do gerador de legendas
        clip: Caminho do clipe a ser processado
        max_retries: Número máximo de tentativas

    Returns:
        Caminho do clipe final ou None se falhar
    """
    for attempt in range(max_retries + 1):
        try:
            if attempt > 0:
                print(f"  {Colors.warning(f'🔄 Tentativa {attempt}/{max_retries}...')}")

            # Chama o método de processamento do novo SubtitleGenerator
            # Internamente ele deve usar a lógica de word-timestamps e estilos ASS
            final_clip = await subtitle_gen.process_video(str(clip))

            if final_clip and Path(final_clip).exists():
                return Path(final_clip)

        except Exception as e:
            print(f"  {Colors.error(f'❌ Erro na tentativa {attempt}: {e}')}")

        if attempt < max_retries:
            await asyncio.sleep(2)  # Espera 2 segundos entre tentativas

    return None


@execution_time_of_a_function
async def process_subtitles_batch(
    clips: List[Path],
    subtitle_gen: SubtitleGenerator,
    batch_size: int = 3,
) -> List[Path]:
    """
    Processa legendas em lotes para melhor performance.

    Args:
        clips: Lista de clipes a processar
        subtitle_gen: Instância do gerador de legendas
        batch_size: Tamanho do lote para processamento paralelo

    Returns:
        Lista de clipes processados com legendas
    """
    clips_com_legendas = []
    total_clips = len(clips)

    print(f"\n{Colors.bold('📊 Processando em lotes de')} {batch_size} clipes")
    print(f"{Colors.bold('=' * 60)}")

    # Processa em lotes
    for i in range(0, total_clips, batch_size):
        batch = clips[i : i + batch_size]
        batch_num = i // batch_size + 1
        total_batches = (total_clips + batch_size - 1) // batch_size

        print(f"\n{Colors.bold(f'📦 Lote {batch_num}/{total_batches}')}")
        print(f"{Colors.bold('-' * 40)}")

        # Cria tarefas para processamento paralelo dentro do lote
        tasks = []
        for j, clip in enumerate(batch):
            clip_idx = i + j + 1
            print(
                f"  {Colors.info(f'📝 Preparando clipe {clip_idx}/{total_clips}:')} {clip.name}"
            )
            tasks.append(process_clip_with_retry(subtitle_gen, clip))

        # Executa tarefas do lote em paralelo
        batch_results = await asyncio.gather(*tasks)

        # Processa resultados do lote
        for clip, result in zip(batch, batch_results):
            if result:
                clips_com_legendas.append(result)
                size_mb = result.stat().st_size / (1024 * 1024)
                print(
                    f"  {Colors.success(f'✅ Legendas adicionadas:')} {result.name} ({size_mb:.1f} MB)"
                )
            else:
                print(f"  {Colors.error(f'❌ Falha:')} {clip.name}")

        # Pequena pausa entre lotes para liberar recursos
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
        # Mostra ícone baseado no tipo de arquivo
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
        print_file_list(clips, "CLIPES BRUTOS GERADOS")
    else:
        print(f"\n{Colors.error('❌ Nenhum clipe foi gerado!')}")
        return

    # SEGUNDA ETAPA: Transcrever os clipes (se não for pulado)
    if not args.no_subtitles and clips:
        print(f"\n{Colors.bold('🎬 SEGUNDA ETAPA: GERANDO LEGENDAS')}")
        print(f"{Colors.bold('=' * 70)}")
        print(f"  {Colors.info('🎨 Estilo:')} Impact + Borda AZUL + Destaque Amarelo")
        print(f"  {Colors.info('🛡️ Proteção:')} Palavras ofensivas censuradas")
        print(f"{Colors.bold('-' * 70)}")

        # Inicializa o gerador de legendas (agora com a lógica word-by-word)
        subtitle_gen = SubtitleGenerator()

        # Mostra preview das palavras censuradas
        print(f"\n  {Colors.info('📋 Palavras protegidas:')}")
        bad_words_sample = list(subtitle_gen.BAD_WORDS.keys())[:5]
        for word in bad_words_sample:
            censored = subtitle_gen.BAD_WORDS[word]
            print(f"  • {word} → {censored} ⚠️")

        # Processa legendas em lotes
        start_time = asyncio.get_event_loop().time()
        clips_com_legendas = await process_subtitles_batch(
            clips, subtitle_gen, batch_size=args.batch_size
        )
        elapsed_time = asyncio.get_event_loop().time() - start_time

        # Status final das legendas
        print_status_header("STATUS DAS LEGENDAS")
        print(
            f"  {Colors.success('✅ Clipes com legendas:')} {len(clips_com_legendas)}/{len(clips)}"
        )
        print(f"  {Colors.info('⏱️ Tempo transcrição:')} {elapsed_time:.1f}s")

        if clips_com_legendas:
            print_file_list(clips_com_legendas, "CLIPES FINAIS COM LEGENDAS")
        else:
            print(f"\n{Colors.warning('⚠️ Nenhuma legenda foi gerada!')}")

    # FOOTER FINAL
    print(f"\n{Colors.bold('=' * 70)}")
    print(f"{Colors.success('✅ PROCESSAMENTO CONCLUÍDO COM SUCESSO!')}")
    print(f"{Colors.bold('=' * 70)}")

    # Localização dos arquivos
    print(f"\n{Colors.info('📁 ARQUIVOS GERADOS:')}")
    print(
        f"  {Colors.info('📼 Clipes brutos:')} {ROOT_DIR}/processed_videos/raw_clips/"
    )
    print(
        f"  {Colors.info('🎬 Clipes finais:')} {ROOT_DIR}/processed_videos/final_clips/"
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
