"""
Componentes reutilizáveis da UI — Clip Engine.
"""

import flet as ft
from src.views.theme import C


def divider():
    return ft.Container(
        height=1, bgcolor=C.BORDER, margin=ft.margin.symmetric(vertical=8)
    )


def tag(texto: str, cor: str = C.ACCENT, bg: str = C.ACCENT_SOFT):
    return ft.Container(
        content=ft.Text(
            texto,
            size=10,
            weight=ft.FontWeight.W_600,
            color=cor,
            font_family="monospace",
        ),
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
                ft.Text(
                    f"{pct}",
                    size=26,
                    weight=ft.FontWeight.W_900,
                    color=cor,
                    font_family="monospace",
                ),
                ft.Text(
                    label,
                    size=9,
                    weight=ft.FontWeight.W_700,
                    color=cor,
                    font_family="monospace",
                ),
            ],
            spacing=0,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        width=64,
        height=64,
        border_radius=8,
        bgcolor=bg,
        border=ft.border.all(1, cor + "66"),
        alignment=ft.Alignment.TOP_CENTER,
    )


def status_chip(status: str):
    mapa = {
        "aguardando": (C.TEXT_MUTED, C.SURFACE_2, "⏸ Aguardando"),
        "baixando": (C.CYAN, C.CYAN_SOFT, "⬇ Baixando"),
        "transcrevendo": (C.WARNING, C.WARNING_SOFT, "🎙 Transcrevendo"),
        "analisando": (C.ACCENT, C.ACCENT_SOFT, "🤖 Analisando IA"),
        "pronto": (C.SUCCESS, C.SUCCESS_SOFT, "✓ Concluído"),
        "erro": (C.ERROR, C.ERROR_SOFT, "✗ Erro"),
        "renderizando": (C.CYAN, C.CYAN_SOFT, "⚙ Renderizando"),
        "pendente": (C.TEXT_MUTED, C.SURFACE_2, "· Pendente"),
    }
    cor, bg, txt = mapa.get(status, (C.TEXT_MUTED, C.SURFACE_2, status))
    return ft.Container(
        content=ft.Text(txt, size=11, weight=ft.FontWeight.W_600, color=cor),
        padding=ft.padding.symmetric(horizontal=10, vertical=4),
        border_radius=20,
        bgcolor=bg,
        border=ft.border.all(1, cor + "44"),
    )


def clip_card(clipe, on_renderizar, on_preview) -> ft.Container:
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
        ft.Text("Renderizar"),
        icon=ft.Icons.MOVIE_CREATION_OUTLINED,
        on_click=lambda e: on_renderizar(clipe),
        style=ft.ButtonStyle(
            color=C.BG,
            bgcolor={
                ft.ControlState.DEFAULT: C.ACCENT,
                ft.ControlState.HOVERED: "#FF8C42",
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
                ft.Row(
                    [
                        score_badge(clipe.score),
                        ft.Column(
                            [
                                ft.Text(
                                    clipe.titulo,
                                    size=14,
                                    weight=ft.FontWeight.W_700,
                                    color=C.TEXT_PRIMARY,
                                    max_lines=2,
                                    overflow=ft.TextOverflow.ELLIPSIS,
                                ),
                                ft.Row(
                                    [
                                        tag(
                                            f"⏱ {clipe.inicio} → {clipe.fim}",
                                            C.CYAN,
                                            C.CYAN_SOFT,
                                        ),
                                        tag(
                                            f"📐 {clipe.duracao}",
                                            C.TEXT_SECONDARY,
                                            C.SURFACE_2,
                                        ),
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
                ft.Container(
                    content=ft.Row(
                        [
                            ft.Icon(ft.Icons.AUTO_AWESOME, size=13, color=C.ACCENT),
                            ft.Text(
                                clipe.motivo,
                                size=12,
                                color=C.TEXT_SECONDARY,
                                italic=True,
                                expand=True,
                            ),
                        ],
                        spacing=6,
                        vertical_alignment=ft.CrossAxisAlignment.START,
                    ),
                    padding=ft.padding.symmetric(horizontal=10, vertical=8),
                    border_radius=6,
                    bgcolor=C.ACCENT_SOFT,
                    border=ft.border.all(1, C.ACCENT + "22"),
                ),
                barra_prog,
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
        animate=ft.Animation(200, ft.AnimationCurve.EASE_OUT),
    )
