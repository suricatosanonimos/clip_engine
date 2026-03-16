"""
Aba 2 — Processamento.
Busca jobs reais do usuário via GET /api/jobs e exibe
métricas + status de cada projeto em tempo real.
Compatível com Flet 0.82.
"""

import threading
from datetime import datetime

import flet as ft
import httpx

# ── ngrok: evita página de aviso do browser ──────────────────────
_NGROK_HEADERS = {"ngrok-skip-browser-warning": "true"}


from src.views.components import divider, status_chip, tag
from src.views.theme import C

API_BASE_URL    = "https://perceptible-westin-checkable.ngrok-free.dev"
REQUEST_TIMEOUT = 15.0

# Mapeamento de status da API → label legível
_STATUS_LABEL = {
    "pending":      "Aguardando",
    "downloading":  "Baixando",
    "processing":   "Processando",
    "transcribing": "Transcrevendo",
    "analyzing":    "Analisando",
    "done":         "Pronto",
    "error":        "Erro",
}

# Mapeamento de status → cor
_STATUS_COR = {
    "pending":      C.TEXT_MUTED,
    "downloading":  C.CYAN,
    "processing":   C.ACCENT,
    "transcribing": C.ACCENT,
    "analyzing":    C.WARNING,
    "done":         C.SUCCESS,
    "error":        C.ERROR,
}

# Mapeamento de status → ícone
_STATUS_ICONE = {
    "pending":      ft.Icons.HOURGLASS_EMPTY,
    "downloading":  ft.Icons.DOWNLOAD_OUTLINED,
    "processing":   ft.Icons.GRAPHIC_EQ,
    "transcribing": ft.Icons.CLOSED_CAPTION_OUTLINED,
    "analyzing":    ft.Icons.PSYCHOLOGY_OUTLINED,
    "done":         ft.Icons.CHECK_CIRCLE_OUTLINE,
    "error":        ft.Icons.ERROR_OUTLINE,
}


