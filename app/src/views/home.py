"""
Aba 1 — Novo Projeto.
Versão atual: consome a API FastAPI via HTTP.
Próxima etapa: integrar upload para Supabase Storage.
"""

import threading
import time
from pathlib import Path

import flet as ft
import httpx

from src.views.components import clip_card, tag
from src.views.models import ClipSugerido
from src.views.theme import C

API_BASE_URL    = "http://127.0.0.1:8000"
REQUEST_TIMEOUT = 30


def build_aba_novo_projeto(estado: dict, page: ft.Page) -> ft.Control:

    url_field = ft.TextField(
        hint_text="https://www.youtube.com/watch?v=...",
        hint_style=ft.TextStyle(color=C.TEXT_MUTED),
        prefix_icon=ft.Icons.LINK,
        border_color=C.BORDER_ACCENT,
        focused_border_color=C.ACCENT,
        cursor_color=C.ACCENT,
        color=C.TEXT_PRIMARY,
        bgcolor=C.SURFACE_2,
        border_radius=8,
        text_style=ft.TextStyle(font_family="monospace", size=13),
        expand=True,
    )

    status_text   = ft.Text("", size=12, color=C.TEXT_SECONDARY)
    progress_row  = ft.ProgressBar(
        value=0, color=C.ACCENT, bgcolor=C.BORDER,
        height=3, border_radius=3, visible=False,
    )
    clips_column  = ft.Column(spacing=10, visible=False)
    etapas_column = ft.Column(spacing=4)

    _STATUS_ETAPA = {
        "pending":      0,
        "downloading":  0,
        "processing":   1,
        "transcribing": 2,
        "analyzing":    2,
        "done":         3,
        "error":        3,
    }

    # ── Notificação ────────────────────────────────────────────────

    def _notificar(mensagem: str, cor: str = C.SUCCESS, duracao: int = 6000):
        icone = (
            ft.Icons.CHECK_CIRCLE if cor == C.SUCCESS
            else ft.Icons.INFO    if cor == C.CYAN
            else ft.Icons.ERROR
        )
        page.snack_bar = ft.SnackBar(
            content=ft.Row(
                spacing=10,
                controls=[
                    ft.Icon(icone, color=cor, size=18),
                    ft.Text(mensagem, color=C.TEXT_PRIMARY, size=13, expand=True),
                ],
            ),
            bgcolor=C.SURFACE_2,
            duration=duracao,
            show_close_icon=True,
            close_icon_color=C.TEXT_SECONDARY,
        )
        page.snack_bar.open = True
        page.update()

    # ── Etapas visuais ─────────────────────────────────────────────

    def atualizar_etapas(etapa_atual: int):
        etapas = [
            (ft.Icons.DOWNLOAD_OUTLINED,       "Download do vídeo"),
            (ft.Icons.GRAPHIC_EQ,              "Transcrição Whisper"),
            (ft.Icons.PSYCHOLOGY_OUTLINED,     "Análise de IA"),
            (ft.Icons.MOVIE_CREATION_OUTLINED, "Geração de clipes"),
        ]
        controles = []
        for i, (icone, label) in enumerate(etapas):
            if i < etapa_atual:
                cor, ic = C.SUCCESS, ft.Icons.CHECK_CIRCLE
            elif i == etapa_atual:
                cor, ic = C.ACCENT, icone
            else:
                cor, ic = C.TEXT_MUTED, icone

            controles.append(
                ft.Row(
                    spacing=8,
                    controls=[
                        ft.Icon(ic, size=16, color=cor),
                        ft.Text(
                            label, size=12, color=cor,
                            weight=(
                                ft.FontWeight.W_600 if i == etapa_atual
                                else ft.FontWeight.NORMAL
                            ),
                        ),
                    ],
                )
            )
            if i < len(etapas) - 1:
                controles.append(
                    ft.Container(
                        width=1, height=12, bgcolor=C.BORDER,
                        margin=ft.Margin(left=7, right=0, top=0, bottom=0),
                    )
                )
        etapas_column.controls = controles
        page.update()

    # ── Helpers UI ─────────────────────────────────────────────────

    def _set_erro(mensagem: str):
        status_text.value     = f"✗ {mensagem}"
        status_text.color     = C.ERROR
        progress_row.visible  = False
        btn_download.disabled = False
        btn_gallery.disabled  = False
        page.update()
        _notificar(f"Erro: {mensagem[:80]}", cor=C.ERROR, duracao=8000)

    def _set_sucesso(mensagem: str):
        status_text.value  = mensagem
        status_text.color  = C.SUCCESS
        progress_row.value = 1.0
        page.update()

    def _popular_cards(clips_api: list):
        if not clips_api:
            _set_erro("Nenhum clipe foi gerado. Verifique o vídeo e tente novamente.")
            return

        clipes = []
        for item in clips_api:
            clipe = ClipSugerido(
                id=item.get("index", len(clipes) + 1),
                titulo=Path(item["filename"]).stem.replace("_", " ").title(),
                inicio="--:--",
                fim="--:--",
                duracao="~60s",
                score=0.0,
                motivo=f"Clipe gerado automaticamente. ({item.get('size_mb', 0):.1f} MB)",
                status="pronto",
                progresso=1.0,
            )
            estado["clipes"][clipe.id] = clipe
            clipes.append(clipe)

        clips_column.controls.clear()
        clips_column.controls.append(
            ft.Row(
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    ft.Icon(ft.Icons.MOVIE_FILTER, color=C.ACCENT, size=16),
                    ft.Text(
                        f"{len(clipes)} clipes gerados",
                        size=14, weight=ft.FontWeight.W_700, color=C.TEXT_PRIMARY,
                    ),
                    ft.Container(expand=True),
                    tag(f"{len(clipes)} clipes", C.CYAN, C.CYAN_SOFT),
                ],
            )
        )
        for clipe in clipes:
            clips_column.controls.append(
                clip_card(clipe, on_renderizar_clipe, on_preview_clipe)
            )

        clips_column.visible = True
        _set_sucesso(f"✓ {len(clipes)} clipes prontos!")
        _notificar(
            f"✅ Concluído! {len(clipes)} clipes prontos na galeria.",
            cor=C.SUCCESS, duracao=8000,
        )

    # ── Polling ────────────────────────────────────────────────────

    def _proximo_intervalo(elapsed: float) -> float:
        if elapsed < 120:   return 5.0
        elif elapsed < 300: return 10.0
        else:               return 15.0

    def _aguardar_task(task_id: str):
        elapsed   = 0.0
        intervalo = 5.0

        with httpx.Client(
            base_url=API_BASE_URL,
            timeout=httpx.Timeout(connect=10, read=30, write=10, pool=10),
        ) as client:
            while True:
                try:
                    resp = client.get(f"/api/status/{task_id}")
                    resp.raise_for_status()
                    data = resp.json()
                except httpx.ConnectError:
                    _set_erro("Conexão com a API perdida. Verifique se está rodando.")
                    return
                except httpx.TimeoutException:
                    time.sleep(intervalo)
                    elapsed  += intervalo
                    intervalo = _proximo_intervalo(elapsed)
                    continue
                except Exception as e:
                    _set_erro(f"Erro ao consultar status: {e}")
                    return

                api_status = data.get("status", "pending")
                progresso  = float(data.get("progress", 0.0))
                mensagem   = data.get("message", "")

                atualizar_etapas(_STATUS_ETAPA.get(api_status, 0))
                progress_row.value = progresso
                status_text.value  = mensagem
                status_text.color  = C.ERROR if api_status == "error" else C.TEXT_SECONDARY
                page.update()

                if api_status == "done":
                    _popular_cards(data.get("clips", []))
                    btn_download.disabled = False
                    btn_gallery.disabled  = False
                    return

                if api_status == "error":
                    _set_erro(data.get("error") or mensagem or "Erro desconhecido na API.")
                    return

                intervalo = _proximo_intervalo(elapsed)
                time.sleep(intervalo)
                elapsed += intervalo

    # ── Pipeline YouTube ───────────────────────────────────────────

    def _pipeline_youtube(url: str):
        try:
            with httpx.Client(
                base_url=API_BASE_URL,
                timeout=httpx.Timeout(connect=10, read=REQUEST_TIMEOUT, write=10, pool=5),
            ) as client:
                resp = client.post(
                    "/api/video/process",
                    json={
                        "url":           url,
                        "num_clips":     10,
                        "clip_duration": 60,
                        "tracking":      True,
                        "subtitles":     False,
                    },
                )
                resp.raise_for_status()
                task_id = resp.json().get("task_id")

            if not task_id:
                _set_erro("API não retornou task_id.")
                return

            status_text.value = f"⏳ Processando no servidor... (task: {task_id})"
            status_text.color = C.TEXT_SECONDARY
            page.update()

            _notificar(
                "Processamento iniciado! Você pode usar outras abas.",
                cor=C.CYAN, duracao=5000,
            )
            _aguardar_task(task_id)

        except httpx.ConnectError:
            _set_erro(f"Não foi possível conectar à API em {API_BASE_URL}.")
        except httpx.HTTPStatusError as e:
            _set_erro(f"Erro da API: {e.response.status_code} — {e.response.text[:200]}")
        except Exception as exc:
            _set_erro(str(exc))

    # ── Pipeline Local / Android ───────────────────────────────────

    def _pipeline_local(nome_arquivo: str, conteudo, path_str):
        try:
            import io

            if conteudo is None and path_str:
                src = Path(path_str)
                if not src.exists():
                    _set_erro(f"Arquivo não encontrado: {src.name}")
                    return
                conteudo = src.read_bytes()

            if not conteudo:
                _set_erro("Não foi possível ler o arquivo.")
                return

            status_text.value  = f"Enviando {nome_arquivo} para o servidor..."
            progress_row.value = 0.05
            page.update()

            upload_timeout = httpx.Timeout(connect=15, read=900, write=900, pool=10)

            with httpx.Client(base_url=API_BASE_URL, timeout=upload_timeout) as client:
                resp = client.post(
                    "/api/video/upload",
                    files={"file": (nome_arquivo, io.BytesIO(conteudo), "video/mp4")},
                    data={"num_clips": "10", "clip_duration": "60", "tracking": "true"},
                )
                resp.raise_for_status()
                task_id = resp.json().get("task_id")

            if not task_id:
                _set_erro("API não retornou task_id.")
                return

            status_text.value  = f"⏳ Upload concluído. Processando... (task: {task_id})"
            status_text.color  = C.TEXT_SECONDARY
            progress_row.value = 0.15
            page.update()

            _notificar(
                "Upload enviado! Você pode usar outras abas.",
                cor=C.CYAN, duracao=5000,
            )
            _aguardar_task(task_id)

        except httpx.ConnectError:
            _set_erro(f"Não foi possível conectar à API em {API_BASE_URL}.")
        except httpx.HTTPStatusError as e:
            _set_erro(f"Erro da API: {e.response.status_code} — {e.response.text[:200]}")
        except Exception as exc:
            _set_erro(str(exc))

    # ── Handlers de entrada ────────────────────────────────────────

    def on_iniciar_download(e):
        url = url_field.value.strip()
        if not url:
            url_field.border_color = C.ERROR
            status_text.value      = "⚠ Insira uma URL válida do YouTube."
            status_text.color      = C.ERROR
            page.update()
            return

        url_field.border_color  = C.BORDER_ACCENT
        clips_column.visible    = False
        etapas_column.controls  = []
        btn_download.disabled   = True
        btn_gallery.disabled    = True
        progress_row.visible    = True
        progress_row.value      = 0.0
        page.update()

        threading.Thread(target=_pipeline_youtube, args=(url,), daemon=True).start()

    async def abrir_galeria_dispositivo(e):
        files = await ft.FilePicker().pick_files(
            dialog_title="Selecionar vídeo",
            allow_multiple=False,
            file_type=ft.FilePickerFileType.VIDEO,
        )

        if not files:
            status_text.value = "Seleção cancelada."
            status_text.color = C.TEXT_SECONDARY
            page.update()
            return

        arquivo  = files[0]
        nome     = arquivo.name or "video.mp4"
        conteudo = getattr(arquivo, "bytes", None)
        path_str = getattr(arquivo, "path",  None)

        if conteudo is None and path_str is None:
            _set_erro("Não foi possível ler o arquivo. Verifique as permissões.")
            return

        btn_gallery.disabled   = True
        btn_download.disabled  = True
        clips_column.visible   = False
        etapas_column.controls = []
        progress_row.visible   = True
        progress_row.value     = 0.0
        status_text.value      = f"Preparando: {nome}"
        status_text.color      = C.ACCENT
        page.update()

        threading.Thread(
            target=_pipeline_local,
            args=(nome, conteudo, path_str),
            daemon=True,
        ).start()

    # ── Handlers de clipe ──────────────────────────────────────────

    def on_renderizar_clipe(clipe: ClipSugerido):
        clipe.status    = "renderizando"
        clipe.progresso = 0.0
        _atualizar_cards()

        def _render():
            # renderizar_clipe(clipe)  ← conectar quando disponível
            pass
            clipe.status    = "pronto"
            clipe.progresso = 1.0
            _atualizar_cards()

        threading.Thread(target=_render, daemon=True).start()

    def _fechar_dlg(dlg):
        dlg.open = False
        page.update()

    def on_preview_clipe(clipe: ClipSugerido):
        dlg = ft.AlertDialog(
            title=ft.Text(
                clipe.titulo, color=C.TEXT_PRIMARY, weight=ft.FontWeight.W_700,
            ),
            content=ft.Column(
                spacing=8, tight=True,
                controls=[
                    ft.Row(
                        spacing=8,
                        controls=[
                            tag(f"⏱ {clipe.inicio} → {clipe.fim}", C.CYAN, C.CYAN_SOFT),
                            tag(
                                f"Score: {int(clipe.score * 100)}%",
                                C.SUCCESS if clipe.score >= 0.75 else C.WARNING,
                                C.SUCCESS_SOFT if clipe.score >= 0.75 else C.WARNING_SOFT,
                            ),
                        ],
                    ),
                    ft.Container(height=8),
                    ft.Text(
                        "Motivo da seleção:", size=12,
                        color=C.TEXT_SECONDARY, weight=ft.FontWeight.W_600,
                    ),
                    ft.Text(clipe.motivo, size=13, color=C.TEXT_PRIMARY),
                    ft.Container(height=8),
                    ft.Container(
                        border_radius=6,
                        bgcolor=C.CYAN_SOFT,
                        border=ft.Border(
                            left=ft.BorderSide(1, C.CYAN + "33"),
                            right=ft.BorderSide(1, C.CYAN + "33"),
                            top=ft.BorderSide(1, C.CYAN + "33"),
                            bottom=ft.BorderSide(1, C.CYAN + "33"),
                        ),
                        padding=ft.Padding(left=10, right=10, top=10, bottom=10),
                        content=ft.Row(
                            spacing=8,
                            controls=[
                                ft.Icon(ft.Icons.INFO_OUTLINE, color=C.CYAN, size=14),
                                ft.Text(
                                    "Pré-visualização disponível após processamento.",
                                    size=12, color=C.TEXT_SECONDARY,
                                ),
                            ],
                        ),
                    ),
                ],
            ),
            bgcolor=C.SURFACE,
            shape=ft.RoundedRectangleBorder(radius=12),
            actions=[
                ft.TextButton(
                    "Fechar",
                    on_click=lambda e: _fechar_dlg(dlg),
                    style=ft.ButtonStyle(color=C.TEXT_SECONDARY),
                ),
                ft.FilledButton(
                    "Renderizar este clipe",
                    on_click=lambda e: (_fechar_dlg(dlg), on_renderizar_clipe(clipe)),
                    style=ft.ButtonStyle(
                        bgcolor=C.ACCENT, color=C.BG,
                        shape=ft.RoundedRectangleBorder(radius=6),
                    ),
                ),
            ],
        )
        page.dialog = dlg
        dlg.open    = True
        page.update()

    def _atualizar_cards():
        if len(clips_column.controls) > 1:
            for i, _ in enumerate(clips_column.controls[1:], 1):
                if i in estado["clipes"]:
                    clipe = estado["clipes"][i]
                    clips_column.controls[i] = clip_card(
                        clipe, on_renderizar_clipe, on_preview_clipe
                    )
        page.update()

    # ── Botões ─────────────────────────────────────────────────────

    _btn_style = ft.ButtonStyle(
        color=C.BG,
        bgcolor={
            ft.ControlState.DEFAULT:  C.ACCENT,
            ft.ControlState.HOVERED:  "#FF8C42",
            ft.ControlState.DISABLED: C.BORDER,
        },
        shape=ft.RoundedRectangleBorder(radius=8),
        padding=ft.Padding(left=24, right=24, top=14, bottom=14),
        text_style=ft.TextStyle(weight=ft.FontWeight.W_700, size=14),
        elevation=0,
    )

    btn_download = ft.FilledButton(
        content=ft.Row(
            spacing=8, tight=True,
            controls=[
                ft.Icon(ft.Icons.ROCKET_LAUNCH_OUTLINED, size=16),
                ft.Text("Analisar e Baixar", weight=ft.FontWeight.W_700, size=14),
            ],
        ),
        on_click=on_iniciar_download,
        style=_btn_style,
    )

    btn_gallery = ft.FilledButton(
        content=ft.Row(
            spacing=8, tight=True,
            controls=[
                ft.Icon(ft.Icons.VIDEO_LIBRARY_OUTLINED, size=16),
                ft.Text("Adicionar da galeria", weight=ft.FontWeight.W_700, size=14),
            ],
        ),
        on_click=abrir_galeria_dispositivo,
        style=_btn_style,
    )

    # ── Layout ─────────────────────────────────────────────────────

    def _borda():
        return ft.Border(
            left=ft.BorderSide(1, C.BORDER), right=ft.BorderSide(1, C.BORDER),
            top=ft.BorderSide(1, C.BORDER),  bottom=ft.BorderSide(1, C.BORDER),
        )

    return ft.Column(
        spacing=8,
        scroll=ft.ScrollMode.AUTO,
        expand=True,
        controls=[
            ft.Container(
                padding=ft.Padding(left=0, right=0, top=0, bottom=16),
                content=ft.Column(
                    spacing=4,
                    controls=[
                        ft.Row(
                            spacing=10,
                            controls=[
                                ft.Icon(ft.Icons.ADD_CIRCLE_OUTLINE, color=C.ACCENT, size=20),
                                ft.Text(
                                    "Novo Projeto", size=20,
                                    weight=ft.FontWeight.W_800, color=C.TEXT_PRIMARY,
                                ),
                            ],
                        ),
                        ft.Text(
                            "Cole a URL do YouTube para extrair os melhores momentos.",
                            size=13, color=C.TEXT_SECONDARY,
                        ),
                    ],
                ),
            ),

            ft.Container(
                border_radius=10, bgcolor=C.SURFACE, border=_borda(),
                padding=ft.Padding(left=16, right=16, top=16, bottom=16),
                content=ft.Column(
                    spacing=8,
                    controls=[
                        ft.Text(
                            "URL do Vídeo", size=12,
                            weight=ft.FontWeight.W_600, color=C.TEXT_SECONDARY,
                        ),
                        ft.Row(controls=[url_field], spacing=0),
                        ft.Container(height=4),
                        ft.Row(
                            controls=[btn_gallery, btn_download],
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        ),
                    ],
                ),
            ),

            ft.Container(height=4),

            ft.Container(
                border_radius=10, bgcolor=C.SURFACE, border=_borda(),
                padding=ft.Padding(left=16, right=16, top=16, bottom=16),
                content=ft.Column(
                    spacing=8,
                    controls=[
                        ft.Row(
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            controls=[
                                ft.Text(
                                    "Pipeline de processamento", size=12,
                                    weight=ft.FontWeight.W_600, color=C.TEXT_SECONDARY,
                                ),
                                ft.Container(expand=True),
                                status_text,
                            ],
                        ),
                        progress_row,
                        ft.Container(height=4),
                        etapas_column,
                    ],
                ),
            ),

            ft.Container(height=8),
            clips_column,
        ],
    )
