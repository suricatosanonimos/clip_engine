"""
╔══════════════════════════════════════════════════════════════════╗
║  CLIP ENGINE — Interface Flet                                    ║
║  Tema: Dark Cinematic / Industrial                               ║
╠══════════════════════════════════════════════════════════════════╣
║  Estrutura:                                                      ║
║  • Navegação inferior: Novo Projeto | Processamento | Galeria    ║
║  • src/controllers/ → orquestra o fluxo                         ║
║  • src/services/    → downloader, transcriber, brain_IA         ║
║  • src/utils/       → ffmpeg, helpers                           ║
╠══════════════════════════════════════════════════════════════════╣
║  pip install flet                                               ║
║  python main.py                                                  ║
╚══════════════════════════════════════════════════════════════════╝
"""

import flet as ft
import threading
import time
import random
from dataclasses import dataclass, field
from typing import Optional

# ─── Importações do back-end (comentadas se não estiverem prontas) ─
# from src.controllers.project_controller import ProjectController
# from src.services.downloader import download_video
# from src.services.transcriber import transcrever
# from src.services.brain_IA import analisar_momentos
# from src.utils.ffm_peg import renderizar_clipe


# ══════════════════════════════════════════════════════════════════
#  PALETA & TOKENS DE DESIGN
# ══════════════════════════════════════════════════════════════════

class C:
    """Cores do sistema — Dark Cinematic Industrial."""

    # Superfícies
    BG          = "#0A0A0C"        # fundo principal — quase preto azulado
    SURFACE     = "#111116"        # cards e painéis
    SURFACE_2   = "#18181F"        # superfícies elevadas
    BORDER      = "#2A2A38"        # bordas sutis
    BORDER_ACCENT = "#3D3D55"      # borda com mais presença

    # Texto
    TEXT_PRIMARY   = "#F0F0F5"
    TEXT_SECONDARY = "#888899"
    TEXT_MUTED     = "#44445A"

    # Acento principal — laranja-âmbar (energia, criação)
    ACCENT         = "#FF6B1A"
    ACCENT_SOFT    = "#FF6B1A22"
    ACCENT_GLOW    = "#FF6B1A44"

    # Acento secundário — ciano elétrico (tech, IA)
    CYAN           = "#00C8FF"
    CYAN_SOFT      = "#00C8FF18"

    # Semânticas
    SUCCESS        = "#22C55E"
    SUCCESS_SOFT   = "#22C55E18"
    WARNING        = "#F59E0B"
    WARNING_SOFT   = "#F59E0B18"
    ERROR          = "#EF4444"
    ERROR_SOFT     = "#EF444418"

    # Score de viralização (gradiente por faixa)
    SCORE_LOW      = "#EF4444"
    SCORE_MID      = "#F59E0B"
    SCORE_HIGH     = "#22C55E"


# ══════════════════════════════════════════════════════════════════
#  MODELOS DE DADOS
# ══════════════════════════════════════════════════════════════════

@dataclass
class ClipSugerido:
    id: int
    titulo: str
    inicio: str
    fim: str
    duracao: str
    score: float           # 0.0 a 1.0
    motivo: str
    status: str = "pendente"   # pendente | renderizando | pronto | erro
    progresso: float = 0.0


@dataclass
class Projeto:
    id: int
    url: str
    titulo: str
    duracao: str
    status: str = "aguardando"
    progresso_geral: float = 0.0
    clipes: list = field(default_factory=list)


# ══════════════════════════════════════════════════════════════════
#  COMPONENTES REUTILIZÁVEIS
# ══════════════════════════════════════════════════════════════════

def divider():
    return ft.Container(height=1, bgcolor=C.BORDER, margin=ft.margin.symmetric(vertical=8))


def tag(texto: str, cor: str = C.ACCENT, bg: str = C.ACCENT_SOFT):
    return ft.Container(
        content=ft.Text(texto, size=10, weight=ft.FontWeight.W_600,
                        color=cor, font_family="monospace"),
        padding=ft.padding.symmetric(horizontal=8, vertical=3),
        border_radius=4,
        bgcolor=bg,
        border=ft.border.all(1, cor + "55"),
    )


