"""
Aba 3 — Galeria.
Clipes prontos para publicação.
"""

import flet as ft
from src.views.theme import C


def build_aba_galeria(estado: dict, page: ft.Page) -> ft.Control:

    clipes_prontos = [
        {
            "titulo": "IA que muda tudo — Clip #1",
            "duracao": "1m27s",
            "score": 0.92,
            "data": "Hoje, 14:32",
            "arquivo": "clip_001_final.mp4",
        },
        {
            "titulo": "Hook de abertura perfeito",
            "duracao": "48s",
            "score": 0.78,
            "data": "Hoje, 13:10",
            "arquivo": "clip_002_final.mp4",
        },
        {
            "titulo": "Momento viral detectado",
            "duracao": "1m05s",
            "score": 0.85,
            "data": "Ontem, 20:44",
            "arquivo": "clip_003_final.mp4",
        },
        {
            "titulo": "Insight técnico — Shorts",
            "duracao": "55s",
            "score": 0.61,
            "data": "Ontem, 19:01",
            "arquivo": "clip_004_final.mp4",
        },
        {
            "titulo": "Engajamento emocional",
            "duracao": "1m12s",
            "score": 0.88,
            "data": "12/03, 09:20",
            "arquivo": "clip_005_final.mp4",
        },
        {
            "titulo": "Revelação de dados chocante",
            "duracao": "38s",
            "score": 0.71,
            "data": "12/03, 08:55",
            "arquivo": "clip_006_final.mp4",
        },
    ]

    def galeria_card(item: dict) -> ft.Container:
        cor_score = (
            C.SUCCESS
            if item["score"] >= 0.75
            else C.WARNING if item["score"] >= 0.5 else C.SCORE_LOW
        )
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
                                        top_left=8, top_right=8
                                    ),
                                ),
                                ft.Container(
                                    content=ft.Icon(
                                        ft.Icons.PLAY_CIRCLE_FILLED,
                                        color=C.ACCENT + "CC",
                                        size=36,
                                    ),
                                    alignment=ft.Alignment(0, 0),
                                    expand=True,
                                ),
                                ft.Container(
                                    content=ft.Text(
                                        f"{int(item['score'] * 100)}%",
                                        size=11,
                                        weight=ft.FontWeight.W_800,
                                        color=cor_score,
                                        font_family="monospace",
                                    ),
                                    padding=ft.padding.symmetric(
                                        horizontal=6, vertical=3
                                    ),
                                    bgcolor=C.BG + "CC",
                                    border_radius=4,
                                    bottom=6,
                                    right=6,
                                ),
                                ft.Container(
                                    content=ft.Text(
                                        item["duracao"],
                                        size=10,
                                        color=C.TEXT_PRIMARY,
                                        font_family="monospace",
                                    ),
                                    padding=ft.padding.symmetric(
                                        horizontal=6, vertical=3
                                    ),
                                    bgcolor=C.BG + "CC",
                                    border_radius=4,
                                    bottom=6,
                                    left=6,
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
                                ft.Text(
                                    item["titulo"],
                                    size=12,
                                    weight=ft.FontWeight.W_600,
                                    color=C.TEXT_PRIMARY,
                                    max_lines=2,
                                    overflow=ft.TextOverflow.ELLIPSIS,
                                ),
                                ft.Text(item["data"], size=10, color=C.TEXT_MUTED),
                                ft.Row(
                                    [
                                        ft.IconButton(
                                            icon=ft.Icons.PLAY_ARROW_OUTLINED,
                                            icon_color=C.CYAN,
                                            icon_size=16,
                                            tooltip="Reproduzir",
                                            style=ft.ButtonStyle(padding=0),
                                        ),
                                        ft.IconButton(
                                            icon=ft.Icons.DOWNLOAD_OUTLINED,
                                            icon_color=C.ACCENT,
                                            icon_size=16,
                                            tooltip="Baixar",
                                            style=ft.ButtonStyle(padding=0),
                                        ),
                                        ft.IconButton(
                                            icon=ft.Icons.DELETE_OUTLINE,
                                            icon_color=C.ERROR,
                                            icon_size=16,
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
                    ft.Icon(ft.Icons.VIDEO_LIBRARY_OUTLINED, color=C.ACCENT, size=20),
                    ft.Text(
                        "Galeria",
                        size=20,
                        weight=ft.FontWeight.W_800,
                        color=C.TEXT_PRIMARY,
                    ),
                    ft.Container(expand=True),
                    ft.Container(
                        content=ft.Text(
                            f"{len(clipes_prontos)} clipes",
                            size=12,
                            color=C.ACCENT,
                            weight=ft.FontWeight.W_700,
                        ),
                        padding=ft.padding.symmetric(horizontal=10, vertical=4),
                        border_radius=20,
                        bgcolor=C.ACCENT_SOFT,
                        border=ft.border.all(1, C.ACCENT + "44"),
                    ),
                ],
                spacing=10,
                alignment=ft.Alignment(0, 0),
            ),
            ft.Text("Clipes prontos para publicação.", size=13, color=C.TEXT_SECONDARY),
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
