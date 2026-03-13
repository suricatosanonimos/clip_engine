"""
Aba 2 — Processamento.
Acompanhe o status de todos os projetos em tempo real.
"""

import flet as ft
from src.views.components import divider, status_chip, tag
from src.views.models import Projeto
from src.views.theme import C


def build_aba_processamento(estado: dict, page: ft.Page) -> ft.Control:

    projetos_mock = [
        Projeto(
            1,
            "youtube.com/watch?v=abc123",
            "Entrevista sobre IA Generativa",
            "1h 23min",
            "analisando",
            0.62,
        ),
        Projeto(
            2,
            "youtube.com/watch?v=def456",
            "Podcast Tech — Ep. 47",
            "2h 05min",
            "transcrevendo",
            0.31,
        ),
        Projeto(
            3,
            "youtube.com/watch?v=ghi789",
            "Palestra sobre Startups",
            "45min",
            "pronto",
            1.0,
        ),
    ]

    def projeto_row(proj: Projeto) -> ft.Container:
        return ft.Container(
            content=ft.Column(
                [
                    ft.Row(
                        [
                            ft.Container(
                                content=ft.Icon(
                                    ft.Icons.MOVIE_OUTLINED, color=C.ACCENT, size=18
                                ),
                                width=36,
                                height=36,
                                border_radius=8,
                                bgcolor=C.ACCENT_SOFT,
                            ),
                            ft.Column(
                                [
                                    ft.Text(
                                        proj.titulo,
                                        size=13,
                                        weight=ft.FontWeight.W_600,
                                        color=C.TEXT_PRIMARY,
                                        max_lines=1,
                                        overflow=ft.TextOverflow.ELLIPSIS,
                                    ),
                                    ft.Row(
                                        [
                                            ft.Text(
                                                proj.url,
                                                size=11,
                                                color=C.TEXT_MUTED,
                                                font_family="monospace",
                                                max_lines=1,
                                                overflow=ft.TextOverflow.ELLIPSIS,
                                            ),
                                            tag(
                                                proj.duracao,
                                                C.TEXT_SECONDARY,
                                                C.SURFACE_2,
                                            ),
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
                        color=(C.SUCCESS if proj.status == "pronto" else C.ACCENT),
                        bgcolor=C.BORDER,
                        height=3,
                        border_radius=3,
                    ),
                    ft.Row(
                        [
                            ft.Text(
                                f"{int(proj.progresso_geral * 100)}% concluído",
                                size=11,
                                color=C.TEXT_MUTED,
                            ),
                            ft.Container(expand=True),
                            ft.Text(
                                f"ID #{proj.id:04d}",
                                size=11,
                                color=C.TEXT_MUTED,
                                font_family="monospace",
                            ),
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

    metricas = [
        (
            "Projetos ativos",
            str(len([p for p in projetos_mock if p.status != "pronto"])),
            ft.Icons.PENDING_OUTLINED,
            C.ACCENT,
        ),
        ("Concluídos hoje", "3", ft.Icons.CHECK_CIRCLE_OUTLINE, C.SUCCESS),
        ("Clipes gerados", "12", ft.Icons.MOVIE_FILTER_OUTLINED, C.CYAN),
        ("Fila de espera", "2", ft.Icons.QUEUE_OUTLINED, C.WARNING),
    ]

    def metrica_card(label, valor, icone, cor):
        return ft.Container(
            content=ft.Column(
                [
                    ft.Icon(icone, color=cor, size=22),
                    ft.Text(
                        valor,
                        size=24,
                        weight=ft.FontWeight.W_900,
                        color=cor,
                        font_family="monospace",
                    ),
                    ft.Text(
                        label,
                        size=11,
                        color=C.TEXT_SECONDARY,
                        text_align=ft.TextAlign.CENTER,
                    ),
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
                    ft.Text(
                        "Processamento",
                        size=20,
                        weight=ft.FontWeight.W_800,
                        color=C.TEXT_PRIMARY,
                    ),
                ],
                spacing=10,
            ),
            ft.Text(
                "Acompanhe o status de todos os projetos em tempo real.",
                size=13,
                color=C.TEXT_SECONDARY,
            ),
            ft.Container(height=8),
            ft.Row(
                [metrica_card(l, v, i, c) for l, v, i, c in metricas],
                spacing=8,
            ),
            ft.Container(height=8),
            divider(),
            ft.Row(
                [
                    ft.Text(
                        "Projetos em andamento",
                        size=14,
                        weight=ft.FontWeight.W_700,
                        color=C.TEXT_PRIMARY,
                    ),
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
