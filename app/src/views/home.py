"""
Aba 1 — Novo Projeto (cloud conectado)
Flet 0.82 | Compatível com Android e Desktop

Funcionalidades:
  • URL do YouTube ou upload de vídeo da galeria
  • Configurações: clipes, duração, legendas, cor, formato, tracking
  • Animação por etapa do pipeline + aviso de "não feche o app"
  • Botões de download por clipe gerado
  • Card simulado de demonstração
  • Salva clipes no Supabase e libera para download no dispositivo
"""

import io
import json
import math
import threading
import time
import uuid
from pathlib import Path

import flet as ft
import httpx

# ── ngrok: evita página de aviso do browser ──────────────────────
_NGROK_HEADERS = {"ngrok-skip-browser-warning": "true"}


from src.views.components import clip_card, tag
from src.views.models import ClipSugerido
from src.views.theme import C

API_BASE_URL    = "https://perceptible-westin-checkable.ngrok-free.dev"
REQUEST_TIMEOUT = 120.0


# ─────────────────────────────────────────────────────────────────
#  CARD DE DEMONSTRAÇÃO (simula vídeo sendo gerado)
# ─────────────────────────────────────────────────────────────────

def _build_demo_card(page: ft.Page) -> ft.Control:
    """Card animado que simula um clipe sendo gerado — dá vida ao app."""


    try:
        page.padding = ft.padding.only(
            top=ft.SafeCast(page).top if hasattr(page, "safe_area") else 40
        )
    except:
        page.padding = ft.padding.only(top=40)

    _ETAPAS_DEMO = [
        (ft.Icons.DOWNLOAD_OUTLINED,       "Baixando vídeo...",         0.20),
        (ft.Icons.GRAPHIC_EQ,              "Transcrevendo áudio...",    0.45),
        (ft.Icons.PSYCHOLOGY_OUTLINED,     "Analisando com IA...",      0.70),
        (ft.Icons.MOVIE_CREATION_OUTLINED, "Gerando clipes...",         0.90),
        (ft.Icons.CHECK_CIRCLE_OUTLINED,   "✅ 3 clipes prontos!",      1.00),
    ]

    _etapa_idx  = [0]
    _running    = [True]

    etapa_icon  = ft.Icon(_ETAPAS_DEMO[0][0], color=C.ACCENT, size=18)
    etapa_label = ft.Text(
        _ETAPAS_DEMO[0][1], size=12,
        color=C.ACCENT, weight=ft.FontWeight.W_600,
    )
    demo_bar = ft.ProgressBar(
        value=0.0, color=C.ACCENT, bgcolor=C.BORDER,
        height=3, border_radius=3,
    )
    demo_thumb = ft.Container(
        width=52, height=52,
        border_radius=6,
        bgcolor=C.SURFACE_2,
        content=ft.Icon(ft.Icons.PLAY_CIRCLE_FILL_OUTLINED,
                        color=C.ACCENT, size=28),
        alignment=ft.Alignment(0, 0),
    )
    demo_title = ft.Text(
        "Como criar conteúdo viral", size=13,
        weight=ft.FontWeight.W_700, color=C.TEXT_PRIMARY,
    )
    demo_sub = ft.Text(
        "YouTube • 18:32 min", size=11, color=C.TEXT_MUTED,
    )

    card = ft.Container(
        border_radius=10,
        bgcolor=C.SURFACE,
        border=ft.Border(
            left=ft.BorderSide(1, C.BORDER_ACCENT),
            right=ft.BorderSide(1, C.BORDER_ACCENT),
            top=ft.BorderSide(1, C.BORDER_ACCENT),
            bottom=ft.BorderSide(1, C.BORDER_ACCENT),
        ),
        padding=ft.Padding(14, 12, 14, 12),
        content=ft.Column(
            spacing=10,
            controls=[
                ft.Row(
                    spacing=6,
                    controls=[
                        ft.Icon(ft.Icons.AUTO_AWESOME, color=C.ACCENT, size=13),
                        ft.Text("Exemplo ao vivo", size=11,
                                color=C.ACCENT, weight=ft.FontWeight.W_600),
                        ft.Container(expand=True),
                        ft.Container(
                            bgcolor=C.ACCENT_SOFT,
                            border_radius=20,
                            padding=ft.Padding(6, 2, 6, 2),
                            content=ft.Text("DEMO", size=9,
                                            color=C.ACCENT,
                                            weight=ft.FontWeight.W_700),
                        ),
                    ],
                ),
                ft.Row(
                    spacing=10,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        demo_thumb,
                        ft.Column(
                            spacing=3, expand=True,
                            controls=[demo_title, demo_sub],
                        ),
                    ],
                ),
                ft.Row(
                    spacing=8,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[etapa_icon, etapa_label],
                ),
                demo_bar,
            ],
        ),
    )

    def _animar():
        while _running[0]:
            idx = _etapa_idx[0]
            if idx >= len(_ETAPAS_DEMO):
                idx = 0
                _etapa_idx[0] = 0

            ic, lbl, alvo = _ETAPAS_DEMO[idx]
            inicio = demo_bar.value or 0.0

            # Anima suavemente até o alvo
            passos = 30
            for p in range(passos + 1):
                if not _running[0]:
                    return
                demo_bar.value    = inicio + (alvo - inicio) * (p / passos)
                etapa_icon.name   = ic
                etapa_label.value = lbl
                etapa_label.color = C.SUCCESS if idx == len(_ETAPAS_DEMO) - 1 else C.ACCENT
                etapa_icon.color  = C.SUCCESS if idx == len(_ETAPAS_DEMO) - 1 else C.ACCENT
                try:
                    page.update()
                except Exception:
                    return
                time.sleep(0.04)

            _etapa_idx[0] += 1
            # Pausa na última etapa, depois recomeça
            if idx == len(_ETAPAS_DEMO) - 1:
                time.sleep(2.5)
                demo_bar.value = 0.0
                try:
                    page.update()
                except Exception:
                    return
            else:
                time.sleep(0.4)

    t = threading.Thread(target=_animar, daemon=True)
    t.start()
    card._demo_stop = lambda: _running.__setitem__(0, False)
    return card