def build_aba_processamento(estado: dict, page: ft.Page) -> ft.Control:

    def _get_user_id() -> str:
        return (estado.get("user_info") or {}).get("id", "")

    _state = {
        "jobs":   [],
        "carregando": False,
    }

    # ── Controles ────────────────────────────────────────────────
    loading_ring = ft.ProgressRing(
        width=18, height=18, stroke_width=2,
        color=C.ACCENT, visible=False,
    )
    status_geral = ft.Text("", size=11, color=C.TEXT_SECONDARY)
    jobs_column  = ft.Column(spacing=8)

    # Métricas dinâmicas
    _metricas_refs = {
        "ativos":    ft.Text("0", size=24, weight=ft.FontWeight.W_900,
                             color=C.ACCENT, font_family="monospace"),
        "concluidos": ft.Text("0", size=24, weight=ft.FontWeight.W_900,
                              color=C.SUCCESS, font_family="monospace"),
        "clipes":    ft.Text("0", size=24, weight=ft.FontWeight.W_900,
                             color=C.CYAN, font_family="monospace"),
        "erros":     ft.Text("0", size=24, weight=ft.FontWeight.W_900,
                             color=C.ERROR, font_family="monospace"),
    }

    # ── Helpers ──────────────────────────────────────────────────

    def _formatar_data(iso_str: str) -> str:
        try:
            dt   = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
            hoje = datetime.now().date()
            if dt.date() == hoje:
                return f"Hoje, {dt.strftime('%H:%M')}"
            elif (hoje - dt.date()).days == 1:
                return f"Ontem, {dt.strftime('%H:%M')}"
            return dt.strftime("%d/%m/%y %H:%M")
        except Exception:
            return iso_str[:10] if iso_str else "—"

    def _titulo_job(job: dict) -> str:
        titulo = job.get("video_title") or job.get("source_url") or ""
        if not titulo:
            src = job.get("source_type", "upload")
            titulo = f"Upload ({src})"
        if len(titulo) > 46:
            titulo = titulo[:46] + "…"
        return titulo

    def _progresso_real(job: dict) -> float:
        """Banco guarda progress em 0–100; normaliza para 0.0–1.0."""
        p = job.get("progress", 0)
        try:
            p = float(p)
            return p / 100.0 if p > 1.0 else p
        except Exception:
            return 0.0

    # ── Card de job ──────────────────────────────────────────────

    def _job_card(job: dict) -> ft.Container:
        st        = job.get("status", "pending")
        cor       = _STATUS_COR.get(st, C.TEXT_MUTED)
        icone     = _STATUS_ICONE.get(st, ft.Icons.PENDING_OUTLINED)
        label_st  = _STATUS_LABEL.get(st, st.title())
        progresso = _progresso_real(job)
        titulo    = _titulo_job(job)
        data_fmt  = _formatar_data(job.get("created_at", ""))
        num_clips = job.get("num_clips", 1)
        duracao   = f"{job.get('clip_duration', 60)}s"
        src_type  = job.get("source_type", "upload")
        mensagem  = job.get("message", "")

        # Ícone de fonte
        src_icone = (
            ft.Icons.SMART_DISPLAY_OUTLINED
            if src_type == "youtube"
            else ft.Icons.UPLOAD_FILE_OUTLINED
        )

        # Indicador animado se ativo
        if st not in ("done", "error", "pending"):
            indicador = ft.ProgressRing(
                width=14, height=14, stroke_width=2, color=cor,
            )
        elif st == "done":
            indicador = ft.Icon(ft.Icons.CHECK_CIRCLE, color=cor, size=16)
        elif st == "error":
            indicador = ft.Icon(ft.Icons.CANCEL, color=cor, size=16)
        else:
            indicador = ft.Icon(icone, color=cor, size=16)

        return ft.Container(
            border_radius=10,
            bgcolor=C.SURFACE,
            border=ft.Border(
                left=ft.BorderSide(2, cor),          # borda esquerda colorida por status
                right=ft.BorderSide(1, C.BORDER),
                top=ft.BorderSide(1, C.BORDER),
                bottom=ft.BorderSide(1, C.BORDER),
            ),
            padding=ft.Padding(left=14, right=14, top=12, bottom=12),
            content=ft.Column(
                spacing=8,
                controls=[
                    # ── Linha 1: ícone + título + badge status ──────
                    ft.Row(
                        spacing=10,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        controls=[
                            ft.Container(
                                width=34, height=34,
                                border_radius=8,
                                bgcolor=C.ACCENT_SOFT,
                                alignment=ft.Alignment(0, 0),
                                content=ft.Icon(src_icone, color=C.ACCENT, size=17),
                            ),
                            ft.Column(
                                spacing=2, expand=True,
                                controls=[
                                    ft.Text(
                                        titulo, size=13,
                                        weight=ft.FontWeight.W_600,
                                        color=C.TEXT_PRIMARY,
                                        max_lines=1,
                                        overflow=ft.TextOverflow.ELLIPSIS,
                                    ),
                                    ft.Row(
                                        spacing=6,
                                        controls=[
                                            ft.Text(
                                                data_fmt, size=10,
                                                color=C.TEXT_MUTED,
                                                font_family="monospace",
                                            ),
                                            tag(f"{num_clips} clipes", C.CYAN, C.CYAN_SOFT),
                                            tag(duracao, C.TEXT_SECONDARY, C.SURFACE_2),
                                        ],
                                    ),
                                ],
                            ),
                            # Badge de status
                            ft.Container(
                                border_radius=6,
                                bgcolor=cor + "22",
                                padding=ft.Padding(left=8, right=8, top=4, bottom=4),
                                content=ft.Row(
                                    spacing=4,
                                    tight=True,
                                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                    controls=[
                                        indicador,
                                        ft.Text(
                                            label_st, size=10,
                                            color=cor,
                                            weight=ft.FontWeight.W_700,
                                        ),
                                    ],
                                ),
                            ),
                        ],
                    ),

                    # ── Linha 2: barra de progresso ─────────────────
                    ft.Column(
                        spacing=4,
                        controls=[
                            ft.ProgressBar(
                                value=progresso,
                                color=cor,
                                bgcolor=C.BORDER,
                                height=4,
                                border_radius=4,
                            ),
                            ft.Row(
                                controls=[
                                    ft.Text(
                                        f"{int(progresso * 100)}%",
                                        size=10,
                                        color=cor,
                                        font_family="monospace",
                                        weight=ft.FontWeight.W_600,
                                    ),
                                    ft.Container(expand=True),
                                    ft.Text(
                                        mensagem[:48] + ("…" if len(mensagem) > 48 else "")
                                        if mensagem else "",
                                        size=10,
                                        color=C.TEXT_MUTED,
                                        italic=True,
                                    ),
                                ],
                            ),
                        ],
                    ),
                ],
            ),
        )

    # ── Atualizar métricas ───────────────────────────────────────

    def _atualizar_metricas(jobs: list):
        ativos    = len([j for j in jobs if j.get("status") not in ("done", "error")])
        concluidos = len([j for j in jobs if j.get("status") == "done"])
        erros     = len([j for j in jobs if j.get("status") == "error"])
        # Soma de num_clips dos jobs concluídos
        clipes    = sum(j.get("num_clips", 0) for j in jobs if j.get("status") == "done")

        _metricas_refs["ativos"].value     = str(ativos)
        _metricas_refs["concluidos"].value = str(concluidos)
        _metricas_refs["clipes"].value     = str(clipes)
        _metricas_refs["erros"].value      = str(erros)

    # ── Buscar jobs da API ───────────────────────────────────────

    def _buscar_jobs():
        user_id = _get_user_id()
        if not user_id:
            status_geral.value    = "Faça login para ver seus projetos."
            status_geral.color    = C.TEXT_MUTED
            loading_ring.visible  = False
            page.update()
            return

        try:
            with httpx.Client(base_url=API_BASE_URL, timeout=REQUEST_TIMEOUT, headers=_NGROK_HEADERS) as client:
                r = client.get("/api/jobs", params={
                    "user_id": user_id,
                    "limit":   50,
                    "offset":  0,
                })
                r.raise_for_status()
                _state["jobs"] = r.json()

        except httpx.ConnectError:
            status_geral.value   = f"Sem conexão com a API."
            status_geral.color   = C.ERROR
            loading_ring.visible = False
            page.update()
            return
        except Exception as e:
            status_geral.value   = f"Erro: {str(e)[:60]}"
            status_geral.color   = C.ERROR
            loading_ring.visible = False
            page.update()
            return

        jobs = _state["jobs"]
        _atualizar_metricas(jobs)

        if jobs:
            jobs_column.controls = [_job_card(j) for j in jobs]
            status_geral.value   = f"Última atualização: {datetime.now().strftime('%H:%M:%S')}"
            status_geral.color   = C.TEXT_MUTED
        else:
            jobs_column.controls = [
                ft.Container(
                    padding=ft.Padding(left=0, right=0, top=24, bottom=24),
                    alignment=ft.Alignment(0, 0),
                    content=ft.Column(
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=8,
                        controls=[
                            ft.Icon(ft.Icons.INBOX_OUTLINED,
                                    color=C.TEXT_MUTED, size=40),
                            ft.Text(
                                "Nenhum projeto ainda.",
                                size=14, color=C.TEXT_MUTED,
                            ),
                            ft.Text(
                                "Crie um novo projeto na aba Novo.",
                                size=12, color=C.TEXT_MUTED,
                            ),
                        ],
                    ),
                )
            ]
            status_geral.value = ""

        loading_ring.visible = False
        page.update()

    def _recarregar(e=None):
        loading_ring.visible = True
        status_geral.value   = "Atualizando..."
        status_geral.color   = C.TEXT_SECONDARY
        page.update()
        threading.Thread(target=_buscar_jobs, daemon=True).start()

    _recarregar()

    # ── Cards de métrica ─────────────────────────────────────────

    def _metrica_card(label: str, valor_ref: ft.Text,
                      icone, cor: str) -> ft.Container:
        return ft.Container(
            expand=True,
            border_radius=10,
            bgcolor=C.SURFACE,
            border=ft.Border(
                left=ft.BorderSide(1, C.BORDER),
                right=ft.BorderSide(1, C.BORDER),
                top=ft.BorderSide(1, C.BORDER),
                bottom=ft.BorderSide(1, C.BORDER),
            ),
            padding=ft.padding.all(12),
            content=ft.Column(
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=4,
                controls=[
                    ft.Icon(icone, color=cor, size=20),
                    valor_ref,
                    ft.Text(label, size=10, color=C.TEXT_SECONDARY,
                            text_align=ft.TextAlign.CENTER),
                ],
            ),
        )

    # ── Layout ────────────────────────────────────────────────────

    return ft.Column(
        spacing=8,
        scroll=ft.ScrollMode.AUTO,
        expand=True,
        controls=[
            # Header
            ft.Row(
                spacing=10,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    ft.Icon(ft.Icons.SETTINGS_OUTLINED, color=C.ACCENT, size=20),
                    ft.Text(
                        "Processamento",
                        size=20, weight=ft.FontWeight.W_800,
                        color=C.TEXT_PRIMARY,
                    ),
                    ft.Container(expand=True),
                    loading_ring,
                    ft.IconButton(
                        icon=ft.Icons.REFRESH,
                        icon_color=C.TEXT_SECONDARY,
                        icon_size=18,
                        tooltip="Atualizar",
                        on_click=_recarregar,
                        style=ft.ButtonStyle(
                            bgcolor={ft.ControlState.HOVERED: C.SURFACE_2},
                            shape=ft.RoundedRectangleBorder(radius=8),
                        ),
                    ),
                ],
            ),
            ft.Row(
                controls=[
                    ft.Text(
                        "Histórico e status dos seus projetos.",
                        size=13, color=C.TEXT_SECONDARY, expand=True,
                    ),
                    status_geral,
                ],
            ),

            ft.Container(height=4),

            # Métricas
            ft.Row(
                spacing=8,
                controls=[
                    _metrica_card(
                        "Em andamento",
                        _metricas_refs["ativos"],
                        ft.Icons.PENDING_OUTLINED,
                        C.ACCENT,
                    ),
                    _metrica_card(
                        "Concluídos",
                        _metricas_refs["concluidos"],
                        ft.Icons.CHECK_CIRCLE_OUTLINE,
                        C.SUCCESS,
                    ),
                    _metrica_card(
                        "Clipes gerados",
                        _metricas_refs["clipes"],
                        ft.Icons.MOVIE_FILTER_OUTLINED,
                        C.CYAN,
                    ),
                    _metrica_card(
                        "Com erro",
                        _metricas_refs["erros"],
                        ft.Icons.ERROR_OUTLINE,
                        C.ERROR,
                    ),
                ],
            ),

            ft.Container(height=4),
            divider(),

            # Título da lista
            ft.Row(
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    ft.Text(
                        "Projetos",
                        size=14, weight=ft.FontWeight.W_700,
                        color=C.TEXT_PRIMARY,
                    ),
                ],
            ),

            # Lista de jobs
            jobs_column,
        ],
    )
