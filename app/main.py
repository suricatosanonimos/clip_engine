"""
CLIP ENGINE — main.py
"""

import sys
from pathlib import Path

import flet as ft

ROOT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT_DIR))

from src.views.auth       import build_tela_auth
from src.views.theme      import C
from src.views.home       import build_aba_novo_projeto
from src.views.processing import build_aba_processamento
from src.views.gallery    import build_aba_galeria


DEV_MODE = True  # ← mude para False quando quiser reativar o login


def main(page: ft.Page):

    try:
        page.padding = ft.padding.only(
            top=ft.SafeCast(page).top if hasattr(page, "safe_area") else 40
        )
    except:
        page.padding = ft.padding.only(top=40)

    page.title      = "Clip Engine"
    page.theme_mode = ft.ThemeMode.DARK
    page.bgcolor    = C.BG
    page.padding    = ft.Padding(left=0, right=0, top=0, bottom=0)
    page.window.width      = 420
    page.window.height     = 860
    page.window.min_width  = 360
    page.window.min_height = 640

    page.theme = ft.Theme(
        color_scheme=ft.ColorScheme(
            primary=C.ACCENT, secondary=C.CYAN,
            surface=C.SURFACE,
            on_primary=C.BG, on_surface=C.TEXT_PRIMARY,
        ),
        visual_density=ft.VisualDensity.COMPACT,
    )

    estado = {
        "clipes":    {},
        "projetos":  {},
        "aba_atual": 0,
        "user_info": None,
        "token":     None,
    }

    corpo      = ft.Container(expand=True, bgcolor=C.BG)
    usuario_txt = ft.Text("", size=11, color=C.TEXT_MUTED, font_family="monospace")

    def on_logout(e):
        estado["user_info"] = None
        estado["token"]     = None
        _mostrar_login()

    btn_logout = ft.IconButton(
        icon=ft.Icons.LOGOUT,
        icon_color=C.TEXT_SECONDARY,
        icon_size=18,
        tooltip="Sair da conta",
        on_click=on_logout,
        visible=False,
        style=ft.ButtonStyle(
            bgcolor={ft.ControlState.HOVERED: C.SURFACE_2},
            shape=ft.RoundedRectangleBorder(radius=8),
        ),
    )

    header = ft.Container(
        padding=ft.Padding(left=16, right=8, top=12, bottom=12),
        bgcolor=C.SURFACE,
        border=ft.Border(bottom=ft.BorderSide(1, C.BORDER)),
        content=ft.Row(
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                ft.Row(
                    spacing=10,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        ft.Container(
                            width=30, height=30,
                            border_radius=8,
                            bgcolor=C.ACCENT,
                            alignment=ft.Alignment(0, 0),
                            content=ft.Icon(ft.Icons.MOVIE_FILTER, color=C.BG, size=16),
                        ),
                        ft.Text(
                            "CLIP ENGINE",
                            size=16, weight=ft.FontWeight.W_900,
                            color=C.TEXT_PRIMARY, font_family="monospace",
                        ),
                    ],
                ),
                ft.Container(expand=True),
                usuario_txt,
                btn_logout,
            ],
        ),
    )

    def _construir_app(user: dict, token: str = None):
        estado["user_info"] = user
        estado["token"]     = token

        abas_conteudo = [
            build_aba_novo_projeto(estado, page),
            build_aba_processamento(estado, page),
            build_aba_galeria(estado, page),
        ]

        conteudo_aba = ft.Container(
            content=abas_conteudo[0],
            expand=True,
            padding=ft.Padding(left=16, right=16, top=16, bottom=16),
            bgcolor=C.BG,
        )

        def on_nav_change(e):
            idx = e.control.selected_index
            estado["aba_atual"] = idx
            conteudo_aba.content = abas_conteudo[idx]
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
                    label="Novo",
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

        corpo.content = ft.Column(
            spacing=0, expand=True,
            controls=[
                conteudo_aba,
                ft.Container(
                    content=nav_bar,
                    border=ft.Border(top=ft.BorderSide(1, C.BORDER)),
                ),
            ],
        )

        nome  = user.get("nome", "")
        email = user.get("email", "")
        label = nome if nome else email
        usuario_txt.value  = label[:22] + ("…" if len(label) > 22 else "")
        btn_logout.visible = True
        page.update()

    def _mostrar_login():
        btn_logout.visible = False
        usuario_txt.value  = ""
        corpo.content = build_tela_auth(
            page=page,
            on_autenticado=_on_autenticado,
        )
        page.update()

    def _on_autenticado(user: dict, token: str = None):
        _construir_app(user, token)

    # ── Inicialização ──────────────────────────────────────────────
    page.add(
        ft.Column(
            spacing=0, expand=True,
            controls=[header, corpo],
        )
    )

    if DEV_MODE:
        _construir_app(
            user={
                "id":         "dev-local",
                "email":      "dev@local.com",
                "nome":       "Gilderlan",
                "avatar_url": None,
                "created_at": "",
            },
            token="fake-token-dev",
        )
    else:
        _mostrar_login()


if __name__ == "__main__":
    ft.run(main=main)
