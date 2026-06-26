#!/usr/bin/env python3
"""
run_pipeline.py

Script principal para rodar todo o pipeline de processamento de vídeos.
Localizado na raiz do projeto: clip_engine/

Fluxo completo:
1. Download do vídeo (YouTube)
2. Corte em clipes 9:16 com gancho via IA
3. Transcrição e legendas
4. Processamento final com speaker tracking

Uso:
    python3 run_pipeline.py
"""

import asyncio
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import List, Optional

# Adiciona api/ ao path
ROOT_DIR = Path(__file__).resolve().parent
API_DIR = ROOT_DIR / "api"
sys.path.insert(0, str(API_DIR))

from src.utils.brain_selector import BrainSelector
from src.utils.video_splitter import VideoSplitterFast


class Colors:
    """Cores para terminal."""

    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"
    BOLD = "\033[1m"
    RESET = "\033[0m"

    @classmethod
    def success(cls, msg):
        return f"{cls.GREEN}{msg}{cls.RESET}"

    @classmethod
    def error(cls, msg):
        return f"{cls.RED}{msg}{cls.RESET}"

    @classmethod
    def warning(cls, msg):
        return f"{cls.YELLOW}{msg}{cls.RESET}"

    @classmethod
    def info(cls, msg):
        return f"{cls.CYAN}{msg}{cls.RESET}"

    @classmethod
    def bold(cls, msg):
        return f"{cls.BOLD}{msg}{cls.RESET}"

    @classmethod
    def header(cls, msg):
        return f"{cls.MAGENTA}{cls.BOLD}{msg}{cls.RESET}"