def score_badge(score: float):
    """Exibe o Score de Viralização com cor dinâmica."""
    pct = int(score * 100)
    if pct >= 75:
        cor, bg, label = C.SUCCESS, C.SUCCESS_SOFT, "VIRAL"
    elif pct >= 50:
        cor, bg, label = C.WARNING, C.WARNING_SOFT, "BOM"
    else:
        cor, bg, label = C.SCORE_LOW, C.ERROR_SOFT, "BAIXO"

    return ft.Container(
        content=ft.Column(
            [
                ft.Text(f"{pct}", size=26, weight=ft.FontWeight.W_900,
                        color=cor, font_family="monospace"),
                ft.Text(label, size=9, weight=ft.FontWeight.W_700,
                        color=cor, font_family="monospace"),
            ],
            spacing=0,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        width=64,
        height=64,
        border_radius=8,
        bgcolor=bg,
        border=ft.border.all(1, cor + "66"),
        alignment=ft.alignment.CENTER,
    )


def progress_bar_estilizada(valor: float, cor: str = C.ACCENT, altura: int = 4):
    """Barra de progresso customizada com brilho."""
    return ft.Stack(
        [
            ft.Container(height=altura, border_radius=altura,
                         bgcolor=C.BORDER, expand=True),
            ft.Container(
                height=altura,
                border_radius=altura,
                bgcolor=cor,
                width=None,
                expand=False,
                # A largura é controlada via FractionallySizedBox
            ),
        ]
    )


def status_chip(status: str):
    mapa = {
        "aguardando":   (C.TEXT_MUTED,   C.SURFACE_2,  "⏸ Aguardando"),
        "baixando":     (C.CYAN,          C.CYAN_SOFT,  "⬇ Baixando"),
        "transcrevendo":(C.WARNING,       C.WARNING_SOFT,"🎙 Transcrevendo"),
        "analisando":   (C.ACCENT,        C.ACCENT_SOFT, "🤖 Analisando IA"),
        "pronto":       (C.SUCCESS,       C.SUCCESS_SOFT,"✓ Concluído"),
        "erro":         (C.ERROR,         C.ERROR_SOFT,  "✗ Erro"),
        "renderizando": (C.CYAN,          C.CYAN_SOFT,   "⚙ Renderizando"),
        "pendente":     (C.TEXT_MUTED,    C.SURFACE_2,   "· Pendente"),
    }
    cor, bg, txt = mapa.get(status, (C.TEXT_MUTED, C.SURFACE_2, status))
    return ft.Container(
        content=ft.Text(txt, size=11, weight=ft.FontWeight.W_600, color=cor),
        padding=ft.padding.symmetric(horizontal=10, vertical=4),
        border_radius=20,
        bgcolor=bg,
        border=ft.border.all(1, cor + "44"),
    )


# ══════════════════════════════════════════════════════════════════
#  CARD DE CLIPE SUGERIDO
# ══════════════════════════════════════════════════════════════════

def clip_card(clipe: ClipSugerido, on_renderizar, on_preview) -> ft.Container:
    """Card cinematográfico para exibir um clipe sugerido pela IA."""

    barra_prog = ft.ProgressBar(
        value=clipe.progresso,
        color=C.ACCENT,
        bgcolor=C.BORDER,
        height=3,
        border_radius=3,
        visible=clipe.status == "renderizando",
    )

    btn_renderizar = ft.ElevatedButton(
        text=ft.Text("Renderizar"),
        icon=ft.Icons.MOVIE_CREATION_OUTLINED,
        on_click=lambda e: on_renderizar(clipe),
        style=ft.ButtonStyle(
            color=C.BG,
            bgcolor={
                ft.ControlState.DEFAULT:  C.ACCENT,
                ft.ControlState.HOVERED:  "#FF8C42",
                ft.ControlState.DISABLED: C.TEXT_MUTED,
            },
            shape=ft.RoundedRectangleBorder(radius=6),
            padding=ft.padding.symmetric(horizontal=16, vertical=10),
            text_style=ft.TextStyle(weight=ft.FontWeight.W_700, size=13),
            elevation=0,
        ),
        disabled=clipe.status in ("renderizando", "pronto"),
    )

    btn_preview = ft.IconButton(
        icon=ft.Icons.PLAY_CIRCLE_OUTLINE,
        icon_color=C.CYAN,
        icon_size=22,
        tooltip="Pré-visualizar segmento",
        on_click=lambda e: on_preview(clipe),
        style=ft.ButtonStyle(
            bgcolor={ft.ControlState.HOVERED: C.CYAN_SOFT},
            shape=ft.RoundedRectangleBorder(radius=6),
        ),
    )

    return ft.Container(
        content=ft.Column(
            [
                # ── Linha superior: score + info ──────────────────
                ft.Row(
                    [
                        score_badge(clipe.score),
                        ft.Column(
                            [
                                ft.Text(clipe.titulo, size=14,
                                        weight=ft.FontWeight.W_700,
                                        color=C.TEXT_PRIMARY,
                                        max_lines=2, overflow=ft.TextOverflow.ELLIPSIS),
                                ft.Row(
                                    [
                                        tag(f"⏱ {clipe.inicio} → {clipe.fim}", C.CYAN, C.CYAN_SOFT),
                                        tag(f"📐 {clipe.duracao}", C.TEXT_SECONDARY, C.SURFACE_2),
                                    ],
                                    spacing=6,
                                ),
                            ],
                            spacing=6,
                            expand=True,
                        ),
                        status_chip(clipe.status),
                    ],
                    spacing=12,
                    vertical_alignment=ft.CrossAxisAlignment.START,
                ),

                # ── Motivo da IA ──────────────────────────────────
                ft.Container(
                    content=ft.Row(
                        [
                            ft.Icon(ft.Icons.AUTO_AWESOME, size=13, color=C.ACCENT),
                            ft.Text(clipe.motivo, size=12, color=C.TEXT_SECONDARY,
                                    italic=True, expand=True),
                        ],
                        spacing=6,
                        vertical_alignment=ft.CrossAxisAlignment.START,
                    ),
                    padding=ft.padding.symmetric(horizontal=10, vertical=8),
                    border_radius=6,
                    bgcolor=C.ACCENT_SOFT,
                    border=ft.border.all(1, C.ACCENT + "22"),
                ),

                # ── Barra de progresso ────────────────────────────
                barra_prog,

                # ── Ações ─────────────────────────────────────────
                ft.Row(
                    [btn_preview, ft.Container(expand=True), btn_renderizar],
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
            ],
            spacing=10,
        ),
        padding=ft.padding.all(16),
        border_radius=10,
        bgcolor=C.SURFACE,
        border=ft.border.all(1, C.BORDER),
        animate=ft.animation.Animation(200, ft.AnimationCurve.EASE_OUT),
    )


# ══════════════════════════════════════════════════════════════════
#  ABA 1 — NOVO PROJETO
# ══════════════════════════════════════════════════════════════════

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
        value=0, color=C.ACCENT, bgcolor=C.BORDER, height=3,
        border_radius=3, visible=False,
    )
    clips_column  = ft.Column(spacing=10, visible=False)
    etapas_column = ft.Column(spacing=4)

    def atualizar_etapas(etapa_atual: int):
        """Atualiza o indicador visual de etapas do pipeline."""
        etapas = [
            (ft.Icons.DOWNLOAD_OUTLINED,       "Download do vídeo"),
            (ft.Icons.GRAPHIC_EQ,              "Transcrição Whisper"),
            (ft.Icons.PSYCHOLOGY_OUTLINED,     "Análise de IA"),
            (ft.Icons.MOVIE_CREATION_OUTLINED, "Geração de clipes"),
        ]
        controles = []
        for i, (icone, label) in enumerate(etapas):
            if i < etapa_atual:
                cor, ic = C.SUCCESS,       ft.Icons.CHECK_CIRCLE
            elif i == etapa_atual:
                cor, ic = C.ACCENT,        icone
            else:
                cor, ic = C.TEXT_MUTED,    icone

            controles.append(
                ft.Row(
                    [
                        ft.Icon(ic, size=16, color=cor),
                        ft.Text(label, size=12, color=cor,
                                weight=(ft.FontWeight.W_600 if i == etapa_atual
                                        else ft.FontWeight.NORMAL)),
                    ],
                    spacing=8,
                )
            )
            if i < len(etapas) - 1:
                controles.append(
                    ft.Container(
                        width=1, height=12, bgcolor=C.BORDER,
                        margin=ft.margin.only(left=7),
                    )
                )
        etapas_column.controls = controles
        page.update()

    def simular_pipeline(url: str):
        """
        Simula o pipeline completo.
        Substitua cada bloco pela chamada real ao seu back-end.
        """
        # ── ETAPA 0: Download ─────────────────────────────────
        atualizar_etapas(0)
        status_text.value = "Baixando vídeo..."
        progress_row.visible = True
        for p in range(0, 101, 5):
            progress_row.value = p / 100
            page.update()
            time.sleep(0.06)
        # download_video(url)  ← seu back-end aqui

        # ── ETAPA 1: Transcrição ──────────────────────────────
        atualizar_etapas(1)
        status_text.value = "Transcrevendo com Whisper..."
        progress_row.value = 0
        for p in range(0, 101, 3):
            progress_row.value = p / 100
            page.update()
            time.sleep(0.08)
        # transcrever()  ← seu back-end aqui

        # ── ETAPA 2: Análise de IA ────────────────────────────
        atualizar_etapas(2)
        status_text.value = "Analisando momentos virais com IA..."
        progress_row.value = 0
        for p in range(0, 101, 4):
            progress_row.value = p / 100
            page.update()
            time.sleep(0.07)
        # clipes_brutos = analisar_momentos()  ← seu back-end aqui

        # ── ETAPA 3: Geração dos cards ────────────────────────
        atualizar_etapas(3)
        status_text.value = "Gerando sugestões de clipes..."
        progress_row.value = 0.9
        page.update()
        time.sleep(0.4)

        # Dados simulados — substitua pelos retornos do brain_IA
        clipes_mock = [
            ClipSugerido(1, "Momento de climax narrativo incrível", "02:14", "03:41", "1m27s",
                         0.92, "Pico emocional detectado + variação de tom + palavras-gatilho de engajamento"),
            ClipSugerido(2, "Revelação surpreendente no diálogo",   "07:05", "08:10", "1m05s",
                         0.78, "Alta densidade de palavras de alto impacto + pausa dramática detectada"),
            ClipSugerido(3, "Introdução energética e direta",       "00:00", "00:48", "48s",
                         0.65, "Abertura com hook forte — potencial para retenção nos primeiros 3 segundos"),
            ClipSugerido(4, "Trecho com insight técnico valioso",   "12:33", "13:55", "1m22s",
                         0.51, "Conteúdo informativo denso — desempenho histórico moderado em reels"),
        ]

        clips_column.controls.clear()
        clips_column.controls.append(
            ft.Row(
                [
                    ft.Icon(ft.Icons.AUTO_AWESOME, color=C.ACCENT, size=16),
                    ft.Text(f"{len(clipes_mock)} clipes sugeridos pela IA",
                            size=14, weight=ft.FontWeight.W_700, color=C.TEXT_PRIMARY),
                    ft.Container(expand=True),
                    tag(f"Score médio: {int(sum(c.score for c in clipes_mock) / len(clipes_mock) * 100)}%",
                        C.CYAN, C.CYAN_SOFT),
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

    def on_iniciar_download(e):
        url = url_field.value.strip()
        if not url:
            url_field.border_color = C.ERROR
            status_text.value = "⚠ Insira uma URL válida do YouTube."
            status_text.color = C.ERROR
            page.update()
            return

        url_field.border_color    = C.BORDER_ACCENT
        status_text.color         = C.TEXT_SECONDARY
        clips_column.visible      = False
        etapas_column.controls    = []
        btn_download.disabled     = True
        btn_download.text         = "Processando..."
        page.update()

        threading.Thread(target=simular_pipeline, args=(url,), daemon=True).start()

    def on_renderizar_clipe(clipe: ClipSugerido):
        clipe.status = "renderizando"
        clipe.progresso = 0.0
        _atualizar_cards()

        def _render():
            for p in range(0, 101, 2):
                clipe.progresso = p / 100
                time.sleep(0.04)
            # renderizar_clipe(clipe)  ← seu back-end aqui
            clipe.status    = "pronto"
            clipe.progresso = 1.0
            _atualizar_cards()

        threading.Thread(target=_render, daemon=True).start()

    def on_preview_clipe(clipe: ClipSugerido):
        dlg = ft.AlertDialog(
            title=ft.Text(clipe.titulo, color=C.TEXT_PRIMARY,
                          weight=ft.FontWeight.W_700),
            content=ft.Column(
                [
                    ft.Row([
                        tag(f"⏱ {clipe.inicio} → {clipe.fim}", C.CYAN, C.CYAN_SOFT),
                        tag(f"Score: {int(clipe.score*100)}%",
                            C.SUCCESS if clipe.score >= 0.75 else C.WARNING,
                            C.SUCCESS_SOFT if clipe.score >= 0.75 else C.WARNING_SOFT),
                    ], spacing=8),
                    ft.Container(height=8),
                    ft.Text("Motivo da seleção:", size=12, color=C.TEXT_SECONDARY,
                            weight=ft.FontWeight.W_600),
                    ft.Text(clipe.motivo, size=13, color=C.TEXT_PRIMARY),
                    ft.Container(height=8),
                    ft.Container(
                        content=ft.Row(
                            [ft.Icon(ft.Icons.INFO_OUTLINE, color=C.CYAN, size=14),
                             ft.Text("Pré-visualização disponível após download.",
                                     size=12, color=C.TEXT_SECONDARY)],
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
                ft.TextButton("Fechar", on_click=lambda e: page.close(dlg),
                              style=ft.ButtonStyle(color=C.TEXT_SECONDARY)),
                ft.ElevatedButton(
                    "Renderizar este clipe",
                    on_click=lambda e: (page.close(dlg), on_renderizar_clipe(clipe)),
                    style=ft.ButtonStyle(
                        bgcolor=C.ACCENT, color=C.BG,
                        shape=ft.RoundedRectangleBorder(radius=6),
                    ),
                ),
            ],
        )
        page.open(dlg)

    def _atualizar_cards():
        """Reconstrói todos os cards com o estado atual."""
        if len(clips_column.controls) > 1:
            for i, ctrl in enumerate(clips_column.controls[1:], 1):
                clipe_id = i  # corresponde ao índice dos clipes mock
                if clipe_id in estado["clipes"]:
                    clipe = estado["clipes"][clipe_id]
                    clips_column.controls[i] = clip_card(
                        clipe, on_renderizar_clipe, on_preview_clipe
                    )
        page.update()

    btn_download = ft.ElevatedButton(
        content=ft.Text("Analisar e Baixar"),
        icon=ft.Icons.ROCKET_LAUNCH_OUTLINED,
        on_click=on_iniciar_download,
        style=ft.ButtonStyle(
            color=C.BG,
            bgcolor={
                ft.ControlState.DEFAULT: C.ACCENT,
                ft.ControlState.HOVERED: "#FF8C42",
                ft.ControlState.DISABLED: C.BORDER,
            },
            shape=ft.RoundedRectangleBorder(radius=8),
            padding=ft.padding.symmetric(horizontal=24, vertical=14),
            text_style=ft.TextStyle(weight=ft.FontWeight.W_700, size=14),
            elevation=0,
        ),
    )

    return ft.Column(
        [
            # ── Header ────────────────────────────────────────────
            ft.Container(
                content=ft.Column(
                    [
                        ft.Row(
                            [
                                ft.Icon(ft.Icons.ADD_CIRCLE_OUTLINE,
                                        color=C.ACCENT, size=20),
                                ft.Text("Novo Projeto", size=20,
                                        weight=ft.FontWeight.W_800,
                                        color=C.TEXT_PRIMARY),
                            ],
                            spacing=10,
                        ),
                        ft.Text("Cole a URL do YouTube para extrair os melhores momentos.",
                                size=13, color=C.TEXT_SECONDARY),
                    ],
                    spacing=4,
                ),
                padding=ft.padding.only(bottom=16),
            ),

            # ── Input de URL ──────────────────────────────────────
            ft.Container(
                content=ft.Column(
                    [
                        ft.Text("URL do Vídeo", size=12, weight=ft.FontWeight.W_600,
                                color=C.TEXT_SECONDARY),
                        ft.Row([url_field], spacing=0),
                        ft.Container(height=4),
                        ft.Row([btn_download], alignment=ft.MainAxisAlignment.END),
                    ],
                    spacing=8,
                ),
                padding=ft.padding.all(16),
                border_radius=10,
                bgcolor=C.SURFACE,
                border=ft.border.all(1, C.BORDER),
            ),

            ft.Container(height=4),

            # ── Painel de progresso do pipeline ───────────────────
            ft.Container(
                content=ft.Column(
                    [
                        ft.Row(
                            [
                                ft.Text("Pipeline de processamento", size=12,
                                        weight=ft.FontWeight.W_600,
                                        color=C.TEXT_SECONDARY),
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

            # ── Lista de clipes sugeridos ─────────────────────────
            clips_column,
        ],
        spacing=8,
        scroll=ft.ScrollMode.AUTO,
        expand=True,
    )


# ══════════════════════════════════════════════════════════════════
#  ABA 2 — PROCESSAMENTO
# ══════════════════════════════════════════════════════════════════

def build_aba_processamento(estado: dict, page: ft.Page) -> ft.Control:

    # Projetos simulados em processamento
    projetos_mock = [
        Projeto(1, "youtube.com/watch?v=abc123", "Entrevista sobre IA Generativa",
                "1h 23min", "analisando", 0.62),
        Projeto(2, "youtube.com/watch?v=def456", "Podcast Tech — Ep. 47",
                "2h 05min", "transcrevendo", 0.31),
        Projeto(3, "youtube.com/watch?v=ghi789", "Palestra sobre Startups",
                "45min", "pronto", 1.0),
    ]

    def projeto_row(proj: Projeto) -> ft.Container:
        return ft.Container(
            content=ft.Column(
                [
                    ft.Row(
                        [
                            ft.Container(
                                content=ft.Icon(ft.Icons.MOVIE_OUTLINED,
                                                color=C.ACCENT, size=18),
                                width=36, height=36,
                                border_radius=8,
                                bgcolor=C.ACCENT_SOFT,
                            ),
                            ft.Column(
                                [
                                    ft.Text(proj.titulo, size=13,
                                            weight=ft.FontWeight.W_600,
                                            color=C.TEXT_PRIMARY,
                                            max_lines=1,
                                            overflow=ft.TextOverflow.ELLIPSIS),
                                    ft.Row(
                                        [
                                            ft.Text(proj.url, size=11,
                                                    color=C.TEXT_MUTED,
                                                    font_family="monospace",
                                                    max_lines=1,
                                                    overflow=ft.TextOverflow.ELLIPSIS),
                                            tag(proj.duracao, C.TEXT_SECONDARY, C.SURFACE_2),
                                        ],
                                        spacing=8,
                                    ),
                                ],
                                spacing=3,
                                expand=True,
                            ),
                            status_chip(proj.status),
                        ],
                        spacing=12,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    ft.ProgressBar(
                        value=proj.progresso_geral,
                        color=(C.SUCCESS if proj.status == "pronto"
                               else C.ACCENT),
                        bgcolor=C.BORDER,
                        height=3,
                        border_radius=3,
                    ),
                    ft.Row(
                        [
                            ft.Text(f"{int(proj.progresso_geral * 100)}% concluído",
                                    size=11, color=C.TEXT_MUTED),
                            ft.Container(expand=True),
                            ft.Text(f"ID #{proj.id:04d}", size=11,
                                    color=C.TEXT_MUTED, font_family="monospace"),
                        ],
                    ),
                ],
                spacing=8,
            ),
            padding=ft.padding.all(14),
            border_radius=10,
            bgcolor=C.SURFACE,
            border=ft.border.all(1, C.BORDER),
        )

    # Métricas de sistema
    metricas = [
        ("Projetos ativos",   str(len([p for p in projetos_mock if p.status != "pronto"])),
         ft.Icons.PENDING_OUTLINED, C.ACCENT),
        ("Concluídos hoje",   "3", ft.Icons.CHECK_CIRCLE_OUTLINE, C.SUCCESS),
        ("Clipes gerados",    "12", ft.Icons.MOVIE_FILTER_OUTLINED, C.CYAN),
        ("Fila de espera",    "2", ft.Icons.QUEUE_OUTLINED, C.WARNING),
    ]

    def metrica_card(label, valor, icone, cor):
        return ft.Container(
            content=ft.Column(
                [
                    ft.Icon(icone, color=cor, size=22),
                    ft.Text(valor, size=24, weight=ft.FontWeight.W_900,
                            color=cor, font_family="monospace"),
                    ft.Text(label, size=11, color=C.TEXT_SECONDARY,
                            text_align=ft.TextAlign.CENTER),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=4,
            ),
            padding=ft.padding.all(14),
            border_radius=10,
            bgcolor=C.SURFACE,
            border=ft.border.all(1, C.BORDER),
            expand=True,
        )

    return ft.Column(
        [
            ft.Row(
                [
                    ft.Icon(ft.Icons.SETTINGS_OUTLINED, color=C.ACCENT, size=20),
                    ft.Text("Processamento", size=20,
                            weight=ft.FontWeight.W_800, color=C.TEXT_PRIMARY),
                ],
                spacing=10,
            ),
            ft.Text("Acompanhe o status de todos os projetos em tempo real.",
                    size=13, color=C.TEXT_SECONDARY),

            ft.Container(height=8),

            # Métricas
            ft.Row(
                [metrica_card(l, v, i, c) for l, v, i, c in metricas],
                spacing=8,
            ),

            ft.Container(height=8),
            divider(),

            ft.Row(
                [
                    ft.Text("Projetos em andamento", size=14,
                            weight=ft.FontWeight.W_700, color=C.TEXT_PRIMARY),
                    ft.Container(expand=True),
                    ft.IconButton(
                        icon=ft.Icons.REFRESH,
                        icon_color=C.TEXT_SECONDARY,
                        icon_size=18,
                        tooltip="Atualizar",
                    ),
                ],
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),

            ft.Column(
                [projeto_row(p) for p in projetos_mock],
                spacing=8,
            ),
        ],
        spacing=8,
        scroll=ft.ScrollMode.AUTO,
        expand=True,
    )


# ══════════════════════════════════════════════════════════════════
#  ABA 3 — GALERIA
# ══════════════════════════════════════════════════════════════════

def build_aba_galeria(estado: dict, page: ft.Page) -> ft.Control:

    clipes_prontos = [
        {"titulo": "IA que muda tudo — Clip #1",  "duracao": "1m27s", "score": 0.92,
         "data": "Hoje, 14:32", "arquivo": "clip_001_final.mp4"},
        {"titulo": "Hook de abertura perfeito",   "duracao": "48s",   "score": 0.78,
         "data": "Hoje, 13:10", "arquivo": "clip_002_final.mp4"},
        {"titulo": "Momento viral detectado",     "duracao": "1m05s", "score": 0.85,
         "data": "Ontem, 20:44", "arquivo": "clip_003_final.mp4"},
        {"titulo": "Insight técnico — Shorts",   "duracao": "55s",   "score": 0.61,
         "data": "Ontem, 19:01", "arquivo": "clip_004_final.mp4"},
        {"titulo": "Engajamento emocional",      "duracao": "1m12s", "score": 0.88,
         "data": "12/03, 09:20", "arquivo": "clip_005_final.mp4"},
        {"titulo": "Revelação de dados chocante","duracao": "38s",   "score": 0.71,
         "data": "12/03, 08:55", "arquivo": "clip_006_final.mp4"},
    ]

    def galeria_card(item: dict) -> ft.Container:
        cor_score = (C.SUCCESS if item["score"] >= 0.75
                     else C.WARNING if item["score"] >= 0.5
                     else C.SCORE_LOW)
        return ft.Container(
            content=ft.Column(
                [
                    # Thumbnail simulada
                    ft.Container(
                        content=ft.Stack(
                            [
                                ft.Container(
                                    gradient=ft.LinearGradient(
                                        colors=[C.SURFACE_2, "#1A1A28"],
                                        begin=ft.Alignment(-1, -1),
                                        end=ft.Alignment(1, 1),
                                    ),
                                    expand=True,
                                    border_radius=ft.border_radius.only(
                                        top_left=8, top_right=8),
                                ),
                                ft.Container(
                                    content=ft.Icon(ft.Icons.PLAY_CIRCLE_FILLED,
                                                    color=C.ACCENT + "CC",
                                                    size=36),
                                    alignment=ft.Alignment(0, 0),

                                    expand=True,
                                ),
                                ft.Container(
                                    content=ft.Text(
                                        f"{int(item['score'] * 100)}%",
                                        size=11, weight=ft.FontWeight.W_800,
                                        color=cor_score, font_family="monospace",
                                    ),
                                    padding=ft.padding.symmetric(horizontal=6, vertical=3),
                                    bgcolor=C.BG + "CC",
                                    border_radius=4,
                                    bottom=6, right=6,
                                ),
                                ft.Container(
                                    content=ft.Text(
                                        item["duracao"], size=10,
                                        color=C.TEXT_PRIMARY,
                                        font_family="monospace",
                                    ),
                                    padding=ft.padding.symmetric(horizontal=6, vertical=3),
                                    bgcolor=C.BG + "CC",
                                    border_radius=4,
                                    bottom=6, left=6,
                                ),
                            ]
                        ),
                        height=100,
                        border_radius=ft.border_radius.only(top_left=8, top_right=8),
                        clip_behavior=ft.ClipBehavior.HARD_EDGE,
                    ),
                    # Info
                    ft.Container(
                        content=ft.Column(
                            [
                                ft.Text(item["titulo"], size=12,
                                        weight=ft.FontWeight.W_600,
                                        color=C.TEXT_PRIMARY,
                                        max_lines=2,
                                        overflow=ft.TextOverflow.ELLIPSIS),
                                ft.Text(item["data"], size=10,
                                        color=C.TEXT_MUTED),
                                ft.Row(
                                    [
                                        ft.IconButton(
                                            icon=ft.Icons.PLAY_ARROW_OUTLINED,
                                            icon_color=C.CYAN, icon_size=16,
                                            tooltip="Reproduzir",
                                            style=ft.ButtonStyle(padding=0),
                                        ),
                                        ft.IconButton(
                                            icon=ft.Icons.DOWNLOAD_OUTLINED,
                                            icon_color=C.ACCENT, icon_size=16,
                                            tooltip="Baixar",
                                            style=ft.ButtonStyle(padding=0),
                                        ),
                                        ft.IconButton(
                                            icon=ft.Icons.DELETE_OUTLINE,
                                            icon_color=C.ERROR, icon_size=16,
                                            tooltip="Remover",
                                            style=ft.ButtonStyle(padding=0),
                                        ),
                                    ],
                                    spacing=0,
                                    alignment=ft.MainAxisAlignment.END,
                                ),
                            ],
                            spacing=4,
                        ),
                        padding=ft.padding.symmetric(horizontal=10, vertical=8),
                    ),
                ],
                spacing=0,
            ),
            border_radius=8,
            bgcolor=C.SURFACE,
            border=ft.border.all(1, C.BORDER),
            clip_behavior=ft.ClipBehavior.HARD_EDGE,
        )

    grid = ft.GridView(
        runs_count=2,
        max_extent=220,
        child_aspect_ratio=0.72,
        spacing=10,
        run_spacing=10,
        expand=True,
        controls=[galeria_card(c) for c in clipes_prontos],
    )

    return ft.Column(
        [
            ft.Row(
                [
                    ft.Icon(ft.Icons.VIDEO_LIBRARY_OUTLINED,
                            color=C.ACCENT, size=20),
                    ft.Text("Galeria", size=20,
                            weight=ft.FontWeight.W_800, color=C.TEXT_PRIMARY),
                    ft.Container(expand=True),
                    ft.Container(
                        content=ft.Text(f"{len(clipes_prontos)} clipes",
                                        size=12, color=C.ACCENT,
                                        weight=ft.FontWeight.W_700),
                        padding=ft.padding.symmetric(horizontal=10, vertical=4),
                        border_radius=20,
                        bgcolor=C.ACCENT_SOFT,
                        border=ft.border.all(1, C.ACCENT + "44"),
                    ),
                ],
                spacing=10,
                alignment=ft.Alignment(0, 0),

            ),
            ft.Text("Clipes prontos para publicação.",
                    size=13, color=C.TEXT_SECONDARY),

            ft.Container(height=4),

            ft.Row(
                [
                    ft.TextField(
                        hint_text="Buscar clipes...",
                        hint_style=ft.TextStyle(color=C.TEXT_MUTED),
                        prefix_icon=ft.Icons.SEARCH,
                        border_color=C.BORDER_ACCENT,
                        focused_border_color=C.ACCENT,
                        cursor_color=C.ACCENT,
                        color=C.TEXT_PRIMARY,
                        bgcolor=C.SURFACE,
                        border_radius=8,
                        height=42,
                        text_size=13,
                        expand=True,
                        content_padding=ft.padding.symmetric(vertical=8, horizontal=12),
                    ),
                    ft.IconButton(
                        icon=ft.Icons.TUNE,
                        icon_color=C.TEXT_SECONDARY,
                        icon_size=20,
                        tooltip="Filtros",
                        style=ft.ButtonStyle(
                            bgcolor={ft.ControlState.HOVERED: C.SURFACE_2},
                            shape=ft.RoundedRectangleBorder(radius=8),
                        ),
                    ),
                ],
                spacing=8,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),

            ft.Container(height=4),
            grid,
        ],
        spacing=8,
        expand=True,
    )


# ══════════════════════════════════════════════════════════════════
#  APP PRINCIPAL
# ══════════════════════════════════════════════════════════════════

def main(page: ft.Page):

    # ── Configuração da página ─────────────────────────────────
    page.title         = "Clip Engine"
    page.theme_mode    = ft.ThemeMode.DARK
    page.bgcolor       = C.BG
    page.padding       = 0
    page.window.width  = 420
    page.window.height = 860
    page.window.min_width  = 360
    page.window.min_height = 640
    page.fonts         = {}   # fontes customizadas podem ser adicionadas aqui

    page.theme = ft.Theme(
        color_scheme=ft.ColorScheme(
            primary=C.ACCENT,
            secondary=C.CYAN,
            # background=C.BG,
            surface=C.SURFACE,
            on_primary=C.BG,
            # on_background=C.TEXT_PRIMARY,
            on_surface=C.TEXT_PRIMARY,
        ),
        visual_density=ft.VisualDensity.COMPACT,
    )

    # ── Estado global ─────────────────────────────────────────
    estado = {
        "clipes":  {},    # id → ClipSugerido
        "projetos": {},   # id → Projeto
        "aba_atual": 0,
    }

    # ── Conteúdo das abas ─────────────────────────────────────
    abas_conteudo = [
        build_aba_novo_projeto(estado, page),
        build_aba_processamento(estado, page),
        build_aba_galeria(estado, page),
    ]

    indice_aba = ft.Ref[int]()
    conteudo_principal = ft.Container(
        content=abas_conteudo[0],
        expand=True,
        padding=ft.padding.symmetric(horizontal=16, vertical=16),
        bgcolor=C.BG,
    )

    # ── Header fixo ───────────────────────────────────────────
    header = ft.Container(
        content=ft.Row(
            [
                ft.Row(
                    [
                        ft.Container(
                            content=ft.Icon(ft.Icons.MOVIE_FILTER,
                                            color=C.BG, size=16),
                            width=30, height=30,
                            border_radius=8,
                            bgcolor=C.ACCENT,
                            alignment=ft.Alignment(0, 0),

                        ),
                        ft.Text("CLIP ENGINE", size=16,
                                weight=ft.FontWeight.W_900,
                                color=C.TEXT_PRIMARY,
                                font_family="monospace",
                                style=ft.TextStyle(letter_spacing=2)),
                    ],
                    spacing=10,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                ft.Container(expand=True),
                ft.IconButton(
                    icon=ft.Icons.NOTIFICATIONS_NONE_OUTLINED,
                    icon_color=C.TEXT_SECONDARY,
                    icon_size=20,
                    tooltip="Notificações",
                    style=ft.ButtonStyle(
                        bgcolor={ft.ControlState.HOVERED: C.SURFACE},
                        shape=ft.RoundedRectangleBorder(radius=8),
                    ),
                ),
                ft.IconButton(
                    icon=ft.Icons.SETTINGS_OUTLINED,
                    icon_color=C.TEXT_SECONDARY,
                    icon_size=20,
                    tooltip="Configurações",
                    style=ft.ButtonStyle(
                        bgcolor={ft.ControlState.HOVERED: C.SURFACE},
                        shape=ft.RoundedRectangleBorder(radius=8),
                    ),
                ),
            ],
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        padding=ft.padding.symmetric(horizontal=16, vertical=12),
        bgcolor=C.SURFACE,
        border=ft.border.only(bottom=ft.BorderSide(1, C.BORDER)),
    )

    # ── Nav bar inferior ──────────────────────────────────────
    def on_nav_change(e):
        idx = e.control.selected_index
        estado["aba_atual"] = idx
        conteudo_principal.content = abas_conteudo[idx]
        page.update()

    nav_bar = ft.NavigationBar(
        selected_index=0,
        on_change=on_nav_change,
        bgcolor=C.SURFACE,
        indicator_color=C.ACCENT_SOFT,
        indicator_shape=ft.RoundedRectangleBorder(radius=8),
        shadow_color=ft.Colors.TRANSPARENT,
        destinations=[
            ft.NavigationBarDestination(
                icon=ft.Icons.ADD_CIRCLE_OUTLINE,
                selected_icon=ft.Icons.ADD_CIRCLE,
                label="Novo Projeto",
            ),
            ft.NavigationBarDestination(
                icon=ft.Icons.TUNE_OUTLINED,
                selected_icon=ft.Icons.TUNE,
                label="Processamento",
            ),
            ft.NavigationBarDestination(
                icon=ft.Icons.VIDEO_LIBRARY_OUTLINED,
                selected_icon=ft.Icons.VIDEO_LIBRARY,
                label="Galeria",
            ),
        ],
        label_behavior=ft.NavigationBarLabelBehavior.ALWAYS_SHOW,
    )

    # ── Layout principal ──────────────────────────────────────
    page.add(
        ft.Column(
            [
                header,
                conteudo_principal,
                ft.Container(
                    content=nav_bar,
                    border=ft.border.only(top=ft.BorderSide(1, C.BORDER)),
                ),
            ],
            spacing=0,
            expand=True,
        )
    )


# ══════════════════════════════════════════════════════════════════
#  ENTRYPOINT
# ══════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    ft.app(target=main)
    # Para rodar como web app:
    # ft.app(target=main, view=ft.AppView.WEB_BROWSER, port=8080)