# ─────────────────────────────────────────────────────────────────
#  ANIMAÇÃO DE ETAPA (spinner pulsante)
# ─────────────────────────────────────────────────────────────────

def _spinner_ring(cor: str = None) -> ft.Control:
    """Anel giratório simples (ProgressRing pequeno)."""
    return ft.ProgressRing(
        width=14, height=14,
        stroke_width=2,
        color=cor or C.ACCENT,
    )


# ─────────────────────────────────────────────────────────────────
#  BUILD PRINCIPAL
# ─────────────────────────────────────────────────────────────────

def build_aba_novo_projeto(estado: dict, page: ft.Page) -> ft.Control:

    # ── Usuário ──────────────────────────────────────────────────
    def _get_user_id() -> str:
        return (estado.get("user_info") or {}).get("id", "")

    # ── Estado de configurações ──────────────────────────────────
    cfg = {
        "num_clips":     3,
        "clip_duration": 60,
        "subtitles":     True,
        "legenda_cor":   "white",
        "formato":       "9:16",
        "tracking":      True,
    }

    # ── Mapa de status da API → índice de etapa ──────────────────
    _STATUS_ETAPA = {
        "pending":      0,
        "downloading":  0,
        "processing":   1,
        "transcribing": 2,
        "analyzing":    2,
        "done":         3,
        "error":        3,
    }

    # ─────────────────────────────────────────────────────────────
    #  CONTROLES PRINCIPAIS
    # ─────────────────────────────────────────────────────────────

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

    status_text  = ft.Text("", size=12, color=C.TEXT_SECONDARY)
    progress_row = ft.ProgressBar(
        value=0, color=C.ACCENT, bgcolor=C.BORDER,
        height=3, border_radius=3, visible=False,
    )
    clips_column  = ft.Column(spacing=10, visible=False)
    etapas_column = ft.Column(spacing=4)

    # Aviso "não feche o app"
    aviso_nao_feche = ft.Container(
        visible=False,
        border_radius=8,
        bgcolor="#FF6B0015",
        border=ft.Border(
            left=ft.BorderSide(1, "#FF6B0055"),
            right=ft.BorderSide(1, "#FF6B0055"),
            top=ft.BorderSide(1, "#FF6B0055"),
            bottom=ft.BorderSide(1, "#FF6B0055"),
        ),
        padding=ft.Padding(12, 10, 12, 10),
        content=ft.Row(
            spacing=10,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                ft.Icon(ft.Icons.LOCK_CLOCK, color="#FF6B00", size=16),
                ft.Text(
                    "Por segurança, não feche o app enquanto o vídeo está sendo processado.",
                    size=12,
                    color="#FF6B00",
                    weight=ft.FontWeight.W_600,
                    expand=True,
                ),
            ],
        ),
    )

    # ─────────────────────────────────────────────────────────────
    #  CONFIGURAÇÕES — INPUT SHOTS
    # ─────────────────────────────────────────────────────────────

    def _val_shots(e):
        v = e.control.value
        if v and v.isdigit() and 1 <= int(v) <= 10:
            cfg["num_clips"]     = int(v)
            e.control.error_text = None
        elif v:
            e.control.error_text = "Entre 1 e 10"
        e.control.update()

    input_shots = ft.TextField(
        value="3",
        label="Clipes (1–10)",
        keyboard_type=ft.KeyboardType.NUMBER,
        border_color=C.BORDER_ACCENT,
        focused_border_color=C.ACCENT,
        cursor_color=C.ACCENT,
        color=C.TEXT_PRIMARY,
        bgcolor=C.SURFACE_2,
        label_style=ft.TextStyle(color=C.TEXT_SECONDARY, size=12),
        border_radius=8,
        input_filter=ft.InputFilter(
            allow=True,
            regex_string=r"^[0-9]*$",
            replacement_string="",
        ),
        on_change=_val_shots,
        expand=True,
    )

    # ─────────────────────────────────────────────────────────────
    #  CONFIGURAÇÕES — DURAÇÃO
    # ─────────────────────────────────────────────────────────────

    def _on_duracao(e):
        try:
            cfg["clip_duration"] = int(e.control.value)
        except (ValueError, TypeError):
            pass

    dropdown_duracao = ft.Dropdown(
        label="Duração",
        value="60",
        options=[
            ft.dropdown.Option("30", "30 seg"),
            ft.dropdown.Option("60", "60 seg"),
            ft.dropdown.Option("90", "90 seg"),
        ],
        border_color=C.BORDER_ACCENT,
        focused_border_color=C.ACCENT,
        color=C.TEXT_PRIMARY,
        bgcolor=C.SURFACE_2,
        label_style=ft.TextStyle(color=C.TEXT_SECONDARY, size=12),
        border_radius=8,
        expand=True,
    )

    # ─────────────────────────────────────────────────────────────
    #  CONFIGURAÇÕES — PREVIEW DE LEGENDA
    # ─────────────────────────────────────────────────────────────

    preview_text = ft.Text(
        "PALAVRA POR PALAVRA",
        size=14,
        weight=ft.FontWeight.W_900,
        color="#FFFFFF",
        font_family="monospace",
        text_align=ft.TextAlign.CENTER,
    )
    preview_legenda = ft.Container(
        visible=True,
        border_radius=8,
        bgcolor="#111118",
        padding=ft.Padding(16, 12, 16, 12),
        height=80,
        alignment=ft.Alignment(0, 0),
        content=preview_text,
    )

    # ─────────────────────────────────────────────────────────────
    #  CONFIGURAÇÕES — CORES DA LEGENDA
    # ─────────────────────────────────────────────────────────────

    _CORES_LEGENDA = {
        "white":  ("#FFFFFF", "Branco"),
        "yellow": ("#FFE000", "Amarelo"),
        "blue":   ("#5599FF", "Azul"),
        "green":  ("#44DD88", "Verde"),
    }

    cor_btns: dict = {}

    def _on_cor(cor_key: str):
        cfg["legenda_cor"] = cor_key
        for k, btn in cor_btns.items():
            selecionado = (k == cor_key)
            btn.style = ft.ButtonStyle(
                bgcolor=_CORES_LEGENDA[k][0],
                shape=ft.CircleBorder(),
                side=ft.BorderSide(
                    3 if selecionado else 0,
                    C.TEXT_PRIMARY if selecionado else "transparent",
                ),
                padding=ft.Padding(0, 0, 0, 0),
            )
        preview_text.color = _CORES_LEGENDA[cor_key][0]
        page.update()

    for cor_key, (hex_cor, label_cor) in _CORES_LEGENDA.items():
        _btn = ft.IconButton(
            icon=ft.Icons.SUBTITLES_OUTLINED,
            width=32,
            height=32,
            tooltip=label_cor,
            on_click=lambda e, k=cor_key: _on_cor(k),
            style=ft.ButtonStyle(
                bgcolor=hex_cor,
                shape=ft.CircleBorder(),
                side=ft.BorderSide(
                    3 if cor_key == "white" else 0,
                    C.TEXT_PRIMARY if cor_key == "white" else "transparent",
                ),
                padding=ft.Padding(0, 0, 0, 0),
            ),
        )
        cor_btns[cor_key] = _btn

    row_cor_legenda = ft.Row(
        spacing=10,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
        controls=[
            ft.Text("Cor:", size=12, color=C.TEXT_SECONDARY),
            *cor_btns.values(),
        ],
    )

    # ─────────────────────────────────────────────────────────────
    #  CONFIGURAÇÕES — SWITCH DE LEGENDAS
    # ─────────────────────────────────────────────────────────────

    legenda_label = ft.Text(
        "Legendas: ON", size=12,
        color=C.SUCCESS, weight=ft.FontWeight.W_600,
    )

    def _on_legenda_switch(e):
        ativo                   = e.control.value
        cfg["subtitles"]        = ativo
        legenda_label.value     = "Legendas: ON" if ativo else "Legendas: OFF"
        legenda_label.color     = C.SUCCESS if ativo else C.TEXT_MUTED
        row_cor_legenda.visible = ativo
        preview_legenda.visible = ativo
        page.update()

    switch_legenda = ft.Switch(
        value=True,
        active_color=C.ACCENT,
        on_change=_on_legenda_switch,
    )

    # ─────────────────────────────────────────────────────────────
    #  CONFIGURAÇÕES — FORMATO
    # ─────────────────────────────────────────────────────────────

    _FORMATOS = [
        ("9:16",  ft.Icons.STAY_CURRENT_PORTRAIT,  "Shorts / Reels"),
        ("16:9",  ft.Icons.STAY_CURRENT_LANDSCAPE, "Landscape"),
    ]

    formato_btns: dict = {}

    def _on_formato(fmt: str):
        cfg["formato"] = fmt
        for k, (btn, lbl) in formato_btns.items():
            sel = (k == fmt)
            btn.style = ft.ButtonStyle(
                bgcolor=C.ACCENT_SOFT if sel else C.SURFACE_2,
                side=ft.BorderSide(
                    1.5 if sel else 1,
                    C.ACCENT if sel else C.BORDER,
                ),
                shape=ft.RoundedRectangleBorder(radius=8),
                padding=ft.Padding(10, 8, 10, 8),
            )
            btn.icon_color = C.ACCENT if sel else C.TEXT_SECONDARY
            lbl.color      = C.ACCENT if sel else C.TEXT_SECONDARY
            lbl.weight     = ft.FontWeight.W_600 if sel else ft.FontWeight.NORMAL
        page.update()

    for fmt, icone, desc in _FORMATOS:
        _lbl = ft.Text(
            desc, size=11,
            color=C.TEXT_SECONDARY if fmt != "9:16" else C.ACCENT,
        )
        _btn = ft.IconButton(
            icon=icone,
            icon_color=C.ACCENT if fmt == "9:16" else C.TEXT_SECONDARY,
            icon_size=20,
            tooltip=desc,
            on_click=lambda e, f=fmt: _on_formato(f),
            style=ft.ButtonStyle(
                bgcolor=C.ACCENT_SOFT if fmt == "9:16" else C.SURFACE_2,
                side=ft.BorderSide(
                    1.5 if fmt == "9:16" else 1,
                    C.ACCENT if fmt == "9:16" else C.BORDER,
                ),
                shape=ft.RoundedRectangleBorder(radius=8),
                padding=ft.Padding(10, 8, 10, 8),
            ),
        )
        formato_btns[fmt] = (_btn, _lbl)

    row_formato = ft.Row(
        spacing=8,
        controls=[
            ft.Column(
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=4,
                controls=[formato_btns["9:16"][0], formato_btns["9:16"][1]],
            ),
            ft.Column(
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=4,
                controls=[formato_btns["16:9"][0], formato_btns["16:9"][1]],
            ),
        ],
    )

    # ─────────────────────────────────────────────────────────────
    #  CONFIGURAÇÕES — FACE TRACKING
    # ─────────────────────────────────────────────────────────────

    def _on_tracking(e):
        cfg["tracking"] = e.control.value

    switch_tracking = ft.Switch(
        value=True,
        active_color=C.ACCENT,
        on_change=_on_tracking,
    )

    # ─────────────────────────────────────────────────────────────
    #  PAINEL DE CONFIGURAÇÕES
    # ─────────────────────────────────────────────────────────────

    def _borda(cor=None):
        c = cor or C.BORDER
        return ft.Border(
            left=ft.BorderSide(1, c), right=ft.BorderSide(1, c),
            top=ft.BorderSide(1, c),  bottom=ft.BorderSide(1, c),
        )

    painel_config = ft.Container(
        border_radius=10,
        bgcolor=C.SURFACE,
        border=_borda(),
        padding=ft.Padding(16, 14, 16, 14),
        content=ft.Column(
            spacing=14,
            controls=[
                ft.Row(
                    spacing=8,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        ft.Icon(ft.Icons.TUNE, color=C.ACCENT, size=16),
                        ft.Text("Configurações do clipe", size=13,
                                weight=ft.FontWeight.W_700, color=C.TEXT_PRIMARY),
                    ],
                ),
                ft.Container(height=1, bgcolor=C.BORDER),
                ft.Row(spacing=10, controls=[input_shots, dropdown_duracao]),
                ft.Column(
                    spacing=8,
                    controls=[
                        ft.Text("Formato", size=12,
                                color=C.TEXT_SECONDARY, weight=ft.FontWeight.W_600),
                        row_formato,
                    ],
                ),
                ft.Container(height=1, bgcolor=C.BORDER),
                ft.Row(
                    spacing=0,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        ft.Icon(ft.Icons.SUBTITLES_OUTLINED,
                                color=C.TEXT_SECONDARY, size=16),
                        ft.Container(width=8),
                        legenda_label,
                        ft.Container(expand=True),
                        switch_legenda,
                    ],
                ),
                row_cor_legenda,
                ft.Column(
                    spacing=6,
                    controls=[
                        ft.Text("Preview", size=11, color=C.TEXT_MUTED),
                        preview_legenda,
                    ],
                ),
                ft.Container(height=1, bgcolor=C.BORDER),
                ft.Row(
                    spacing=0,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        ft.Icon(ft.Icons.FACE_OUTLINED,
                                color=C.TEXT_SECONDARY, size=16),
                        ft.Container(width=8),
                        ft.Text("Face tracking", size=12, color=C.TEXT_SECONDARY),
                        ft.Container(expand=True),
                        switch_tracking,
                    ],
                ),
            ],
        ),
    )

    # ─────────────────────────────────────────────────────────────
    #  NOTIFICAÇÃO
    # ─────────────────────────────────────────────────────────────

    def _notificar(mensagem: str, cor: str = C.SUCCESS, duracao: int = 6000):
        icone = (
            ft.Icons.CHECK_CIRCLE if cor == C.SUCCESS
            else ft.Icons.INFO    if cor == C.CYAN
            else ft.Icons.ERROR
        )
        page.snack_bar = ft.SnackBar(
            content=ft.Row(
                spacing=10,
                controls=[
                    ft.Icon(icone, color=cor, size=18),
                    ft.Text(mensagem, color=C.TEXT_PRIMARY, size=13, expand=True),
                ],
            ),
            bgcolor=C.SURFACE_2,
            duration=duracao,
            show_close_icon=True,
            close_icon_color=C.TEXT_SECONDARY,
        )
        page.snack_bar.open = True
        page.update()

    # ─────────────────────────────────────────────────────────────
    #  ETAPAS VISUAIS COM ANIMAÇÃO
    # ─────────────────────────────────────────────────────────────

    _ETAPAS_INFO = [
        (ft.Icons.DOWNLOAD_OUTLINED,       "Download do vídeo"),
        (ft.Icons.GRAPHIC_EQ,              "Transcrição Whisper"),
        (ft.Icons.PSYCHOLOGY_OUTLINED,     "Análise de IA"),
        (ft.Icons.MOVIE_CREATION_OUTLINED, "Geração de clipes"),
    ]

    def atualizar_etapas(etapa_atual: int):
        controles = []
        for i, (icone, label) in enumerate(_ETAPAS_INFO):
            concluida = i < etapa_atual
            ativa     = i == etapa_atual
            pendente  = i > etapa_atual

            if concluida:
                cor = C.SUCCESS
                ic_widget = ft.Icon(ft.Icons.CHECK_CIRCLE, size=16, color=cor)
            elif ativa:
                cor = C.ACCENT
                ic_widget = _spinner_ring(C.ACCENT)
            else:
                cor = C.TEXT_MUTED
                ic_widget = ft.Icon(icone, size=16, color=cor)

            controles.append(ft.Row(
                spacing=8,
                controls=[
                    ic_widget,
                    ft.Text(
                        label, size=12, color=cor,
                        weight=ft.FontWeight.W_600 if ativa else ft.FontWeight.NORMAL,
                    ),
                ],
            ))
            if i < len(_ETAPAS_INFO) - 1:
                controles.append(ft.Container(
                    width=1, height=12, bgcolor=C.BORDER,
                    margin=ft.Margin(left=7, right=0, top=0, bottom=0),
                ))
        etapas_column.controls = controles
        page.update()

    # ─────────────────────────────────────────────────────────────
    #  HELPERS DE UI
    # ─────────────────────────────────────────────────────────────

    def _iniciar_pipeline_ui():
        """Ativa controles visuais ao iniciar qualquer pipeline."""
        aviso_nao_feche.visible  = True
        progress_row.visible     = True
        progress_row.value       = 0.0
        clips_column.visible     = False
        etapas_column.controls   = []
        btn_download.disabled    = True
        btn_gallery.disabled     = True
        atualizar_etapas(0)
        page.update()

    def _finalizar_pipeline_ui():
        """Remove aviso e reativa botões ao concluir."""
        aviso_nao_feche.visible = False
        btn_download.disabled   = False
        btn_gallery.disabled    = False
        page.update()

    def _set_erro(mensagem: str):
        status_text.value  = f"✗ {mensagem}"
        status_text.color  = C.ERROR
        progress_row.value = 0.0
        _finalizar_pipeline_ui()
        _notificar(f"Erro: {mensagem[:80]}", cor=C.ERROR, duracao=8000)

    def _set_sucesso(mensagem: str):
        status_text.value  = mensagem
        status_text.color  = C.SUCCESS
        progress_row.value = 1.0
        _finalizar_pipeline_ui()
        page.update()

    # ─────────────────────────────────────────────────────────────
    #  BOTÃO DE DOWNLOAD DE UM CLIPE
    # ─────────────────────────────────────────────────────────────

    def _btn_download_clipe(url: str, nome: str) -> ft.Control:
        """Botão de download individual para cada clipe gerado."""
        if not url:
            return ft.Container()

        def _baixar(e, u=url):
            page.launch_url(u)

        return ft.ElevatedButton(
            content=ft.Row(
                spacing=6, tight=True,
                controls=[
                    ft.Icon(ft.Icons.DOWNLOAD_FOR_OFFLINE_OUTLINED, size=14),
                    ft.Text(
                        f"Baixar {nome[:20]}{'…' if len(nome) > 20 else ''}",
                        size=12,
                        weight=ft.FontWeight.W_600,
                    ),
                ],
            ),
            on_click=_baixar,
            style=ft.ButtonStyle(
                bgcolor={
                    ft.ControlState.DEFAULT:  C.ACCENT,
                    ft.ControlState.HOVERED:  "#FF8C42",
                },
                color=C.BG,
                shape=ft.RoundedRectangleBorder(radius=6),
                padding=ft.Padding(10, 8, 10, 8),
                elevation=0,
            ),
        )

    # ─────────────────────────────────────────────────────────────
    #  POPULAR CARDS COM BOTÕES DE DOWNLOAD
    # ─────────────────────────────────────────────────────────────

    def _popular_cards(clips_api: list):
        if not clips_api:
            _set_erro("Nenhum clipe foi gerado. Verifique o vídeo e tente novamente.")
            return

        clipes = []
        for item in clips_api:
            clipe = ClipSugerido(
                id=item.get("index", len(clipes) + 1),
                titulo=Path(item["filename"]).stem.replace("_", " ").title(),
                inicio="--:--", fim="--:--",
                duracao=f"~{cfg['clip_duration']}s",
                score=item.get("score", 0.0),
                motivo=f"Clipe gerado. ({item.get('size_mb', 0):.1f} MB)",
                status="pronto", progresso=1.0,
            )
            clipe.__dict__["download_url"] = item.get("public_url", "")
            estado["clipes"][clipe.id] = clipe
            clipes.append(clipe)

        clips_column.controls.clear()
        clips_column.controls.append(ft.Row(
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                ft.Icon(ft.Icons.MOVIE_FILTER, color=C.ACCENT, size=16),
                ft.Text(
                    f"{len(clipes)} clipes gerados", size=14,
                    weight=ft.FontWeight.W_700, color=C.TEXT_PRIMARY,
                ),
                ft.Container(expand=True),
                tag(f"{len(clipes)} clipes", C.CYAN, C.CYAN_SOFT),
            ],
        ))

        for clipe in clipes:
            download_url = clipe.__dict__.get("download_url", "")
            nome_curto   = Path(
                clipe.titulo.replace(" ", "_").lower() + ".mp4"
            ).name

            # Card do clipe (componente existente)
            card_ctrl = clip_card(clipe, on_renderizar_clipe, on_preview_clipe)

            # Botão de download abaixo do card
            btn_dl = _btn_download_clipe(download_url, nome_curto)

            clips_column.controls.append(
                ft.Column(
                    spacing=4,
                    controls=[card_ctrl, btn_dl] if download_url else [card_ctrl],
                )
            )

        clips_column.visible = True
        _set_sucesso(f"✓ {len(clipes)} clipes prontos!")
        _notificar(
            f"✅ Concluído! {len(clipes)} clipes prontos para download.",
            cor=C.SUCCESS, duracao=8000,
        )

    # ─────────────────────────────────────────────────────────────
    #  SSE — recebe updates em tempo real
    # ─────────────────────────────────────────────────────────────

    def _aguardar_task(task_id: str):
        url = f"{API_BASE_URL}/api/status/{task_id}/stream"
        try:
            with httpx.Client(timeout=None, headers=_NGROK_HEADERS) as client:
                with client.stream("GET", url) as resp:
                    if resp.status_code == 404:
                        _set_erro(f"Tarefa {task_id} não encontrada.")
                        return
                    for linha in resp.iter_lines():
                        if not linha.startswith("data:"):
                            continue
                        raw = linha[len("data:"):].strip()
                        if not raw:
                            continue
                        try:
                            data = json.loads(raw)
                        except Exception:
                            continue

                        api_status = data.get("status", "pending")
                        atualizar_etapas(_STATUS_ETAPA.get(api_status, 0))
                        progress_row.value = float(data.get("progress", 0.0))
                        status_text.value  = data.get("message", "")
                        status_text.color  = (
                            C.ERROR if api_status == "error" else C.TEXT_SECONDARY
                        )
                        page.update()

                        if api_status == "done":
                            _popular_cards(data.get("clips", []))
                            return
                        if api_status == "error":
                            _set_erro(
                                data.get("error")
                                or data.get("message")
                                or "Erro desconhecido."
                            )
                            return

        except httpx.ConnectError:
            _set_erro(f"Não foi possível conectar à API em {API_BASE_URL}.")
        except Exception as exc:
            _set_erro(f"Erro no stream: {exc}")

    # ─────────────────────────────────────────────────────────────
    #  PIPELINES
    # ─────────────────────────────────────────────────────────────

    def _criar_job_api(source_type: str, source_url: str = None) -> str:
        user_id = _get_user_id()
        if not user_id:
            return str(uuid.uuid4())
        try:
            with httpx.Client(
                base_url=API_BASE_URL,
                timeout=httpx.Timeout(connect=10, read=15, write=10, pool=5),
                headers=_NGROK_HEADERS,
            ) as client:
                resp = client.post("/api/jobs", json={
                    "user_id":       user_id,
                    "source_type":   source_type,
                    "source_url":    source_url,
                    "num_clips":     cfg["num_clips"],
                    "clip_duration": cfg["clip_duration"],
                    "tracking":      cfg["tracking"],
                })
                if resp.status_code in (200, 201):
                    return resp.json().get("id", str(uuid.uuid4()))
        except Exception:
            pass
        return str(uuid.uuid4())

    def _pipeline_youtube(url: str):
        user_id = _get_user_id()
        if not user_id:
            _set_erro("Usuário não autenticado. Faça login novamente.")
            return
        try:
            job_id = _criar_job_api(source_type="youtube", source_url=url)
            with httpx.Client(
                base_url=API_BASE_URL,
                timeout=httpx.Timeout(connect=10, read=REQUEST_TIMEOUT, write=10, pool=5),
                headers=_NGROK_HEADERS,
            ) as client:
                resp = client.post("/api/video/process", json={
                    "url":           url,
                    "user_id":       user_id,
                    "job_id":        job_id,
                    "num_clips":     cfg["num_clips"],
                    "clip_duration": cfg["clip_duration"],
                    "tracking":      cfg["tracking"],
                    "subtitles":     cfg["subtitles"],
                    "source_type":   "youtube",
                    "cor_legenda":   cfg["legenda_cor"],
                    "formato":       cfg["formato"],
                })
                resp.raise_for_status()
                task_id = resp.json().get("task_id")

            if not task_id:
                _set_erro("API não retornou task_id.")
                return

            status_text.value = f"⏳ Processando... (job: {job_id[:8]})"
            status_text.color = C.TEXT_SECONDARY
            page.update()
            _notificar(
                "Processamento iniciado! Você pode usar outras abas.",
                cor=C.CYAN, duracao=5000,
            )
            _aguardar_task(task_id)

        except httpx.ConnectError:
            _set_erro(f"Não foi possível conectar à API em {API_BASE_URL}.")
        except httpx.HTTPStatusError as e:
            _set_erro(f"Erro {e.response.status_code}: {e.response.text[:200]}")
        except Exception as exc:
            _set_erro(str(exc))

    def _pipeline_local(nome_arquivo: str, conteudo, path_str):
        user_id = _get_user_id()
        if not user_id:
            _set_erro("Usuário não autenticado. Faça login novamente.")
            return
        try:
            if conteudo is None and path_str:
                src = Path(path_str)
                if not src.exists():
                    _set_erro(f"Arquivo não encontrado: {src.name}")
                    return
                conteudo = src.read_bytes()

            if not conteudo:
                _set_erro("Não foi possível ler o arquivo.")
                return

            status_text.value  = f"Enviando {nome_arquivo}..."
            progress_row.value = 0.05
            page.update()

            job_id = _criar_job_api(source_type="upload")
            upload_timeout = httpx.Timeout(connect=15, read=900, write=900, pool=10)

            with httpx.Client(base_url=API_BASE_URL, timeout=upload_timeout, headers=_NGROK_HEADERS) as client:
                resp = client.post(
                    "/api/video/upload",
                    files={"file": (nome_arquivo, io.BytesIO(conteudo), "video/mp4")},
                    data={
                        "user_id":       user_id,
                        "job_id":        job_id,
                        "num_clips":     str(cfg["num_clips"]),
                        "clip_duration": str(cfg["clip_duration"]),
                        "tracking":      str(cfg["tracking"]).lower(),
                        "subtitles":     str(cfg["subtitles"]).lower(),
                        "cor_legenda":   cfg["legenda_cor"],
                    },
                )
                resp.raise_for_status()
                task_id = resp.json().get("task_id")

            if not task_id:
                _set_erro("API não retornou task_id.")
                return

            status_text.value  = f"⏳ Upload concluído. Processando... (job: {job_id[:8]})"
            status_text.color  = C.TEXT_SECONDARY
            progress_row.value = 0.15
            page.update()
            _notificar(
                "Upload enviado! Você pode usar outras abas.",
                cor=C.CYAN, duracao=5000,
            )
            _aguardar_task(task_id)

        except httpx.ConnectError:
            _set_erro(f"Não foi possível conectar à API em {API_BASE_URL}.")
        except httpx.HTTPStatusError as e:
            _set_erro(f"Erro {e.response.status_code}: {e.response.text[:200]}")
        except Exception as exc:
            _set_erro(str(exc))

    # ─────────────────────────────────────────────────────────────
    #  HANDLERS DE ENTRADA
    # ─────────────────────────────────────────────────────────────

    def on_iniciar_download(e):
        url = url_field.value.strip()
        if not url:
            url_field.border_color = C.ERROR
            status_text.value      = "⚠ Insira uma URL válida do YouTube."
            status_text.color      = C.ERROR
            page.update()
            return
        if not _get_user_id():
            _set_erro("Sessão expirada. Faça login novamente.")
            return

        url_field.border_color = C.BORDER_ACCENT
        _iniciar_pipeline_ui()

        threading.Thread(
            target=_pipeline_youtube, args=(url,), daemon=True
        ).start()

    async def abrir_galeria_dispositivo(e):
        files = await ft.FilePicker().pick_files(
            dialog_title="Selecionar vídeo",
            allow_multiple=False,
            file_type=ft.FilePickerFileType.VIDEO,
        )
        if not files:
            status_text.value = "Seleção cancelada."
            status_text.color = C.TEXT_SECONDARY
            page.update()
            return

        arquivo  = files[0]
        nome     = arquivo.name or "video.mp4"
        conteudo = getattr(arquivo, "bytes", None)
        path_str = getattr(arquivo, "path",  None)

        if conteudo is None and path_str is None:
            _set_erro("Não foi possível ler o arquivo. Verifique as permissões.")
            return

        _iniciar_pipeline_ui()
        status_text.value = f"Preparando: {nome}"
        status_text.color = C.ACCENT
        page.update()

        threading.Thread(
            target=_pipeline_local,
            args=(nome, conteudo, path_str),
            daemon=True,
        ).start()

    # ─────────────────────────────────────────────────────────────
    #  HANDLERS DE CLIPE
    # ─────────────────────────────────────────────────────────────

    def on_renderizar_clipe(clipe: ClipSugerido):
        pass

    def _fechar_dlg(dlg):
        dlg.open = False
        page.update()

    def on_preview_clipe(clipe: ClipSugerido):
        download_url = clipe.__dict__.get("download_url", "")
        dlg = ft.AlertDialog(
            title=ft.Text(
                clipe.titulo, color=C.TEXT_PRIMARY, weight=ft.FontWeight.W_700,
            ),
            content=ft.Column(
                spacing=8, tight=True,
                controls=[
                    ft.Row(
                        spacing=8,
                        controls=[
                            tag(f"⏱ {clipe.inicio} → {clipe.fim}", C.CYAN, C.CYAN_SOFT),
                            tag(
                                f"Score: {int(clipe.score * 100)}%",
                                C.SUCCESS if clipe.score >= 0.75 else C.WARNING,
                                C.SUCCESS_SOFT if clipe.score >= 0.75 else C.WARNING_SOFT,
                            ),
                        ],
                    ),
                    ft.Container(height=4),
                    ft.Text(clipe.motivo, size=13, color=C.TEXT_PRIMARY),
                    ft.Container(
                        border_radius=6,
                        bgcolor=C.CYAN_SOFT,
                        border=ft.Border(
                            left=ft.BorderSide(1, C.CYAN + "33"),
                            right=ft.BorderSide(1, C.CYAN + "33"),
                            top=ft.BorderSide(1, C.CYAN + "33"),
                            bottom=ft.BorderSide(1, C.CYAN + "33"),
                        ),
                        padding=ft.Padding(10, 10, 10, 10),
                        content=ft.Row(
                            spacing=8,
                            controls=[
                                ft.Icon(ft.Icons.CLOUD_DOWNLOAD_OUTLINED,
                                        color=C.CYAN, size=14),
                                ft.Text("Clipe salvo na nuvem.",
                                        size=12, color=C.TEXT_SECONDARY),
                            ],
                        ),
                    ),
                ],
            ),
            bgcolor=C.SURFACE,
            shape=ft.RoundedRectangleBorder(radius=12),
            actions=[
                ft.TextButton(
                    "Fechar",
                    on_click=lambda e: _fechar_dlg(dlg),
                    style=ft.ButtonStyle(color=C.TEXT_SECONDARY),
                ),
                ft.FilledButton(
                    "Baixar clipe",
                    icon=ft.Icons.DOWNLOAD,
                    on_click=lambda e: page.launch_url(download_url) if download_url else None,
                    disabled=not bool(download_url),
                    style=ft.ButtonStyle(
                        bgcolor=C.ACCENT, color=C.BG,
                        shape=ft.RoundedRectangleBorder(radius=6),
                    ),
                ),
            ],
        )
        page.dialog = dlg
        dlg.open    = True
        page.update()

    # ─────────────────────────────────────────────────────────────
    #  BOTÕES PRINCIPAIS
    # ─────────────────────────────────────────────────────────────

    _btn_style = ft.ButtonStyle(
        color=C.BG,
        bgcolor={
            ft.ControlState.DEFAULT:  C.ACCENT,
            ft.ControlState.HOVERED:  "#FF8C42",
            ft.ControlState.DISABLED: C.BORDER,
        },
        shape=ft.RoundedRectangleBorder(radius=8),
        padding=ft.Padding(20, 14, 20, 14),
        text_style=ft.TextStyle(weight=ft.FontWeight.W_700, size=14),
        elevation=0,
    )

    btn_download = ft.FilledButton(
        content=ft.Row(
            spacing=8, tight=True,
            controls=[
                ft.Icon(ft.Icons.ROCKET_LAUNCH_OUTLINED, size=16),
                ft.Text("Analisar e Baixar", weight=ft.FontWeight.W_700, size=14),
            ],
        ),
        on_click=on_iniciar_download,
        style=_btn_style,
    )

    btn_gallery = ft.FilledButton(
        content=ft.Row(
            spacing=8, tight=True,
            controls=[
                ft.Icon(ft.Icons.VIDEO_LIBRARY_OUTLINED, size=16),
                ft.Text("Da galeria", weight=ft.FontWeight.W_700, size=14),
            ],
        ),
        on_click=abrir_galeria_dispositivo,
        style=_btn_style,
    )

    # ─────────────────────────────────────────────────────────────
    #  CARD DE DEMONSTRAÇÃO
    # ─────────────────────────────────────────────────────────────

    demo_card = _build_demo_card(page)

    # ─────────────────────────────────────────────────────────────
    #  LAYOUT FINAL
    # ─────────────────────────────────────────────────────────────

    return ft.Column(
        spacing=10,
        scroll=ft.ScrollMode.AUTO,
        expand=True,
        controls=[
            # ── Header ──────────────────────────────────────────
            ft.Row(
                spacing=10,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    ft.Icon(ft.Icons.ADD_CIRCLE_OUTLINE, color=C.ACCENT, size=20),
                    ft.Column(
                        spacing=2,
                        controls=[
                            ft.Text("Novo Projeto", size=20,
                                    weight=ft.FontWeight.W_800, color=C.TEXT_PRIMARY),
                            ft.Text("Cole a URL do YouTube ou envie um vídeo.",
                                    size=12, color=C.TEXT_SECONDARY),
                        ],
                    ),
                ],
            ),

            # ── Demo card ───────────────────────────────────────
            demo_card,

            # ── Configurações ───────────────────────────────────
            painel_config,

            # ── URL + botões ────────────────────────────────────
            ft.Container(
                border_radius=10, bgcolor=C.SURFACE,
                border=_borda(),
                padding=ft.Padding(16, 14, 16, 14),
                content=ft.Column(
                    spacing=10,
                    controls=[
                        ft.Text("URL do Vídeo", size=12,
                                weight=ft.FontWeight.W_600, color=C.TEXT_SECONDARY),
                        url_field,
                        ft.Row(
                            spacing=8,
                            controls=[btn_gallery, btn_download],
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        ),
                    ],
                ),
            ),

            # ── Aviso de segurança (não feche o app) ────────────
            aviso_nao_feche,

            # ── Pipeline ────────────────────────────────────────
            ft.Container(
                border_radius=10, bgcolor=C.SURFACE,
                border=_borda(),
                padding=ft.Padding(16, 14, 16, 14),
                content=ft.Column(
                    spacing=8,
                    controls=[
                        ft.Row(
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            controls=[
                                ft.Text("Pipeline de processamento", size=12,
                                        weight=ft.FontWeight.W_600,
                                        color=C.TEXT_SECONDARY),
                                ft.Container(expand=True),
                                status_text,
                            ],
                        ),
                        progress_row,
                        ft.Container(height=2),
                        etapas_column,
                    ],
                ),
            ),

            ft.Container(height=4),

            # ── Clipes gerados com botões de download ───────────
            clips_column,
        ],
    )
