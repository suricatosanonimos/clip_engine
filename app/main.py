"""
╔══════════════════════════════════════════════════════════════════╗
║  CLIP ENGINE — Interface Flet                                    ║
║  Tema: Dark Cinematic / Industrial                               ║
╠══════════════════════════════════════════════════════════════════╣
║  Estrutura:                                                      ║
║  • views/theme.py       → paleta de cores                       ║
║  • views/models.py      → dataclasses                           ║
║  • views/components.py  → widgets reutilizáveis                 ║
║  • views/home.py        → aba Novo Projeto                      ║
║  • views/processing.py  → aba Processamento                     ║
║  • views/gallery.py     → aba Galeria                           ║
╠══════════════════════════════════════════════════════════════════╣
║  pip install flet                                                ║
║  python main.py                                                  ║
╚══════════════════════════════════════════════════════════════════╝
"""
import flet as ft
from flet.controls import alignment
from src.views import (
    build_aba_galeria,
    build_aba_novo_projeto,
    build_aba_processamento,
)
from src.views.theme import C

def main(page: ft.Page):

    # ── Configuração da página ─────────────────────────────────
    page.title = "Clip Engine"
    page.theme_mode = ft.ThemeMode.DARK
    page.bgcolor = C.BG
    page.padding = 0
    page.window.width = 420
    page.window.height = 860
    page.window.min_width = 360
    page.window.min_height = 640
    page.fonts = {}

    try:
        page.padding = ft.padding.only(top=ft.SafeCast(page).top if hasattr(page, "safe_area") else 40)
    except:
        page.padding = ft.padding.only(top=40)



    page.theme = ft.Theme(
        color_scheme=ft.ColorScheme(
            primary=C.ACCENT,
            secondary=C.CYAN,
            surface=C.SURFACE,
            on_primary=C.BG,
            on_surface=C.TEXT_PRIMARY,
        ),
        visual_density=ft.VisualDensity.COMPACT,
    )

    # ── Estado global ─────────────────────────────────────────
    estado = {
        "clipes": {},
        "projetos": {},
        "aba_atual": 0,
    }

    # ── Conteúdo das abas ─────────────────────────────────────
    abas_conteudo = [
        build_aba_novo_projeto(estado, page),
        build_aba_processamento(estado, page),
        build_aba_galeria(estado, page),
    ]

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
            # --- ÁREA DO LOGO E TÍTULO ---
            ft.Row(
                [
                    ft.Container(
                        width=4,        # Fiz ele como uma barrinha vertical moderna
                        height=20,       # Altura próxima ao tamanho da fonte
                        bgcolor=C.ACCENT,
                        border_radius=2,
                    ),
                    ft.Text(
                        "CLIP ENGINE",
                        size=16,
                        weight=ft.FontWeight.W_900,
                        color=C.TEXT_PRIMARY,
                        font_family="monospace",
                        style=ft.TextStyle(letter_spacing=2),
                    ),
                ],
                spacing=10,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),

            # ESPAÇADOR (Empurra o resto para a direita)
            ft.Container(expand=True),

            # --- ÁREA DE BOTÕES ---
            ft.Row(
                [
                    ft.IconButton(
                        icon=ft.Icons.NOTIFICATIONS_NONE_OUTLINED,
                        icon_color=C.TEXT_SECONDARY,
                        icon_size=20,
                        tooltip="Notificações",
                        style=ft.ButtonStyle(
                            shape=ft.RoundedRectangleBorder(radius=8),
                        ),
                    ),
                    ft.IconButton(
                        icon=ft.Icons.SETTINGS_OUTLINED,
                        icon_color=C.TEXT_SECONDARY,
                        icon_size=20,
                        tooltip="Configurações",
                        style=ft.ButtonStyle(
                            shape=ft.RoundedRectangleBorder(radius=8),
                        ),
                    ),
                ],
                spacing=4, # Botões um pouco mais próximos
            ),
        ],
        alignment=ft.MainAxisAlignment.SPACE_BETWEEN, # Garante a distribuição
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
    ),
    padding=ft.padding.only(left=20, right=10, top=10, bottom=10),
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
