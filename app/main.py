"""
CLIP ENGINE — main.py (versão cloud)

Fluxo:
  1. Inicia → verifica sessão Supabase ativa
  2. Se não autenticado → mostra tela de login (views/auth.py)
  3. Se autenticado → mostra app principal com nav bar
  4. Header com e-mail do usuário + botão de logout

Variáveis de ambiente necessárias:
  SUPABASE_URL       → Supabase dashboard > Settings > API > Project URL
  SUPABASE_ANON_KEY  → Supabase dashboard > Settings > API > anon public key
"""

import os
import sys
from pathlib import Path

import flet as ft
from supabase import create_client

# ── Path setup ────────────────────────────────────────────────────
ROOT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT_DIR))

from src.views.auth       import build_tela_auth
from src.views.theme      import C
from src.views.home       import build_aba_novo_projeto
from src.views.processing import build_aba_processamento
from src.views.gallery    import build_aba_galeria

# ── Supabase ──────────────────────────────────────────────────────
SUPABASE_URL      = os.getenv("SUPABASE_URL",      "https://SEU_PROJETO.supabase.co")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "SUA_ANON_KEY")

supabase = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)


def main(page: ft.Page):

    # ── Configuração da página ─────────────────────────────────────
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
            primary=C.ACCENT,
            secondary=C.CYAN,
            surface=C.SURFACE,
            on_primary=C.BG,
            on_surface=C.TEXT_PRIMARY,
        ),
        visual_density=ft.VisualDensity.COMPACT,
    )

    try:
            page.padding = ft.Padding.only(
                top=ft.SafeCast(page).top if hasattr(page, "safe_area") else 40
            )
    except:
        page.padding = ft.padding.only(top=40)


    # ── Estado global ──────────────────────────────────────────────
    estado = {"clipes": {}, "projetos": {}, "aba_atual": 0}

    # ── Área de conteúdo principal ─────────────────────────────────
    corpo = ft.Container(expand=True, bgcolor=C.BG)

    # ── Header ────────────────────────────────────────────────────
    usuario_txt = ft.Text(
        "", size=11, color=C.TEXT_MUTED, font_family="monospace",
    )

    def on_logout(e):
        try:
            supabase.auth.sign_out()
        except Exception:
            pass
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
                # Logo
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
                            size=16,
                            weight=ft.FontWeight.W_900,
                            color=C.TEXT_PRIMARY,
                            font_family="monospace",
                        ),
                    ],
                ),
                ft.Container(expand=True),
                # E-mail do usuário
                usuario_txt,
                # Logout
                btn_logout,
            ],
        ),
    )

    # ── App principal (construído após login) ──────────────────────

    def _construir_app(user):
        """Monta o app completo com as 3 abas após autenticação."""

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
            spacing=0,
            expand=True,
            controls=[
                conteudo_aba,
                ft.Container(
                    content=nav_bar,
                    border=ft.Border(top=ft.BorderSide(1, C.BORDER)),
                ),
            ],
        )

        # Atualiza header com dados do usuário
        email = getattr(user, "email", "") or ""
        usuario_txt.value  = email[:22] + ("…" if len(email) > 22 else "")
        btn_logout.visible = True
        page.update()

    def _mostrar_login():
        """Volta para a tela de login e limpa o header."""
        btn_logout.visible  = False
        usuario_txt.value   = ""
        corpo.content = build_tela_auth(
            page=page,
            supabase=supabase,
            on_autenticado=_construir_app,
        )
        page.update()

    # ── Verifica sessão existente ao abrir o app ───────────────────
    try:
        sessao = supabase.auth.get_session()
        if sessao and sessao.user:
            _construir_app(sessao.user)
        else:
            _mostrar_login()
    except Exception:
        _mostrar_login()

    # ── Layout final ───────────────────────────────────────────────
    page.add(
        ft.Column(
            spacing=0,
            expand=True,
            controls=[header, corpo],
        )
    )


if __name__ == "__main__":
        ft.run(main=main)
