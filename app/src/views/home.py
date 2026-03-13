"""
Aba 1 — Novo Projeto.
Cole a URL do YouTube e dispare o pipeline de análise.
"""

import threading
import time

import flet as ft
from src.views.components import clip_card, tag
from src.views.models import ClipSugerido
from src.views.theme import C


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

    status_text = ft.Text("", size=12, color=C.TEXT_SECONDARY)
    progress_row = ft.ProgressBar(
        value=0,
        color=C.ACCENT,
        bgcolor=C.BORDER,
        height=3,
        border_radius=3,
        visible=False,
    )
    clips_column = ft.Column(spacing=10, visible=False)
    etapas_column = ft.Column(spacing=4)

    # ──────────────────────────────────────────────────────────────
    #  ETAPAS DO PIPELINE
    # ──────────────────────────────────────────────────────────────

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
                    [
                        ft.Icon(ic, size=16, color=cor),
                        ft.Text(
                            label,
                            size=12,
                            color=cor,
                            weight=(
                                ft.FontWeight.W_600
                                if i == etapa_atual
                                else ft.FontWeight.NORMAL
                            ),
                        ),
                    ],
                    spacing=8,
                )
            )
            if i < len(etapas) - 1:
                controles.append(
                    ft.Container(
                        width=1,
                        height=12,
                        bgcolor=C.BORDER,
                        margin=ft.margin.only(left=7),
                    )
                )
        etapas_column.controls = controles
        page.update()

    # ──────────────────────────────────────────────────────────────
    #  PIPELINE (fake — substitua pelas chamadas reais ao back-end)
    # ──────────────────────────────────────────────────────────────

    def simular_pipeline(origem: str):
        """
        Simula o pipeline completo.
        `origem` pode ser uma URL do YouTube ou o caminho de um arquivo local.
        Substitua cada bloco pela chamada real ao seu back-end.
        """
        # ETAPA 0 — Download / leitura do arquivo
        atualizar_etapas(0)
        status_text.value = (
            "Baixando vídeo..." if origem.startswith("http") else "Lendo arquivo..."
        )
        progress_row.visible = True
        for p in range(0, 101, 5):
            progress_row.value = p / 100
            page.update()
            time.sleep(0.06)
        # download_video(origem)  ←  substitua aqui
        pass

        # ETAPA 1 — Transcrição
        atualizar_etapas(1)
        status_text.value = "Transcrevendo com Whisper..."
        progress_row.value = 0
        for p in range(0, 101, 3):
            progress_row.value = p / 100
            page.update()
            time.sleep(0.08)
        # transcrever()  ←  substitua aqui
        pass

        # ETAPA 2 — Análise de IA
        atualizar_etapas(2)
        status_text.value = "Analisando momentos virais com IA..."
        progress_row.value = 0
        for p in range(0, 101, 4):
            progress_row.value = p / 100
            page.update()
            time.sleep(0.07)
        # clipes_brutos = analisar_momentos()  ←  substitua aqui
        pass

        # ETAPA 3 — Geração dos cards
        atualizar_etapas(3)
        status_text.value = "Gerando sugestões de clipes..."
        progress_row.value = 0.9
        page.update()
        time.sleep(0.4)

        clipes_mock = [
            ClipSugerido(
                1,
                "Momento de climax narrativo incrível",
                "02:14", "03:41", "1m27s",
                0.92,
                "Pico emocional detectado + variação de tom + palavras-gatilho de engajamento",
            ),
            ClipSugerido(
                2,
                "Revelação surpreendente no diálogo",
                "07:05", "08:10", "1m05s",
                0.78,
                "Alta densidade de palavras de alto impacto + pausa dramática detectada",
            ),
            ClipSugerido(
                3,
                "Introdução energética e direta",
                "00:00", "00:48", "48s",
                0.65,
                "Abertura com hook forte — potencial para retenção nos primeiros 3 segundos",
            ),
            ClipSugerido(
                4,
                "Trecho com insight técnico valioso",
                "12:33", "13:55", "1m22s",
                0.51,
                "Conteúdo informativo denso — desempenho histórico moderado em reels",
            ),
        ]

        clips_column.controls.clear()
        clips_column.controls.append(
            ft.Row(
                [
                    ft.Icon(ft.Icons.AUTO_AWESOME, color=C.ACCENT, size=16),
                    ft.Text(
                        f"{len(clipes_mock)} clipes sugeridos pela IA",
                        size=14,
                        weight=ft.FontWeight.W_700,
                        color=C.TEXT_PRIMARY,
                    ),
                    ft.Container(expand=True),
                    tag(
                        f"Score médio: {int(sum(c.score for c in clipes_mock) / len(clipes_mock) * 100)}%",
                        C.CYAN,
                        C.CYAN_SOFT,
                    ),
                ],
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            )
        )
        for clipe in clipes_mock:
            estado["clipes"][clipe.id] = clipe
            clips_column.controls.append(
                clip_card(clipe, on_renderizar_clipe, on_preview_clipe)
            )

        clips_column.visible = True
        progress_row.value   = 1.0
        status_text.value    = "✓ Análise concluída! Selecione os clipes para renderizar."
        status_text.color    = C.SUCCESS
        page.update()

    # ──────────────────────────────────────────────────────────────
    #  HANDLERS DE ENTRADA
    # ──────────────────────────────────────────────────────────────

    def on_iniciar_download(e):
        """Valida a URL e dispara o pipeline via download."""
        url = url_field.value.strip()
        if not url:
            url_field.border_color = C.ERROR
            status_text.value      = "⚠ Insira uma URL válida do YouTube."
            status_text.color      = C.ERROR
            page.update()
            return

        url_field.border_color  = C.BORDER_ACCENT
        status_text.color       = C.TEXT_SECONDARY
        clips_column.visible    = False
        etapas_column.controls  = []
        btn_download.disabled   = True
        btn_download.text       = "Processando..."
        page.update()

        threading.Thread(target=simular_pipeline, args=(url,), daemon=True).start()

    async def abrir_galeria_dispositivo(e: ft.Event[ft.Button]):
        """
        Abre o seletor de arquivos nativo filtrado apenas para vídeos.
        Em Android/iOS mostra a galeria de mídia; em desktop o explorador.
        Extensões aceitas: mp4, mov, mkv, avi, webm, 3gp, m4v.

        No Flet 0.81+, pick_files() é async e retorna a lista diretamente,
        sem necessidade de on_result ou page.overlay.
        """
        files = await ft.FilePicker().pick_files(
            dialog_title="Selecionar vídeo",
            allow_multiple=False,
            file_type=ft.FilePickerFileType.VIDEO,
        )

        if files:
            arquivo    = files[0]
            video_path = arquivo.path  # caminho absoluto no dispositivo

            btn_gallery.disabled   = True
            status_text.value      = f"Vídeo selecionado: {arquivo.name}"
            status_text.color      = C.ACCENT
            clips_column.visible   = False
            etapas_column.controls = []
            page.update()

            threading.Thread(
                target=simular_pipeline, args=(video_path,), daemon=True
            ).start()
        else:
            status_text.value = "Seleção cancelada."
            status_text.color = C.ERROR
            page.update()

    # ──────────────────────────────────────────────────────────────
    #  HANDLERS DE CLIPE (fake — substitua pelas chamadas reais)
    # ──────────────────────────────────────────────────────────────

    def on_renderizar_clipe(clipe: ClipSugerido):
        clipe.status    = "renderizando"
        clipe.progresso = 0.0
        _atualizar_cards()

        def _render():
            for p in range(0, 101, 2):
                clipe.progresso = p / 100
                time.sleep(0.04)
            # renderizar_clipe(clipe)  ←  substitua aqui
            pass
            clipe.status    = "pronto"
            clipe.progresso = 1.0
            _atualizar_cards()

        threading.Thread(target=_render, daemon=True).start()

    def on_preview_clipe(clipe: ClipSugerido):
        dlg = ft.AlertDialog(
            title=ft.Text(
                clipe.titulo, color=C.TEXT_PRIMARY, weight=ft.FontWeight.W_700
            ),
            content=ft.Column(
                [
                    ft.Row(
                        [
                            tag(f"⏱ {clipe.inicio} → {clipe.fim}", C.CYAN, C.CYAN_SOFT),
                            tag(
                                f"Score: {int(clipe.score * 100)}%",
                                C.SUCCESS if clipe.score >= 0.75 else C.WARNING,
                                C.SUCCESS_SOFT if clipe.score >= 0.75 else C.WARNING_SOFT,
                            ),
                        ],
                        spacing=8,
                    ),
                    ft.Container(height=8),
                    ft.Text(
                        "Motivo da seleção:",
                        size=12,
                        color=C.TEXT_SECONDARY,
                        weight=ft.FontWeight.W_600,
                    ),
                    ft.Text(clipe.motivo, size=13, color=C.TEXT_PRIMARY),
                    ft.Container(height=8),
                    ft.Container(
                        content=ft.Row(
                            [
                                ft.Icon(ft.Icons.INFO_OUTLINE, color=C.CYAN, size=14),
                                ft.Text(
                                    "Pré-visualização disponível após download.",
                                    size=12,
                                    color=C.TEXT_SECONDARY,
                                ),
                            ],
                            spacing=8,
                        ),
                        padding=ft.padding.all(10),
                        border_radius=6,
                        bgcolor=C.CYAN_SOFT,
                        border=ft.border.all(1, C.CYAN + "33"),
                    ),
                ],
                spacing=8,
                tight=True,
            ),
            bgcolor=C.SURFACE,
            shape=ft.RoundedRectangleBorder(radius=12),
            actions=[
                ft.TextButton(
                    "Fechar",
                    on_click=lambda e: page.close(dlg),
                    style=ft.ButtonStyle(color=C.TEXT_SECONDARY),
                ),
                ft.ElevatedButton(
                    "Renderizar este clipe",
                    on_click=lambda e: (page.close(dlg), on_renderizar_clipe(clipe)),
                    style=ft.ButtonStyle(
                        bgcolor=C.ACCENT,
                        color=C.BG,
                        shape=ft.RoundedRectangleBorder(radius=6),
                    ),
                ),
            ],
        )
        page.open(dlg)

    def _atualizar_cards():
        if len(clips_column.controls) > 1:
            for i, _ in enumerate(clips_column.controls[1:], 1):
                if i in estado["clipes"]:
                    clipe = estado["clipes"][i]
                    clips_column.controls[i] = clip_card(
                        clipe, on_renderizar_clipe, on_preview_clipe
                    )
        page.update()

    # ──────────────────────────────────────────────────────────────
    #  BOTÕES
    # ──────────────────────────────────────────────────────────────

    _btn_style = ft.ButtonStyle(
        color=C.BG,
        bgcolor={
            ft.ControlState.DEFAULT:  C.ACCENT,
            ft.ControlState.HOVERED:  "#FF8C42",
            ft.ControlState.DISABLED: C.BORDER,
        },
        shape=ft.RoundedRectangleBorder(radius=8),
        padding=ft.padding.symmetric(horizontal=24, vertical=14),
        text_style=ft.TextStyle(weight=ft.FontWeight.W_700, size=14),
        elevation=0,
    )

    # Analisa e baixa o vídeo da internet
    btn_download = ft.ElevatedButton(
        content=ft.Text("Analisar e Baixar"),
        icon=ft.Icons.ROCKET_LAUNCH_OUTLINED,
        on_click=on_iniciar_download,
        style=_btn_style,
    )

    # Abre o seletor de vídeos locais do dispositivo
    btn_gallery = ft.ElevatedButton(
        content=ft.Text("Adicionar da galeria"),
        icon=ft.Icons.VIDEO_LIBRARY_OUTLINED,
        on_click=abrir_galeria_dispositivo,  # async — Flet chama com await automaticamente
        style=_btn_style,
    )

    # ──────────────────────────────────────────────────────────────
    #  LAYOUT
    # ──────────────────────────────────────────────────────────────

    return ft.Column(
        [
            # Header da aba
            ft.Container(
                content=ft.Column(
                    [
                        ft.Row(
                            [
                                ft.Icon(ft.Icons.ADD_CIRCLE_OUTLINE, color=C.ACCENT, size=20),
                                ft.Text(
                                    "Novo Projeto",
                                    size=20,
                                    weight=ft.FontWeight.W_800,
                                    color=C.TEXT_PRIMARY,
                                ),
                            ],
                            spacing=10,
                        ),
                        ft.Text(
                            "Cole a URL do YouTube para extrair os melhores momentos.",
                            size=13,
                            color=C.TEXT_SECONDARY,
                        ),
                    ],
                    spacing=4,
                ),
                padding=ft.padding.only(bottom=16),
            ),

            # Card de entrada
            ft.Container(
                content=ft.Column(
                    [
                        ft.Text(
                            "URL do Vídeo",
                            size=12,
                            weight=ft.FontWeight.W_600,
                            color=C.TEXT_SECONDARY,
                        ),
                        ft.Row([url_field], spacing=0),
                        ft.Container(height=4),
                        ft.Row(
                            controls=[btn_gallery, btn_download],
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        ),
                    ],
                    spacing=8,
                ),
                padding=ft.padding.all(16),
                border_radius=10,
                bgcolor=C.SURFACE,
                border=ft.border.all(1, C.BORDER),
            ),

            ft.Container(height=4),

            # Painel de progresso do pipeline
            ft.Container(
                content=ft.Column(
                    [
                        ft.Row(
                            [
                                ft.Text(
                                    "Pipeline de processamento",
                                    size=12,
                                    weight=ft.FontWeight.W_600,
                                    color=C.TEXT_SECONDARY,
                                ),
                                ft.Container(expand=True),
                                status_text,
                            ],
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        ),
                        progress_row,
                        ft.Container(height=4),
                        etapas_column,
                    ],
                    spacing=8,
                ),
                padding=ft.padding.all(16),
                border_radius=10,
                bgcolor=C.SURFACE,
                border=ft.border.all(1, C.BORDER),
            ),

            ft.Container(height=8),

            # Lista de clipes sugeridos pela IA
            clips_column,
        ],
        spacing=8,
        scroll=ft.ScrollMode.AUTO,
        expand=True,
    )
