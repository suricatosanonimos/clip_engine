"""
src/utils/ffm_peg.py

Processador de legendas para clipes já cortados.
Lê clipes de raw_clips/, gera legendas word-by-word e salva em final_clips/.

Uso:
    python3 ffm_peg.py                          # Processa TODOS os clipes em raw_clips/
    python3 ffm_peg.py --batch-size 5           # 5 clipes em paralelo
    python3 ffm_peg.py --select 1,3,5           # Apenas clipes específicos
    python3 ffm_peg.py --video original.mp4     # Especifica vídeo original para áudio
"""

import asyncio
import subprocess
import sys
from pathlib import Path
from typing import List, Optional

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(ROOT_DIR))

from src.config.settings import Colors
from src.controllers.video_processing import TranscriberVideo
from src.services.transcriber import SubtitleGenerator
from src.utils.execution_time import execution_time_of_a_function
from src.utils.subtitle_constants import *


@execution_time_of_a_function
async def process_clip_with_retry(
    subtitle_gen: SubtitleGenerator,
    clip: Path,
    audio_path: Optional[Path] = None,
    max_retries: int = 2,
) -> Optional[Path]:
    """Processa um clipe com retry em caso de falha."""
    for attempt in range(max_retries + 1):
        try:
            if attempt > 0:
                print(f"  {Colors.warning(f'🔄 Tentativa {attempt}/{max_retries}...')}")

            if audio_path and audio_path.exists():
                final_clip = await subtitle_gen.process_video(
                    str(clip), audio_path=str(audio_path)
                )
            else:
                final_clip = await subtitle_gen.process_video(str(clip))

            if not final_clip or not Path(final_clip).exists():
                raise Exception("Falha ao gerar clipe com legendas")

            final_clip_path = Path(final_clip)

            # Adicionar áudio de volta
            if audio_path and audio_path.exists():
                final_com_audio = (
                    final_clip_path.parent / f"audio_{final_clip_path.name}"
                )

                cmd = [
                    "ffmpeg",
                    "-i",
                    str(final_clip_path),
                    "-i",
                    str(audio_path),
                    "-c:v",
                    "copy",
                    "-c:a",
                    "aac",
                    "-b:a",
                    "192k",
                    "-map",
                    "0:v:0",
                    "-map",
                    "1:a:0",
                    "-shortest",
                    "-y",
                    str(final_com_audio),
                ]

                result = subprocess.run(cmd, capture_output=True, text=True)

                if result.returncode == 0 and final_com_audio.exists():
                    final_clip_path.unlink()
                    final_com_audio.rename(final_clip_path)
                    return final_clip_path

            return final_clip_path

        except Exception as e:
            print(f"  {Colors.error(f'❌ Erro: {e}')}")

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
    """Processa legendas em lotes paralelos."""
    clips_com_legendas = []
    total_clips = len(clips)

    print(
        f"\n{Colors.bold(f'📊 Processando {total_clips} clipe(s) em lotes de {batch_size}')}"
    )
    print(f"{Colors.bold('=' * 60)}")

    for i in range(0, total_clips, batch_size):
        batch = clips[i : i + batch_size]
        batch_num = i // batch_size + 1
        total_batches = (total_clips + batch_size - 1) // batch_size

        print(f"\n{Colors.bold(f'📦 Lote {batch_num}/{total_batches}')}")
        print(f"{Colors.bold('-' * 40)}")

        # Extrai áudio do vídeo original (reusa para todos os clipes do lote)
        transcriber = TranscriberVideo(video_original_path)
        audio_path = transcriber.extract_audio()

        if audio_path:
            print(
                f"  {Colors.success('🎵 Áudio extraído do original:')} {audio_path.name}"
            )
        else:
            print(f"  {Colors.warning('⚠️ Falha ao extrair áudio')}")

        # Processa em paralelo
        tasks = [
            process_clip_with_retry(subtitle_gen, clip, audio_path) for clip in batch
        ]
        batch_results = await asyncio.gather(*tasks)

        # Limpa áudio
        if audio_path and audio_path.exists():
            transcriber.cleanup_audio(audio_path)

        # Resultados
        for clip, result in zip(batch, batch_results):
            if result:
                clips_com_legendas.append(result)
                size_mb = result.stat().st_size / (1024 * 1024)
                print(f"  {Colors.success('✅')} {result.name} ({size_mb:.1f} MB)")
            else:
                print(f"  {Colors.error('❌ Falha:')} {clip.name}")

        if i + batch_size < total_clips:
            print(f"\n  {Colors.info('⏳ Aguardando 2s...')}")
            await asyncio.sleep(2)

    return clips_com_legendas


def find_clips_to_process(
    raw_clips_dir: Path, select_indices: Optional[List[int]] = None
) -> List[Path]:
    """
    Encontra clipes para processar.
    Prioriza *_final.mp4, depois *_clip_*.mp4 (exclui _hook).
    """
    all_clips = sorted(raw_clips_dir.glob("*.mp4"))

    # Prioridade: _final > _clip_ > outros
    final_clips = [c for c in all_clips if "_final" in c.name]
    clip_clips = [c for c in all_clips if "_clip_" in c.name and "_final" not in c.name]
    outros = [
        c
        for c in all_clips
        if c not in final_clips and c not in clip_clips and "_hook" not in c.name
    ]

    candidates = final_clips + clip_clips + outros

    if select_indices:
        return [candidates[i - 1] for i in select_indices if 0 < i <= len(candidates)]

    return candidates


