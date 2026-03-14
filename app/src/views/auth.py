"""
Tela de Login / Cadastro — Clip Engine
Flet 0.82 | Supabase Auth | Mobile-first

CORREÇÕES DE TAMANHO:
  • Card maior e mais espaçoso
  • Campos de texto com altura aumentada
  • Botões maiores e mais confortáveis
  • Melhor espaçamento entre elementos
  • Adaptação responsiva para tablets
"""

import threading
import time
from typing import Callable

import flet as ft
from supabase import Client

from src.views.theme import C


def build_tela_auth(
    page: ft.Page,
    supabase: Client,
    on_autenticado: Callable,
) -> ft.Control:

    _modo = {"valor": "login"}

    # ──────────────────────────────────────────────────────────────
    #  CAMPOS — TAMANHO AUMENTADO
    # ──────────────────────────────────────────────────────────────

    _field_style = dict(
        border_color=C.BORDER_ACCENT,
        focused_border_color=C.ACCENT,
        cursor_color=C.ACCENT,
        color=C.TEXT_PRIMARY,
        bgcolor=C.SURFACE_2,
        label_style=ft.TextStyle(color=C.TEXT_SECONDARY, size=14),
        hint_style=ft.TextStyle(color=C.TEXT_MUTED, size=13),
        border_radius=12,
        text_size=15,
        height=56,  # Altura fixa maior
        content_padding=ft.Padding(left=16, right=16, top=8, bottom=8),
    )

    campo_nome = ft.TextField(
        label="Nome completo",
        hint_text="Seu nome completo",
        prefix_icon=ft.Icons.PERSON_OUTLINE,
        visible=False,
        animate_opacity=ft.Animation(300, ft.AnimationCurve.EASE_IN_OUT),
        opacity=0,
        **_field_style,
    )

    campo_email = ft.TextField(
        label="E-mail",
        hint_text="seu@email.com",
        prefix_icon=ft.Icons.EMAIL_OUTLINED,
        keyboard_type=ft.KeyboardType.EMAIL,
        **_field_style,
    )

    campo_senha = ft.TextField(
        label="Senha",
        hint_text="Mínimo 6 caracteres",
        prefix_icon=ft.Icons.LOCK_OUTLINE,
        password=True,
        can_reveal_password=True,
        **_field_style,
    )

    campo_confirma = ft.TextField(
        label="Confirmar senha",
        hint_text="Repita a senha",
        prefix_icon=ft.Icons.LOCK_OUTLINE,
        password=True,
        can_reveal_password=True,
        visible=False,
        animate_opacity=ft.Animation(300, ft.AnimationCurve.EASE_IN_OUT),
        opacity=0,
        **_field_style,
    )

    msg_erro = ft.Text(
        "", color=C.ERROR, size=13, weight=ft.FontWeight.W_500, visible=False,
        animate_opacity=ft.Animation(200, ft.AnimationCurve.EASE_IN),
    )
    msg_info = ft.Text(
        "", color=C.SUCCESS, size=13, weight=ft.FontWeight.W_500, visible=False,
        animate_opacity=ft.Animation(200, ft.AnimationCurve.EASE_IN),
    )

    loading = ft.ProgressBar(
        color=C.ACCENT, bgcolor=C.BORDER, height=4,
        border_radius=4, visible=False,
    )

    # ──────────────────────────────────────────────────────────────
    #  TEXTOS DINÂMICOS — MAIORES
    # ──────────────────────────────────────────────────────────────

    titulo = ft.Text(
        "Bem-vindo de volta",
        size=32,  # Aumentado de 26 para 32
        weight=ft.FontWeight.W_800,
        color=C.TEXT_PRIMARY,
        animate_opacity=ft.Animation(250, ft.AnimationCurve.EASE_IN_OUT),
    )

    subtitulo = ft.Text(
        "Entre para continuar no Clip Engine",
        size=15,  # Aumentado de 13 para 15
        color=C.TEXT_SECONDARY,
        animate_opacity=ft.Animation(250, ft.AnimationCurve.EASE_IN_OUT),
    )

    # ──────────────────────────────────────────────────────────────
    #  ANIMAÇÃO DE SUCESSO — MAIOR
    # ──────────────────────────────────────────────────────────────

    icone_sucesso = ft.Container(
        visible=False,
        alignment=ft.Alignment(0, 0),
        animate_scale=ft.Animation(500, ft.AnimationCurve.BOUNCE_OUT),
        animate_opacity=ft.Animation(400, ft.AnimationCurve.EASE_OUT),
        scale=ft.Scale(0),
        opacity=0,
        content=ft.Column(
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=12,  # Aumentado
            controls=[
                ft.Container(
                    width=88, height=88,  # Aumentado de 72 para 88
                    border_radius=44,
                    bgcolor=C.SUCCESS + "22",
                    border=ft.Border.all(3, C.SUCCESS),  # Borda mais grossa
                    alignment=ft.Alignment(0, 0),
                    content=ft.Icon(ft.Icons.CHECK_ROUNDED, color=C.SUCCESS, size=44),
                ),
                ft.Text(
                    "Conta criada!",
                    size=18,  # Aumentado
                    weight=ft.FontWeight.W_700,
                    color=C.SUCCESS,
                ),
                ft.Text(
                    "Verifique seu e-mail para confirmar.",
                    size=13,  # Aumentado
                    color=C.TEXT_SECONDARY,
                    text_align=ft.TextAlign.CENTER,
                ),
            ],
        ),
    )

    def _animar_sucesso():
        """Mostra animação de sucesso e volta para login após 2.5s."""
        icone_sucesso.visible = True
        icone_sucesso.scale   = ft.Scale(1)
        icone_sucesso.opacity = 1
        page.update()
        time.sleep(2.5)
        icone_sucesso.opacity = 0
        icone_sucesso.scale   = ft.Scale(0.5)
        page.update()
        time.sleep(0.4)
        icone_sucesso.visible = False
        _modo["valor"] = "login"
        _atualizar_modo()

    # ──────────────────────────────────────────────────────────────
    #  BOTÕES — MAIORES E MAIS ESPAÇOSOS
    # ──────────────────────────────────────────────────────────────

    btn_principal = ft.FilledButton(
        content=ft.Text("Entrar", weight=ft.FontWeight.W_700, size=16),  # Texto maior
        style=ft.ButtonStyle(
            bgcolor={
                ft.ControlState.DEFAULT:  C.ACCENT,
                ft.ControlState.HOVERED:  "#FF8C42",
                ft.ControlState.DISABLED: C.BORDER,
            },
            color=C.BG,
            shape=ft.RoundedRectangleBorder(radius=12),
            padding=ft.Padding(left=0, right=0, top=18, bottom=18),  # Padding vertical aumentado
            animation_duration=200,
        ),
        expand=True,
    )

    btn_alternar = ft.TextButton(
        style=ft.ButtonStyle(color=C.ACCENT, text_style=ft.TextStyle(size=15)),  # Texto maior
    )

    btn_google = ft.OutlinedButton(
        content=ft.Row(
            spacing=12,  # Aumentado
            tight=True,
            alignment=ft.MainAxisAlignment.CENTER,
            controls=[
                ft.Icon(ft.Icons.G_MOBILEDATA, color=C.ACCENT, size=24),  # Ícone maior
                ft.Text(
                    "Continuar com Google",
                    color=C.TEXT_PRIMARY,
                    weight=ft.FontWeight.W_600,
                    size=15,  # Aumentado
                ),
            ],
        ),
        style=ft.ButtonStyle(
            side=ft.BorderSide(1.5, C.BORDER_ACCENT),  # Borda mais grossa
            shape=ft.RoundedRectangleBorder(radius=12),
            padding=ft.Padding(left=0, right=0, top=18, bottom=18),  # Padding maior
            overlay_color={ft.ControlState.HOVERED: C.SURFACE_2},
        ),
        expand=True,
        on_click=lambda e: _login_google(e),
    )

    # ──────────────────────────────────────────────────────────────
    #  HELPERS UI
    # ──────────────────────────────────────────────────────────────

    def _set_loading(ativo: bool):
        loading.visible        = ativo
        btn_principal.disabled = ativo
        btn_google.disabled    = ativo
        page.update()

    def _set_erro(mensagem: str):
        msg_erro.value   = mensagem
        msg_erro.visible = bool(mensagem)
        msg_erro.opacity = 1 if mensagem else 0
        msg_info.visible = False
        _set_loading(False)
        page.update()

    def _set_info(mensagem: str):
        msg_info.value   = mensagem
        msg_info.visible = bool(mensagem)
        msg_info.opacity = 1 if mensagem else 0
        msg_erro.visible = False
        _set_loading(False)
        page.update()

    # ──────────────────────────────────────────────────────────────
    #  ALTERNAR LOGIN ↔ CADASTRO
    # ──────────────────────────────────────────────────────────────

    def _atualizar_modo():
        modo     = _modo["valor"]
        eh_login = (modo == "login")

        # Anima entrada dos campos extras
        if eh_login:
            campo_nome.opacity     = 0
            campo_confirma.opacity = 0
            page.update()
            time.sleep(0.15)
            campo_nome.visible     = False
            campo_confirma.visible = False
        else:
            campo_nome.visible     = True
            campo_confirma.visible = True
            page.update()
            time.sleep(0.05)
            campo_nome.opacity     = 1
            campo_confirma.opacity = 1

        btn_principal.content = ft.Text(
            "Entrar" if eh_login else "Criar conta",
            weight=ft.FontWeight.W_700, size=16,
        )
        btn_alternar.text = (
            "Não tem conta? Cadastre-se"
            if eh_login else
            "Já tem conta? Entrar"
        )

        titulo.opacity    = 0
        subtitulo.opacity = 0
        page.update()
        time.sleep(0.1)

        titulo.value    = "Bem-vindo de volta" if eh_login else "Criar conta"
        subtitulo.value = (
            "Entre para continuar no Clip Engine"
            if eh_login else
            "Preencha os dados abaixo"
        )
        titulo.opacity    = 1
        subtitulo.opacity = 1

        msg_erro.visible  = False
        msg_info.visible  = False
        campo_senha.value = ""
        if not eh_login:
            campo_confirma.value = ""

        page.update()

    def on_alternar(e):
        def _trocar():
            _modo["valor"] = "cadastro" if _modo["valor"] == "login" else "login"
            _atualizar_modo()
        threading.Thread(target=_trocar, daemon=True).start()

    btn_alternar.on_click = on_alternar

    # ──────────────────────────────────────────────────────────────
    #  AUTH FUNCTIONS (mantidas iguais)
    # ──────────────────────────────────────────────────────────────

    def _fazer_login():
        email = campo_email.value.strip()
        senha = campo_senha.value

        if not email or not senha:
            _set_erro("Preencha e-mail e senha.")
            return

        try:
            resp = supabase.auth.sign_in_with_password(
                {"email": email, "password": senha}
            )
            if resp.user:
                on_autenticado(resp.user)
            else:
                _set_erro("Credenciais inválidas.")
        except Exception as ex:
            msg = str(ex)
            if "Invalid login credentials" in msg:
                _set_erro("E-mail ou senha incorretos.")
            elif "Email not confirmed" in msg:
                _set_erro("Confirme seu e-mail antes de entrar.")
            else:
                _set_erro(f"Erro: {msg[:120]}")

    def _fazer_cadastro():
        nome  = campo_nome.value.strip()
        email = campo_email.value.strip()
        senha = campo_senha.value
        conf  = campo_confirma.value

        if not nome:
            _set_erro("Informe seu nome.")
            return
        if not email:
            _set_erro("Informe seu e-mail.")
            return
        if len(senha) < 6:
            _set_erro("A senha deve ter pelo menos 6 caracteres.")
            return
        if senha != conf:
            _set_erro("As senhas não coincidem.")
            return

        try:
            resp = supabase.auth.sign_up({
                "email":   email,
                "password": senha,
                "options": {"data": {"full_name": nome}},
            })
            if resp.user:
                _set_loading(False)
                threading.Thread(target=_animar_sucesso, daemon=True).start()
            else:
                _set_erro("Não foi possível criar a conta.")
        except Exception as ex:
            msg = str(ex)
            if "already registered" in msg or "already exists" in msg:
                _set_erro("Este e-mail já está cadastrado.")
            else:
                _set_erro(f"Erro: {msg[:120]}")

    def _login_google(e):
        try:
            resp = supabase.auth.sign_in_with_oauth({
                "provider": "google",
                "options":  {"redirect_to": "io.clipengine.app://login-callback"},
            })
            if resp.url:
                page.launch_url(resp.url)
                _set_info("Navegador aberto. Autorize com sua conta Google.")
        except Exception as ex:
            _set_erro(f"Erro Google: {str(ex)[:120]}")

    # ──────────────────────────────────────────────────────────────
    #  HANDLER BOTÃO PRINCIPAL
    # ──────────────────────────────────────────────────────────────

    def on_btn_principal(e):
        _set_loading(True)
        msg_erro.visible = False
        msg_info.visible = False
        page.update()

        def _executar():
            if _modo["valor"] == "login":
                _fazer_login()
            else:
                _fazer_cadastro()
            _set_loading(False)

        threading.Thread(target=_executar, daemon=True).start()

    btn_principal.on_click = on_btn_principal

    # ──────────────────────────────────────────────────────────────
    #  DIVIDER "ou" — MAIS ESPAÇOSO
    # ──────────────────────────────────────────────────────────────

    divider_ou = ft.Row(
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
        controls=[
            ft.Container(height=1.5, expand=True, bgcolor=C.BORDER),  # Linha mais grossa
            ft.Container(
                padding=ft.Padding(left=16, right=16, top=4, bottom=4),
                content=ft.Text("ou", size=14, color=C.TEXT_MUTED, weight=ft.FontWeight.W_500),
            ),
            ft.Container(height=1.5, expand=True, bgcolor=C.BORDER),
        ],
    )

    # ──────────────────────────────────────────────────────────────
    #  LOGO — MAIOR
    # ──────────────────────────────────────────────────────────────

    logo = ft.Row(
        alignment=ft.MainAxisAlignment.CENTER,
        controls=[
            ft.Column(
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=8,  # Aumentado
                controls=[
                    ft.Container(
                        width=64, height=64,  # Aumentado de 52 para 64
                        border_radius=16,
                        bgcolor=C.ACCENT,
                        alignment=ft.Alignment(0, 0),
                        animate=ft.Animation(400, ft.AnimationCurve.BOUNCE_OUT),
                        content=ft.Icon(
                            ft.Icons.MOVIE_FILTER,
                            color=C.BG, size=32,  # Ícone maior
                        ),
                    ),
                    ft.Text(
                        "CLIP ENGINE",
                        size=16, weight=ft.FontWeight.W_900,  # Aumentado
                        color=C.TEXT_PRIMARY, font_family="monospace",
                        text_align=ft.TextAlign.CENTER,
                    ),
                    ft.Text(
                        "Dev Orbit Tech",
                        size=11, color=C.TEXT_MUTED,  # Aumentado
                        text_align=ft.TextAlign.CENTER,
                    ),
                ],
            ),
        ],
    )

    # ──────────────────────────────────────────────────────────────
    #  INICIALIZA O MODO
    # ──────────────────────────────────────────────────────────────

    _atualizar_modo()

    # ──────────────────────────────────────────────────────────────
    #  CARD PRINCIPAL — MAIOR E COM MAIS ESPAÇAMENTO
    # ──────────────────────────────────────────────────────────────

    card = ft.Container(
        border_radius=28,  # Mais arredondado
        bgcolor=C.SURFACE,
        border=ft.Border.all(1.5, C.BORDER),  # Borda mais visível
        padding=ft.Padding(left=32, right=32, top=40, bottom=40),  # Padding interno maior
        animate=ft.Animation(300, ft.AnimationCurve.EASE_OUT),
        content=ft.Column(
            spacing=20,  # Espaçamento entre elementos aumentado
            scroll=ft.ScrollMode.AUTO,
            controls=[
                # Logo
                logo,

                ft.Container(height=8),  # Espaço extra

                # Título e subtítulo
                ft.Column(
                    spacing=8,  # Aumentado
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[titulo, subtitulo],
                ),

                ft.Container(height=8),

                # Botão Google
                ft.Row(controls=[btn_google]),

                # Divider "ou"
                divider_ou,

                # Campos de entrada
                campo_nome,
                campo_email,
                campo_senha,
                campo_confirma,

                # Mensagens
                msg_erro,
                msg_info,

                loading,

                # Animação de sucesso
                icone_sucesso,

                # Botão principal
                ft.Row(controls=[btn_principal]),

                # Botão alternar modo
                ft.Row(
                    alignment=ft.MainAxisAlignment.CENTER,
                    controls=[btn_alternar],
                ),
            ],
        ),
    )

    # ──────────────────────────────────────────────────────────────
    #  LAYOUT FINAL — RESPONSIVO E CENTRALIZADO
    #  • No celular: card ocupa quase toda largura
    #  • No tablet: card com largura máxima de 500px
    #  • No desktop: card com largura máxima de 550px
    # ──────────────────────────────────────────────────────────────

    def get_card_width():
        """Retorna largura responsiva baseada no tamanho da tela."""
        if page.width < 600:  # Celular
            return None  # Ocupa 100% com padding
        elif page.width < 900:  # Tablet
            return 500
        else:  # Desktop
            return 550

    # Atualiza largura do card quando a página for redimensionada
    def on_page_resize(e=None):
        card.width = get_card_width()
        page.update()

    page.on_resize = on_page_resize

    # Container principal que ocupa toda a tela
    return ft.Container(
        expand=True,
        bgcolor=C.BG,
        alignment=ft.Alignment(0, 0),
        content=ft.ResponsiveRow(
            controls=[
                ft.Container(
                    col={"xs": 12, "sm": 12, "md": 8, "lg": 6, "xl": 5},
                    alignment=ft.Alignment(0, 0),
                    padding=ft.Padding(left=24, right=24, top=32, bottom=32),  # Padding externo maior
                    content=card,
                ),
            ],
            alignment=ft.MainAxisAlignment.CENTER,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            expand=True,
        ),
    )