class PipelineRunner:
    """
    Orquestrador do pipeline completo.

    Etapas:
    1. Download → downloads/
    2. Corte + Gancho → processed_videos/raw_clips/
    3. Legendas → processed_videos/final_clips/
    """

    def __init__(self):
        self.downloads_dir = API_DIR / "downloads"
        self.raw_clips_dir = API_DIR / "processed_videos" / "raw_clips"
        self.final_clips_dir = API_DIR / "processed_videos" / "final_clips"
        self.transcriptions_dir = API_DIR / "processed_videos" / "transcriptions"
        self.moments_dir = API_DIR / "processed_videos" / "moments"

        # Cria diretórios
        for d in [
            self.downloads_dir,
            self.raw_clips_dir,
            self.final_clips_dir,
            self.transcriptions_dir,
            self.moments_dir,
        ]:
            d.mkdir(parents=True, exist_ok=True)

    def print_banner(self):
        """Imprime banner do sistema."""
        print(f"\n{Colors.header('=' * 70)}")
        print(f"{Colors.header('🎬 CLIP ENGINE - PIPELINE COMPLETO')}")
        print(f"{Colors.header('=' * 70)}")

    def print_menu(self):
        """Menu principal interativo."""
        print(f"\n{Colors.bold('📋 MENU PRINCIPAL:')}")
        print(
            f"  {Colors.info('1.')} Baixar vídeo do YouTube + Cortar em clipes + Gancho IA"
        )
        print(f"  {Colors.info('2.')} Processar vídeo já baixado (downloads/)")
        print(f"  {Colors.info('3.')} Processar clipes brutos existentes (raw_clips/)")
        print(f"  {Colors.info('4.')} Gerar legendas para clipes em raw_clips/")
        print(f"  {Colors.info('5.')} Pipeline COMPLETO (download → corte → legenda)")
        print(f"  {Colors.info('6.')} Limpar arquivos temporários")
        print(f"  {Colors.info('0.')} Sair")

    def list_videos_in_downloads(self) -> List[Path]:
        """Lista vídeos disponíveis em downloads/."""
        videos = sorted(self.downloads_dir.glob("*.mp4"))
        return [v for v in videos if "_hook" not in v.name and "_clip_" not in v.name]

    def list_clips_in_raw(self) -> List[Path]:
        """Lista clipes brutos em raw_clips/ (apenas _final.mp4)."""
        return sorted(self.raw_clips_dir.glob("*_final.mp4"))

    def list_raw_originals(self) -> List[Path]:
        """Lista clipes originais (sem _final, sem _hook)."""
        clips = sorted(self.raw_clips_dir.glob("*.mp4"))
        return [c for c in clips if "_final" not in c.name and "_hook" not in c.name]

    # ══════════════════════════════════════════════════════════════
    #  ETAPA 1: DOWNLOAD + CORTE + GANCHO
    # ══════════════════════════════════════════════════════════════

    def step_download_and_split(self):
        """Baixa vídeo do YouTube e corta em clipes com gancho."""
        from src.controllers.youtube.downloader import VideoDownloader

        print(f"\n{Colors.header('━' * 60)}")
        print(f"{Colors.header('📥 ETAPA 1: DOWNLOAD + CORTE + GANCHO')}")
        print(f"{Colors.header('━' * 60)}")

        url = input(f"\n{Colors.info('🔗 URL do YouTube:')} ").strip()
        if not url:
            print(Colors.warning("⚠️ URL vazia, voltando..."))
            return

        try:
            num_clips = int(
                input(f"{Colors.info('✂️  Quantos clipes? (3):')} ").strip() or "3"
            )
        except ValueError:
            num_clips = 3

        try:
            clip_dur = int(
                input(
                    f"{Colors.info('⏱️  Duração por clipe em segundos (90):')} "
                ).strip()
                or "90"
            )
        except ValueError:
            clip_dur = 90

        print(f"\n{Colors.info('🚀 Iniciando download e corte...')}")

        downloader = VideoDownloader()
        result = downloader.download_full_pipeline(
            url=url,
            num_parts=num_clips,
            clip_duration=clip_dur,
            moment_duration=8,
            output_format="9:16",
        )

        if result.get("status") == "completed":
            # print(f"\n{Colors.success(f'{result[\'parts_count\']} clipes gerados com gancho!')}")
            print(f"{Colors.info('📁 Local:')} {result['output_dir']}")
        else:
            print(Colors.error("❌ Falha no pipeline"))

    # ══════════════════════════════════════════════════════════════
    #  ETAPA 2: PROCESSAR VÍDEO JÁ BAIXADO
    # ══════════════════════════════════════════════════════════════

    def step_process_downloaded_video(self):
        """Processa um vídeo que já está em downloads/."""
        videos = self.list_videos_in_downloads()

        if not videos:
            print(Colors.warning("\n⚠️ Nenhum vídeo encontrado em downloads/"))
            print(Colors.info("Use a opção 1 para baixar um vídeo primeiro."))
            return

        print(f"\n{Colors.header('━' * 60)}")
        print(f"{Colors.header('📹 PROCESSAR VÍDEO BAIXADO')}")
        print(f"{Colors.header('━' * 60)}")

        print(f"\n{Colors.bold('📁 Vídeos disponíveis:')}")
        for i, v in enumerate(videos, 1):
            size_mb = v.stat().st_size / (1024 * 1024)
            print(f"  {Colors.info(f'{i}.')} {v.name} ({size_mb:.1f} MB)")

        try:
            choice = int(input(f"\n{Colors.info('🔢 Escolha:')} ").strip())
            if choice < 1 or choice > len(videos):
                print(Colors.warning("⚠️ Escolha inválida"))
                return
        except (ValueError, IndexError):
            print(Colors.warning("⚠️ Escolha inválida"))
            return

        video_path = videos[choice - 1]

        try:
            num_clips = int(
                input(f"{Colors.info('✂️  Quantos clipes? (3):')} ").strip() or "3"
            )
        except ValueError:
            num_clips = 3

        try:
            clip_dur = int(
                input(f"{Colors.info('⏱️  Duração por clipe (90):')} ").strip() or "90"
            )
        except ValueError:
            clip_dur = 90

        print(f"\n{Colors.info('🚀 Processando...')}")

        splitter = VideoSplitterFast(
            base_dir=self.raw_clips_dir, output_format="9:16", num_threads=2
        )

        # Extrai gancho
        hook = splitter.extract_hook(
            video_path=str(video_path), moment_duration=8, apply_transform=True
        )

        start_offset = hook.get("hook_end", 30) if hook else 30

        # Corta clipes
        clips = splitter.split_all_clips(
            video_path=str(video_path),
            clip_duration=clip_dur,
            num_clips=num_clips,
            start_offset=start_offset,
            apply_transform=True,
        )

        if clips and hook:
            clipes_json = self.raw_clips_dir / f"{video_path.stem}_clipes.json"
            final = splitter.prepend_hook_to_clips(
                hook_path=hook["path"],
                clips_json_path=str(clipes_json),
            )
            print(f"\n{Colors.success(f'✅ {len(final)} clipes finais com gancho!')}")
        elif clips:
            print(f"\n{Colors.success(f'✅ {len(clips)} clipes gerados (sem gancho)')}")
        else:
            print(Colors.error("❌ Nenhum clipe gerado"))

    # ══════════════════════════════════════════════════════════════
    #  ETAPA 3: PROCESSAR CLIPES BRUTOS EXISTENTES
    # ══════════════════════════════════════════════════════════════

    def step_process_raw_clips(self):
        """Processa clipes que já estão em raw_clips/ (adiciona gancho)."""
        # Verifica se há vídeos originais em downloads/ para extrair gancho
        videos = self.list_videos_in_downloads()
        raw_clips = self.list_raw_originals()

        if not raw_clips:
            print(Colors.warning("\n⚠️ Nenhum clipe bruto encontrado em raw_clips/"))
            return

        print(f"\n{Colors.header('━' * 60)}")
        print(f"{Colors.header('📼 PROCESSAR CLIPES BRUTOS')}")
        print(f"{Colors.header('━' * 60)}")

        print(f"\n{Colors.bold('📁 Clipes brutos encontrados:')} {len(raw_clips)}")
        for c in raw_clips[:5]:
            print(f"  • {c.name}")
        if len(raw_clips) > 5:
            print(f"  ... e mais {len(raw_clips) - 5}")

        if videos:
            print(f"\n{Colors.bold('📹 Vídeos originais disponíveis para gancho:')}")
            for i, v in enumerate(videos, 1):
                print(f"  {Colors.info(f'{i}.')} {v.name}")

            usar_gancho = (
                input(f"\n{Colors.info('🎯 Adicionar gancho? (s/n):')} ")
                .strip()
                .lower()
                == "s"
            )

            if usar_gancho and videos:
                try:
                    choice = int(
                        input(f"{Colors.info('🔢 Qual vídeo original? (1):')} ").strip()
                        or "1"
                    )
                    video_orig = videos[choice - 1]
                except (ValueError, IndexError):
                    video_orig = videos[0]

                splitter = VideoSplitterFast(
                    base_dir=self.raw_clips_dir, output_format="9:16"
                )
                hook = splitter.extract_hook(
                    str(video_orig), moment_duration=8, apply_transform=True
                )

                if hook:
                    # Encontra JSON de clipes
                    json_files = list(self.raw_clips_dir.glob("*_clipes.json"))
                    if json_files:
                        final = splitter.prepend_hook_to_clips(
                            hook_path=hook["path"],
                            clips_json_path=str(json_files[0]),
                        )
                        print(
                            f"\n{Colors.success(f'✅ {len(final)} clipes com gancho!')}"
                        )

        print(f"\n{Colors.info('💡 Clipes prontos para legenda. Use a opção 4.')}")

    # ══════════════════════════════════════════════════════════════
    #  ETAPA 4: GERAR LEGENDAS
    # ══════════════════════════════════════════════════════════════

    def step_generate_subtitles(self):
        """Gera legendas para clipes em raw_clips/."""
        final_clips = self.list_clips_in_raw()
        raw_clips = self.list_raw_originals()

        # Prioriza _final.mp4, depois originais
        clips_to_process = final_clips if final_clips else raw_clips

        if not clips_to_process:
            print(Colors.warning("\n⚠️ Nenhum clipe encontrado em raw_clips/"))
            return

        print(f"\n{Colors.header('━' * 60)}")
        print(f"{Colors.header('📝 GERAR LEGENDAS')}")
        print(f"{Colors.header('━' * 60)}")

        print(f"\n{Colors.bold('📁 Clipes disponíveis:')} {len(clips_to_process)}")
        for i, c in enumerate(clips_to_process[:10], 1):
            print(f"  {i}. {c.name}")
        if len(clips_to_process) > 10:
            print(f"  ... e mais {len(clips_to_process) - 10}")

        # Pergunta quais processar
        print(f"\n{Colors.info('Opções:')}")
        print(f"  {Colors.info('1.')} Processar TODOS")
        print(f"  {Colors.info('2.')} Escolher manualmente")

        op = input(f"\n{Colors.info('🔢 Opção (1):')} ").strip() or "1"

        if op == "2":
            indices = input(f"{Colors.info('📝 Índices (ex: 1,3,5):')} ").strip()
            try:
                idxs = [int(x.strip()) - 1 for x in indices.split(",")]
                selected = [
                    clips_to_process[i] for i in idxs if 0 <= i < len(clips_to_process)
                ]
            except:
                print(Colors.warning("⚠️ Índices inválidos, processando todos"))
                selected = clips_to_process
        else:
            selected = clips_to_process

        if not selected:
            print(Colors.warning("⚠️ Nenhum clipe selecionado"))
            return

        print(f"\n{Colors.info(f'🎬 Processando {len(selected)} clipe(s)...')}")

        # Chama o ffm_peg.py para cada clipe
        for i, clip in enumerate(selected, 1):
            print(f"\n{Colors.bold(f'📝 Clipe {i}/{len(selected)}: {clip.name}')}")

            cmd = [
                sys.executable,
                str(API_DIR / "src" / "utils" / "ffm_peg.py"),
                "--video",
                clip.name,
                "--num-shots",
                "1",
                "--duration",
                str(int(clip.stat().st_size / 1000000)),  # estimativa
                "--no-tracking",
            ]

            try:
                subprocess.run(cmd, cwd=str(API_DIR))
            except KeyboardInterrupt:
                print(Colors.warning("\n⚠️ Interrompido pelo usuário"))
                break
            except Exception as e:
                print(Colors.error(f"❌ Erro: {e}"))

        print(f"\n{Colors.success('✅ Legendas geradas!')}")
        print(f"{Colors.info('📁 Final clips:')} {self.final_clips_dir}")

    # ══════════════════════════════════════════════════════════════
    #  ETAPA 5: PIPELINE COMPLETO
    # ══════════════════════════════════════════════════════════════

    def step_full_pipeline(self):
        """Pipeline completo do início ao fim."""
        print(f"\n{Colors.header('━' * 60)}")
        print(f"{Colors.header('🚀 PIPELINE COMPLETO')}")
        print(f"{Colors.header('━' * 60)}")

        # 1. Download + Corte
        self.step_download_and_split()

        # 2. Verifica se há clipes gerados
        final_clips = self.list_clips_in_raw()
        if not final_clips:
            print(Colors.warning("\n⚠️ Nenhum clipe gerado. Pulando legendas."))
            return

        # 3. Legendas
        gerar = (
            input(f"\n{Colors.info('📝 Gerar legendas agora? (s/n):')} ")
            .strip()
            .lower()
        )
        if gerar == "s":
            self.step_generate_subtitles()

    # ══════════════════════════════════════════════════════════════
    #  ETAPA 6: LIMPEZA
    # ══════════════════════════════════════════════════════════════

    def step_cleanup(self):
        """Remove arquivos temporários."""
        print(f"\n{Colors.header('━' * 60)}")
        print(f"{Colors.header('🧹 LIMPEZA DE ARQUIVOS')}")
        print(f"{Colors.header('━' * 60)}")

        removed = 0

        # Remove clipes originais (mantém _final)
        for clip in self.raw_clips_dir.glob("*.mp4"):
            if "_final" not in clip.name and "_hook" not in clip.name:
                try:
                    os.remove(clip)
                    removed += 1
                except Exception:
                    pass

        # Remove JSONs temporários
        for pattern in ["*_clipes.json", "*_analysis.json", "*_analysis_temp*"]:
            for f in self.raw_clips_dir.glob(pattern):
                try:
                    os.remove(f)
                    removed += 1
                except Exception:
                    pass
            for f in self.moments_dir.glob(pattern):
                try:
                    os.remove(f)
                    removed += 1
                except Exception:
                    pass

        print(f"\n{Colors.success(f'✅ {removed} arquivos removidos!')}")

    # ══════════════════════════════════════════════════════════════
    #  LOOP PRINCIPAL
    # ══════════════════════════════════════════════════════════════

    def run(self):
        """Executa o menu interativo."""
        self.print_banner()

        while True:
            # Mostra status rápido
            videos = self.list_videos_in_downloads()
            raw = self.list_raw_originals()
            final = self.list_clips_in_raw()

            print(f"\n{Colors.bold('📊 STATUS:')}")
            print(f"  📥 Downloads: {Colors.info(str(len(videos)))} vídeo(s)")
            print(
                f"  📼 Raw clips: {Colors.info(str(len(raw)))} bruto(s), {Colors.info(str(len(final)))} final(is)"
            )

            self.print_menu()

            choice = input(f"\n{Colors.info('🔢 Escolha:')} ").strip()

            if choice == "1":
                self.step_download_and_split()
            elif choice == "2":
                self.step_process_downloaded_video()
            elif choice == "3":
                self.step_process_raw_clips()
            elif choice == "4":
                self.step_generate_subtitles()
            elif choice == "5":
                self.step_full_pipeline()
            elif choice == "6":
                self.step_cleanup()
            elif choice == "0":
                print(f"\n{Colors.success('👋 Até logo!')}")
                break
            else:
                print(Colors.warning("⚠️ Opção inválida"))


if __name__ == "__main__":
    try:
        runner = PipelineRunner()
        runner.run()
    except KeyboardInterrupt:
        print(f"\n\n{Colors.warning('⚠️ Interrompido pelo usuário.')}")
        sys.exit(0)
    except Exception as e:
        print(f"\n{Colors.error(f'❌ Erro fatal: {e}')}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