def find_original_video(downloads_dir: Path, raw_clips_dir: Path) -> Optional[Path]:
    """
    Encontra o vídeo original em downloads/ correspondente aos clipes.
    """
    # Tenta achar pelo nome base
    for clip in raw_clips_dir.glob("*_final.mp4"):
        base = clip.name.split("_clip_")[0].split("_final")[0]
        candidate = downloads_dir / f"{base}.mp4"
        if candidate.exists():
            return candidate

    # Primeiro .mp4 em downloads/ que não seja _hook ou _clip
    for v in sorted(downloads_dir.glob("*.mp4")):
        if "_hook" not in v.name and "_clip_" not in v.name:
            return v

    return None


async def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Gerador de legendas para clipes já cortados"
    )
    parser.add_argument(
        "--video", help="Caminho do vídeo original (para extrair áudio)"
    )
    parser.add_argument("--select", help="Índices dos clipes (ex: 1,3,5)")
    parser.add_argument("--batch-size", type=int, default=3, help="Clipes em paralelo")
    parser.add_argument(
        "--all", action="store_true", help="Processar todos sem perguntar"
    )

    args = parser.parse_args()

    # Diretórios
    raw_clips_dir = ROOT_DIR / "processed_videos" / "raw_clips"
    final_clips_dir = ROOT_DIR / "processed_videos" / "final_clips"
    downloads_dir = ROOT_DIR / "downloads"

    final_clips_dir.mkdir(parents=True, exist_ok=True)

    if not raw_clips_dir.exists():
        print(Colors.error(f"❌ Diretório não encontrado: {raw_clips_dir}"))
        return

    # Encontra clipes
    select = None
    if args.select:
        try:
            select = [int(x.strip()) for x in args.select.split(",")]
        except ValueError:
            print(Colors.warning("⚠️ Índices inválidos, processando todos"))

    clips = find_clips_to_process(raw_clips_dir, select)

    if not clips:
        print(Colors.warning("⚠️ Nenhum clipe encontrado em raw_clips/"))
        return

    # Encontra vídeo original
    if args.video:
        video_original = Path(args.video)
        if not video_original.exists():
            video_original = downloads_dir / args.video
    else:
        video_original = find_original_video(downloads_dir, raw_clips_dir)

    if not video_original or not video_original.exists():
        print(
            Colors.warning(
                "⚠️ Vídeo original não encontrado. O áudio não será adicionado."
            )
        )
        print(Colors.info("💡 Use --video para especificar o caminho."))
        video_original = None

    # HEADER
    print(f"\n{Colors.bold('=' * 70)}")
    print(f"{Colors.bold('🎯 GERADOR DE LEGENDAS - YOUTUBE SHORTS')}")
    print(f"{Colors.bold('=' * 70)}")

    print(f"\n{Colors.bold('⚙️ CONFIGURAÇÃO:')}")
    print(f"  {Colors.info('📁 Clipes:')} {len(clips)} encontrado(s)")
    print(
        f"  {Colors.info('📹 Original:')} {video_original.name if video_original else 'N/A'}"
    )
    print(f"  {Colors.info('🎨 Estilo:')} Impact + Borda AZUL + Word-by-Word")
    print(f"  {Colors.info('📦 Batch:')} {args.batch_size}")

    # Lista clipes
    print(f"\n{Colors.bold('📋 CLIPES:')}")
    for i, c in enumerate(clips, 1):
        size_mb = c.stat().st_size / (1024 * 1024)
        print(f"  {i}. {c.name} ({size_mb:.1f} MB)")

    # Confirma
    if not args.all:
        confirm = (
            input(f"\n{Colors.info('🎬 Processar esses clipes? (s/n):')} ")
            .strip()
            .lower()
        )
        if confirm != "s":
            print(Colors.warning("⚠️ Cancelado"))
            return

    print(f"\n{Colors.bold('=' * 70)}")
    print(f"{Colors.bold('📝 GERANDO LEGENDAS...')}")
    print(f"{Colors.bold('=' * 70)}")

    subtitle_gen = SubtitleGenerator()

    start_time = asyncio.get_event_loop().time()

    if video_original:
        clips_com_legendas = await process_subtitles_batch(
            clips, subtitle_gen, video_original, batch_size=args.batch_size
        )
    else:
        # Sem vídeo original: processa sem áudio extra
        tasks = [process_clip_with_retry(subtitle_gen, clip, None) for clip in clips]
        results = await asyncio.gather(*tasks)
        clips_com_legendas = [r for r in results if r is not None]

    elapsed = asyncio.get_event_loop().time() - start_time

    # Move para final_clips/ e renomeia
    final_clips = []
    for clip_path in clips_com_legendas:
        dest = final_clips_dir / clip_path.name
        if clip_path.parent != final_clips_dir:
            import shutil

            shutil.move(str(clip_path), str(dest))
        final_clips.append(dest)

    # FOOTER
    print(f"\n{Colors.bold('=' * 70)}")
    print(f"{Colors.success('✅ PROCESSAMENTO CONCLUÍDO!')}")
    print(f"{Colors.bold('=' * 70)}")
    print(
        f"  {Colors.success('🎬 Clipes com legenda:')} {len(final_clips)}/{len(clips)}"
    )
    print(f"  {Colors.info('⏱️ Tempo total:')} {elapsed:.1f}s")
    print(f"  {Colors.info('📁 Final clips:')} {final_clips_dir}")

    if final_clips:
        total_size = sum(f.stat().st_size for f in final_clips) / (1024 * 1024)
        print(f"  {Colors.info('📊 Tamanho total:')} {total_size:.1f} MB")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print(f"\n\n{Colors.warning('⚠️ Interrompido pelo usuário.')}")
        sys.exit(0)
    except Exception as e:
        print(f"\n{Colors.error(f'❌ Erro fatal: {e}')}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
