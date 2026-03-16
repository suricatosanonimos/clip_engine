"""
Aba 3 — Galeria (cloud).
Busca os clipes do usuário via GET /api/clips e permite download
direto no dispositivo via signed URL do Supabase Storage.

Download:
  • Android/iOS → baixa bytes via httpx + FilePicker.save_file()
  • Desktop/Web  → page.launch_url() abre no browser
Compatível com Flet 0.82.
"""

import threading
from datetime import datetime
from pathlib import Path

import flet as ft
import httpx

# ── ngrok: evita página de aviso do browser ──────────────────────
_NGROK_HEADERS = {"ngrok-skip-browser-warning": "true"}


from src.views.theme import C

API_BASE_URL    = "https://perceptible-westin-checkable.ngrok-free.dev"
REQUEST_TIMEOUT  = 15.0
DOWNLOAD_TIMEOUT = httpx.Timeout(connect=15, read=300, write=60, pool=10)

_PLATAFORMAS_MOBILE = {
    ft.PagePlatform.ANDROID,
    ft.PagePlatform.IOS,
}


def build_aba_galeria(estado: dict, page: ft.Page) -> ft.Control:

    def _get_user_id() -> str:
        return (estado.get("user_info") or {}).get("id", "")

    def _is_mobile() -> bool:
        try:
            return page.platform in _PLATAFORMAS_MOBILE
        except Exception:
            return False

    _state = {
        "clipes":       [],
        "busca":        "",
        "baixando_ids": set(),
    }

    # ── Controles ────────────────────────────────────────────────
    grid = ft.GridView(
        runs_count=2,
        max_extent=220,
        child_aspect_ratio=0.78,
        spacing=10,
        run_spacing=10,
        expand=True,
    )
    contador_txt = ft.Text(
        "0 clipes", size=12,
        color=C.ACCENT, weight=ft.FontWeight.W_700,
    )
    status_txt = ft.Text("Carregando...", size=12, color=C.TEXT_SECONDARY)
    campo_busca = ft.TextField(
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
        content_padding=ft.Padding(left=12, right=12, top=8, bottom=8),
    )
    loading_ring = ft.ProgressRing(
        width=20, height=20, stroke_width=2,
        color=C.ACCENT, visible=False,
    )

    # ── Notificação ──────────────────────────────────────────────

    def _notificar(msg: str, cor: str = C.SUCCESS):
        icone = ft.Icons.CHECK_CIRCLE if cor == C.SUCCESS else (
            ft.Icons.INFO if cor == C.CYAN else ft.Icons.ERROR
        )
        page.snack_bar = ft.SnackBar(
            content=ft.Row(spacing=10, controls=[
                ft.Icon(icone, color=cor, size=18),
                ft.Text(msg, color=C.TEXT_PRIMARY, size=13, expand=True),
            ]),
            bgcolor=C.SURFACE_2,
            duration=5000,
            show_close_icon=True,
            close_icon_color=C.TEXT_SECONDARY,
        )
        page.snack_bar.open = True
        page.update()

    # ── Helpers de data ──────────────────────────────────────────

    def _formatar_data(iso_str: str) -> str:
        try:
            dt   = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
            hoje = datetime.now().date()
            if dt.date() == hoje:
                return f"Hoje, {dt.strftime('%H:%M')}"
            elif (hoje - dt.date()).days == 1:
                return f"Ontem, {dt.strftime('%H:%M')}"
            return dt.strftime("%d/%m, %H:%M")
        except Exception:
            return iso_str[:10] if iso_str else "—"

    # ── Obter URL válida ─────────────────────────────────────────

    def _obter_url(clip_id: str, public_url: str) -> str:
        if public_url:
            return public_url
        try:
            with httpx.Client(base_url=API_BASE_URL, timeout=REQUEST_TIMEOUT, headers=_NGROK_HEADERS) as client:
                r = client.post(f"/api/clips/{clip_id}/refresh-url")
                if r.status_code == 200:
                    return r.json().get("public_url", "")
        except Exception:
            pass
        return ""

    # ── Download mobile ──────────────────────────────────────────

    def _download_mobile(url: str, filename: str, clip_id: str, btn_txt: ft.Text, btn: ft.ElevatedButton):
        try:
            _notificar(f"Baixando {filename}...", cor=C.CYAN)

            with httpx.Client(timeout=DOWNLOAD_TIMEOUT, follow_redirects=True, headers=_NGROK_HEADERS) as client:
                resp = client.get(url)
                resp.raise_for_status()
                conteudo = resp.content

            import tempfile
            tmp = Path(tempfile.gettempdir()) / filename
            tmp.write_bytes(conteudo)

            fp = ft.FilePicker()

            def on_save(e: ft.FilePickerResultEvent):
                if e.path:
                    try:
                        Path(e.path).write_bytes(conteudo)
                        _notificar(f"✅ Salvo: {Path(e.path).name}")
                    except Exception as ex:
                        _notificar(f"Erro ao salvar: {ex}", cor=C.ERROR)
                else:
                    _notificar("Download cancelado.", cor=C.TEXT_SECONDARY)
                try:
                    page.overlay.remove(fp)
                except Exception:
                    pass
                _state["baixando_ids"].discard(clip_id)
                btn.disabled  = False
                btn_txt.value = "Baixar"
                page.update()

            fp.on_result = on_save
            page.overlay.append(fp)
            page.update()
            fp.save_file(
                dialog_title="Salvar clipe",
                file_name=filename,
                allowed_extensions=["mp4", "mov", "mkv"],
            )

        except httpx.HTTPStatusError as e:
            _notificar(f"Erro HTTP {e.response.status_code}.", cor=C.ERROR)
            _state["baixando_ids"].discard(clip_id)
            btn.disabled  = False
            btn_txt.value = "Baixar"
            page.update()
        except Exception as e:
            _notificar(f"Erro: {str(e)[:60]}", cor=C.ERROR)
            _state["baixando_ids"].discard(clip_id)
            btn.disabled  = False
            btn_txt.value = "Baixar"
            page.update()

    # ── Card de clipe ─────────────────────────────────────────────

    def _galeria_card(item: dict) -> ft.Container:
        nome       = item.get("filename", "clip.mp4")
        titulo     = nome.replace("final_", "").replace("_", " ").rsplit(".", 1)[0].title()
        if len(titulo) > 36:
            titulo = titulo[:36] + "…"

        size_mb    = item.get("size_mb") or 0.0
        data_fmt   = _formatar_data(item.get("created_at", ""))
        public_url = item.get("public_url", "")
        clip_id    = item.get("id", "")
        filename   = nome

        # Controles mutáveis do botão
        btn_icon = ft.Icon(ft.Icons.DOWNLOAD_FOR_OFFLINE_OUTLINED, size=13)
        btn_txt  = ft.Text("Baixar", size=11, weight=ft.FontWeight.W_700)
        btn      = ft.ElevatedButton(
            content=ft.Row(
                spacing=4, tight=True,
                alignment=ft.MainAxisAlignment.CENTER,
                controls=[btn_icon, btn_txt],
            ),
            style=ft.ButtonStyle(
                bgcolor={
                    ft.ControlState.DEFAULT:  C.ACCENT,
                    ft.ControlState.HOVERED:  "#FF8C42",
                    ft.ControlState.DISABLED: C.BORDER,
                },
                color=C.BG,
                shape=ft.RoundedRectangleBorder(radius=6),
                padding=ft.Padding(0, 6, 0, 6),
                elevation=0,
            ),
            disabled=not bool(public_url or clip_id),
            expand=True,
        )

        def _baixar(e):
            if clip_id in _state["baixando_ids"]:
                return
            _state["baixando_ids"].add(clip_id)
            btn.disabled  = True
            btn_txt.value = "…"
            page.update()

            def _executar():
                url = _obter_url(clip_id, public_url)
                if not url:
                    _notificar("URL de download não disponível.", cor=C.ERROR)
                    _state["baixando_ids"].discard(clip_id)
                    btn.disabled  = False
                    btn_txt.value = "Baixar"
                    page.update()
                    return

                if _is_mobile():
                    _download_mobile(url, filename, clip_id, btn_txt, btn)
                else:
                    page.launch_url(url)
                    _notificar("✅ Download iniciado no browser.")
                    _state["baixando_ids"].discard(clip_id)
                    btn.disabled  = False
                    btn_txt.value = "Baixar"
                    page.update()

            threading.Thread(target=_executar, daemon=True).start()

        btn.on_click = _baixar

        return ft.Container(
            border_radius=8,
            bgcolor=C.SURFACE,
            border=ft.Border(
                left=ft.BorderSide(1, C.BORDER_ACCENT),
                right=ft.BorderSide(1, C.BORDER_ACCENT),
                top=ft.BorderSide(1, C.BORDER_ACCENT),
                bottom=ft.BorderSide(1, C.BORDER_ACCENT),
            ),
            clip_behavior=ft.ClipBehavior.HARD_EDGE,
            content=ft.Column(
                spacing=0,
                controls=[
                    # Thumbnail
                    ft.Container(
                        height=100,
                        border_radius=ft.BorderRadius(
                            top_left=8, top_right=8,
                            bottom_left=0, bottom_right=0,
                        ),
                        clip_behavior=ft.ClipBehavior.HARD_EDGE,
                        on_click=_baixar,
                        content=ft.Stack(
                            controls=[
                                ft.Container(
                                    expand=True,
                                    gradient=ft.LinearGradient(
                                        colors=[C.SURFACE_2, "#1A1A28"],
                                        begin=ft.Alignment(-1, -1),
                                        end=ft.Alignment(1, 1),
                                    ),
                                ),
                                ft.Container(
                                    expand=True,
                                    alignment=ft.Alignment(0, 0),
                                    content=ft.Icon(
                                        ft.Icons.PLAY_CIRCLE_FILL_OUTLINED,
                                        color=C.ACCENT + "CC",
                                        size=44,
                                    ),
                                ),
                                ft.Container(
                                    top=6, left=6,
                                    border_radius=4,
                                    bgcolor=C.BG + "CC",
                                    padding=ft.Padding(left=5, right=5, top=2, bottom=2),
                                    content=ft.Text(
                                        "☁ CLOUD", size=9,
                                        weight=ft.FontWeight.W_800,
                                        color=C.CYAN, font_family="monospace",
                                    ),
                                ),
                                ft.Container(
                                    bottom=6, left=6,
                                    border_radius=4,
                                    bgcolor=C.BG + "CC",
                                    padding=ft.Padding(left=6, right=6, top=3, bottom=3),
                                    content=ft.Text(
                                        f"{size_mb:.1f} MB", size=10,
                                        color=C.TEXT_PRIMARY, font_family="monospace",
                                    ),
                                ),
                            ],
                        ),
                    ),
                    # Info
                    ft.Container(
                        padding=ft.Padding(left=10, right=10, top=8, bottom=8),
                        content=ft.Column(
                            spacing=6,
                            controls=[
                                ft.Text(
                                    titulo, size=11,
                                    weight=ft.FontWeight.W_600,
                                    color=C.TEXT_PRIMARY,
                                    max_lines=2,
                                    overflow=ft.TextOverflow.ELLIPSIS,
                                ),
                                ft.Text(data_fmt, size=10, color=C.TEXT_MUTED),
                                btn,
                            ],
                        ),
                    ),
                ],
            ),
        )

    # ── Renderizar ────────────────────────────────────────────────

    def _renderizar(busca: str = ""):
        busca     = busca.lower().strip()
        clipes    = _state["clipes"]
        filtrados = (
            [c for c in clipes if busca in c.get("filename", "").lower()]
            if busca else clipes
        )
        grid.controls      = [_galeria_card(c) for c in filtrados]
        total              = len(clipes)
        visiveis           = len(filtrados)
        contador_txt.value = (
            f"{total} clipes" if not busca
            else f"{visiveis}/{total} clipes"
        )
        status_txt.value = "" if filtrados else (
            "Nenhum clipe encontrado." if busca
            else "Nenhum clipe gerado ainda. Crie um novo projeto!"
        )
        status_txt.color = C.TEXT_MUTED
        page.update()

    # ── Buscar da API ────────────────────────────────────────────

    def _buscar_clipes_api():
        user_id = _get_user_id()
        if not user_id:
            status_txt.value     = "Faça login para ver seus clipes."
            status_txt.color     = C.TEXT_MUTED
            loading_ring.visible = False
            page.update()
            return
        try:
            with httpx.Client(base_url=API_BASE_URL, timeout=REQUEST_TIMEOUT, headers=_NGROK_HEADERS) as client:
                r = client.get("/api/clips/", params={
                    "user_id": user_id,
                    "limit":   100,
                    "offset":  0,
                })
                r.raise_for_status()
                _state["clipes"] = r.json()
        except httpx.ConnectError:
            status_txt.value     = "Sem conexão com a API."
            status_txt.color     = C.ERROR
            loading_ring.visible = False
            page.update()
            return
        except Exception as e:
            status_txt.value     = f"Erro: {str(e)[:60]}"
            status_txt.color     = C.ERROR
            loading_ring.visible = False
            page.update()
            return

        loading_ring.visible = False
        _renderizar(_state["busca"])

    def _recarregar(e=None):
        loading_ring.visible = True
        status_txt.value     = "Buscando clipes..."
        status_txt.color     = C.TEXT_SECONDARY
        grid.controls        = []
        page.update()
        threading.Thread(target=_buscar_clipes_api, daemon=True).start()

    def on_busca(e):
        _state["busca"] = e.control.value or ""
        _renderizar(_state["busca"])

    campo_busca.on_change = on_busca
    _recarregar()

    # ── Layout ────────────────────────────────────────────────────

    return ft.Column(
        spacing=8,
        expand=True,
        controls=[
            ft.Row(
                spacing=8,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    ft.Icon(ft.Icons.VIDEO_LIBRARY_OUTLINED, color=C.ACCENT, size=20),
                    ft.Text("Galeria", size=20,
                            weight=ft.FontWeight.W_800, color=C.TEXT_PRIMARY),
                    ft.Container(expand=True),
                    loading_ring,
                    ft.Container(
                        border_radius=20,
                        bgcolor=C.ACCENT_SOFT,
                        border=ft.Border(
                            left=ft.BorderSide(1, C.ACCENT + "44"),
                            right=ft.BorderSide(1, C.ACCENT + "44"),
                            top=ft.BorderSide(1, C.ACCENT + "44"),
                            bottom=ft.BorderSide(1, C.ACCENT + "44"),
                        ),
                        padding=ft.Padding(left=10, right=10, top=4, bottom=4),
                        content=contador_txt,
                    ),
                    ft.IconButton(
                        icon=ft.Icons.REFRESH,
                        icon_color=C.TEXT_SECONDARY,
                        icon_size=18,
                        tooltip="Atualizar galeria",
                        on_click=_recarregar,
                        style=ft.ButtonStyle(
                            bgcolor={ft.ControlState.HOVERED: C.SURFACE_2},
                            shape=ft.RoundedRectangleBorder(radius=8),
                        ),
                    ),
                ],
            ),
            ft.Row(controls=[
                ft.Text(
                    "Seus clipes gerados e salvos na nuvem.",
                    size=13, color=C.TEXT_SECONDARY, expand=True,
                ),
                status_txt,
            ]),
            ft.Container(height=2),
            ft.Row(spacing=8,
                   vertical_alignment=ft.CrossAxisAlignment.CENTER,
                   controls=[campo_busca]),
            ft.Container(height=2),
            grid,
        ],
    )
