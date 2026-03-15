"""
Tela de Login / Cadastro — Clip Engine
Flet 0.82 | API HTTP | Mobile-first

on_autenticado(user, token) é chamado com:
  user  = {"id": "...", "email": "...", "nome": "...", ...}
  token = access_token JWT (para usar em chamadas autenticadas)
"""

import re
import threading
from typing import Callable

import flet as ft
import httpx

from src.views.theme import C

API_BASE_URL = "http://127.0.0.1:8000/api"


def build_tela_auth(
    page: ft.Page,
    on_autenticado: Callable,       # on_autenticado(user: dict, token: str)
) -> ft.Control:

    _modo = {"valor": "login"}

    # ── Estilo dos campos ──────────────────────────────────────────
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
        height=56,
        expand=True,
        content_padding=ft.Padding(left=16, right=16, top=8, bottom=8),
    )

    # ── Campos ────────────────────────────────────────────────────
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

    # ── Mensagens e loading ────────────────────────────────────────
    msg_erro = ft.Text(
        "", color=C.ERROR, size=13, weight=ft.FontWeight.W_500,
        visible=False,
        animate_opacity=ft.Animation(200, ft.AnimationCurve.EASE_IN),
        text_align=ft.TextAlign.CENTER,
    )
    msg_info = ft.Text(
        "", color=C.SUCCESS, size=13, weight=ft.FontWeight.W_500,
        visible=False,
        animate_opacity=ft.Animation(200, ft.AnimationCurve.EASE_IN),
        text_align=ft.TextAlign.CENTER,
    )
    loading = ft.ProgressBar(
        color=C.ACCENT, bgcolor=C.BORDER, height=4,
        border_radius=4, visible=False,
    )

    # ── Títulos dinâmicos ─────────────────────────────────────────
    titulo = ft.Text(
        "Bem-vindo de volta",
        size=32, weight=ft.FontWeight.W_800,
        color=C.TEXT_PRIMARY,
        animate_opacity=ft.Animation(250, ft.AnimationCurve.EASE_IN_OUT),
        text_align=ft.TextAlign.CENTER,
    )
    subtitulo = ft.Text(
        "Entre para continuar no Clip Engine",
        size=15, color=C.TEXT_SECONDARY,
        animate_opacity=ft.Animation(250, ft.AnimationCurve.EASE_IN_OUT),
        text_align=ft.TextAlign.CENTER,
    )

    # ── Botões ────────────────────────────────────────────────────
    btn_principal = ft.FilledButton(
        content=ft.Text("Entrar", weight=ft.FontWeight.W_700, size=16),
        style=ft.ButtonStyle(
            bgcolor={
                ft.ControlState.DEFAULT:  C.ACCENT,
                ft.ControlState.HOVERED:  "#FF8C42",
                ft.ControlState.DISABLED: C.BORDER,
            },
            color=C.BG,
            shape=ft.RoundedRectangleBorder(radius=12),
            padding=ft.Padding(left=0, right=0, top=18, bottom=18),
            animation_duration=200,
        ),
        expand=True,
    )

    btn_alternar = ft.TextButton(
        "Não tem conta? Cadastre-se",
        style=ft.ButtonStyle(
            color={
                ft.ControlState.DEFAULT: ft.Colors.WHITE,
                ft.ControlState.HOVERED: ft.Colors.WHITE70,
            },
            text_style=ft.TextStyle(size=15, weight=ft.FontWeight.W_500),
        ),
    )

    btn_google = ft.OutlinedButton(
        content=ft.Row(
            spacing=12, tight=True,
            alignment=ft.MainAxisAlignment.CENTER,
            controls=[
                ft.Icon(ft.Icons.G_MOBILEDATA, color=C.ACCENT, size=24),
                ft.Text("Continuar com Google", color=C.TEXT_PRIMARY,
                    weight=ft.FontWeight.W_600, size=15),
            ],
        ),
        style=ft.ButtonStyle(
            side=ft.BorderSide(1.5, C.BORDER_ACCENT),
            shape=ft.RoundedRectangleBorder(radius=12),
            padding=ft.Padding(left=0, right=0, top=18, bottom=18),
            overlay_color={ft.ControlState.HOVERED: C.SURFACE_2},
        ),
        expand=True,
        on_click=lambda e: _login_google(e),
    )

    # ── Helpers de UI ─────────────────────────────────────────────

    def _set_loading(ativo: bool):
        loading.visible        = ativo
        btn_principal.disabled = ativo
        btn_alternar.disabled  = ativo
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

    # ── Alternar login ↔ cadastro ─────────────────────────────────

    def _atualizar_modo():
        modo     = _modo["valor"]
        eh_login = (modo == "login")

        if eh_login:
            campo_nome.visible     = False
            campo_confirma.visible = False
            campo_nome.opacity     = 0
            campo_confirma.opacity = 0
        else:
            campo_nome.visible     = True
            campo_confirma.visible = True
            campo_nome.opacity     = 1
            campo_confirma.opacity = 1

        btn_principal.content = ft.Text(
            "Entrar" if eh_login else "Criar conta",
            weight=ft.FontWeight.W_700, size=16,
        )
        btn_alternar.text = (
            "Não tem conta? Cadastre-se" if eh_login else "Já tem conta? Entrar"
        )
        titulo.value    = "Bem-vindo de volta" if eh_login else "Criar conta"
        subtitulo.value = (
            "Entre para continuar no Clip Engine"
            if eh_login else "Preencha os dados abaixo"
        )
        campo_email.value = ""
        campo_senha.value = ""
        if not eh_login:
            campo_nome.value     = ""
            campo_confirma.value = ""

        msg_erro.visible = False
        msg_info.visible = False
        page.update()

    def on_alternar(e):
        _modo["valor"] = "cadastro" if _modo["valor"] == "login" else "login"
        _atualizar_modo()

    btn_alternar.on_click = on_alternar

    # ── LOGIN via API ─────────────────────────────────────────────

    def _fazer_login():
        email = campo_email.value.strip()
        senha = campo_senha.value

        if not email or not senha:
            _set_erro("Preencha e-mail e senha.")
            return

        try:
            with httpx.Client(timeout=30.0) as client:
                resp = client.post(
                    f"{API_BASE_URL}/auth/login",
                    json={"email": email, "senha": senha},
                )

            if resp.status_code == 200:
                data = resp.json()
                if data.get("success"):
                    user  = data["user"]
                    token = data.get("session", {}).get("access_token", "")
                    # Chama o main.py com user dict + token
                    on_autenticado(user, token)
                else:
                    _set_erro(data.get("message", "Erro no login."))
            else:
                # Extrai mensagem do detail
                try:
                    detail = resp.json().get("detail", f"Erro {resp.status_code}")
                except Exception:
                    detail = resp.text[:120]
                _set_erro(detail)

        except httpx.ConnectError:
            _set_erro(f"Não foi possível conectar à API em {API_BASE_URL}.")
        except Exception as ex:
            _set_erro(f"Erro: {str(ex)[:120]}")

    # ── CADASTRO via API ──────────────────────────────────────────

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
            with httpx.Client(timeout=30.0) as client:
                resp = client.post(
                    f"{API_BASE_URL}/auth/register",
                    json={"nome": nome, "email": email, "senha": senha},
                )

            if resp.status_code == 201:
                data = resp.json()
                if data.get("success"):
                    # Se retornou sessão → login automático
                    if data.get("session") and data.get("user"):
                        user  = data["user"]
                        token = data["session"].get("access_token", "")
                        on_autenticado(user, token)
                    else:
                        # Supabase precisa de confirmação de e-mail
                        _set_info(data.get("message",
                            "Conta criada! Verifique seu e-mail e faça login."))
                        _modo["valor"] = "login"
                        _atualizar_modo()
                else:
                    _set_erro(data.get("message", "Erro no cadastro."))
            else:
                try:
                    detail = resp.json().get("detail", f"Erro {resp.status_code}")
                except Exception:
                    detail = resp.text[:120]
                _set_erro(detail)

        except httpx.ConnectError:
            _set_erro(f"Não foi possível conectar à API em {API_BASE_URL}.")
        except Exception as ex:
            _set_erro(f"Erro: {str(ex)[:120]}")

    # ── GOOGLE OAuth ──────────────────────────────────────────────

    def _login_google(e):
        try:
            with httpx.Client(timeout=10.0) as client:
                resp = client.post(f"{API_BASE_URL}/auth/google")
            if resp.status_code == 200:
                url = resp.json().get("url")
                if url:
                    page.launch_url(url)
                    _set_info("Navegador aberto. Autorize com sua conta Google.")
        except Exception as ex:
            _set_erro(f"Erro Google: {str(ex)[:120]}")

    # ── Handler botão principal ───────────────────────────────────

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

    # ── Divider ───────────────────────────────────────────────────

    divider_ou = ft.Row(
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
        controls=[
            ft.Container(height=1.5, expand=True, bgcolor=C.BORDER),
            ft.Container(
                padding=ft.Padding(left=16, right=16, top=4, bottom=4),
                content=ft.Text("ou", size=14, color=C.TEXT_MUTED, weight=ft.FontWeight.W_500),
            ),
            ft.Container(height=1.5, expand=True, bgcolor=C.BORDER),
        ],
    )

    # ── Logo ──────────────────────────────────────────────────────

    logo = ft.Container(
        content=ft.Column(
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=8,
            controls=[
                ft.Container(
                    width=64, height=64,
                    border_radius=16,
                    bgcolor=C.ACCENT,
                    alignment=ft.Alignment(0, 0),
                    animate=ft.Animation(400, ft.AnimationCurve.BOUNCE_OUT),
                    content=ft.Icon(ft.Icons.MOVIE_FILTER, color=C.BG, size=32),
                ),
                ft.Text("CLIP ENGINE", size=16, weight=ft.FontWeight.W_900,
                    color=C.TEXT_PRIMARY, font_family="monospace",
                    text_align=ft.TextAlign.CENTER),
                ft.Text("Dev Orbit Tech", size=11, color=C.TEXT_MUTED,
                    text_align=ft.TextAlign.CENTER),
            ],
        ),
    )

    # Inicializa modo
    _atualizar_modo()

    # ── Layout ────────────────────────────────────────────────────

    form_content = ft.Column(
        expand=True,
        horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        controls=[
            ft.Container(expand=True),
            ft.Column(
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=20,
                controls=[
                    logo,
                    ft.Container(height=8),
                    ft.Column(
                        spacing=8,
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        controls=[titulo, subtitulo],
                    ),
                    ft.Container(height=8),
                    ft.Row(controls=[btn_google]),
                    divider_ou,
                    campo_nome,
                    campo_email,
                    campo_senha,
                    campo_confirma,
                    msg_erro,
                    msg_info,
                    loading,
                    ft.Row(controls=[btn_principal]),
                    ft.Row(
                        alignment=ft.MainAxisAlignment.CENTER,
                        controls=[btn_alternar],
                    ),
                ],
            ),
            ft.Container(expand=True),
        ],
    )

    card = ft.Container(
        expand=True,
        border_radius=28,
        bgcolor=C.SURFACE,
        border=ft.Border(
            left=ft.BorderSide(1.5, C.BORDER),
            right=ft.BorderSide(1.5, C.BORDER),
            top=ft.BorderSide(1.5, C.BORDER),
            bottom=ft.BorderSide(1.5, C.BORDER),
        ),
        padding=ft.Padding(left=32, right=32, top=20, bottom=20),
        animate=ft.Animation(300, ft.AnimationCurve.EASE_OUT),
        content=form_content,
    )

    return ft.Container(
        expand=True,
        bgcolor=C.BG,
        alignment=ft.Alignment(0, 0),
        content=ft.Column(
            expand=True,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                ft.Container(
                    expand=True,
                    padding=ft.Padding(left=24, right=24, top=24, bottom=24),
                    content=card,
                ),
            ],
        ),
    )
