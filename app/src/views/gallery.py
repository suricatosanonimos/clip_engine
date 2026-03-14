"""
Aba 3 — Galeria.
Lê os clipes reais de processed_videos/final_clips/ e raw_clips/
e permite reproduzir, abrir pasta e remover cada um.
Compatível com Flet 0.82.
"""

import os
import subprocess
import threading
from datetime import datetime
from pathlib import Path

import flet as ft

from src.views.theme import C

# ──────────────────────────────────────────────────────────────────
#  DIRETÓRIOS — sobe a árvore até encontrar a pasta "api"
# ──────────────────────────────────────────────────────────────────

def _encontrar_api_root() -> Path:
    p = Path(__file__).resolve()
    while p.parent != p:
        if (p.parent / "api").exists():
            return p.parent / "api"
        p = p.parent
    return Path.home() / "Code" / "clip_engine" / "api"

_API_ROOT       = _encontrar_api_root()
FINAL_CLIPS_DIR = _API_ROOT / "processed_videos" / "final_clips"
RAW_CLIPS_DIR   = _API_ROOT / "processed_videos" / "raw_clips"
_VIDEO_EXT      = {".mp4", ".mov", ".mkv", ".avi", ".webm"}


# ──────────────────────────────────────────────────────────────────
#  HELPERS
# ──────────────────────────────────────────────────────────────────

def _listar_clipes() -> list:
    clipes = {}

    def _add(path: Path, tipo: str):
        if path.suffix.lower() not in _VIDEO_EXT:
            return
        stat  = path.stat()
        mtime = datetime.fromtimestamp(stat.st_mtime)
        hoje  = datetime.now().date()
        if mtime.date() == hoje:
            data_fmt = f"Hoje, {mtime.strftime('%H:%M')}"
        elif (hoje - mtime.date()).days == 1:
            data_fmt = f"Ontem, {mtime.strftime('%H:%M')}"
        else:
            data_fmt = mtime.strftime("%d/%m, %H:%M")

        size_mb  = stat.st_size / (1024 * 1024)
        nome_key = path.stem.replace("FINAL_HOOK_", "")

        clipes[nome_key] = {
            "titulo":  path.stem.replace("_", " ").replace("FINAL HOOK ", "").title(),
            "arquivo": path.name,
            "path":    str(path),
            "duracao": f"{size_mb:.0f} MB",
            "score":   0.0,
            "data":    data_fmt,
            "tipo":    tipo,
            "size_mb": size_mb,
        }

    if FINAL_CLIPS_DIR.exists():
        for f in sorted(FINAL_CLIPS_DIR.iterdir(),
                        key=lambda x: x.stat().st_mtime, reverse=True):
            _add(f, "final")

    if RAW_CLIPS_DIR.exists():
        for f in sorted(RAW_CLIPS_DIR.iterdir(),
                        key=lambda x: x.stat().st_mtime, reverse=True):
            if f.suffix.lower() in _VIDEO_EXT:
                nome_key = f.stem
                if nome_key not in clipes:
                    _add(f, "raw")

    return list(clipes.values())


def _abrir_video_nativo(path: str):
    try:
        if os.name == "nt":
            os.startfile(path)
        elif os.uname().sysname == "Darwin":
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path])
    except Exception as e:
        print(f"Erro ao abrir: {e}")


# ──────────────────────────────────────────────────────────────────
#  ABA GALERIA
# ──────────────────────────────────────────────────────────────────

def build_aba_galeria(estado: dict, page: ft.Page) -> ft.Control:

    # Estado simples em variáveis Python — sem ft.Ref para strings
    _state = {
        "clipes":      [],
        "busca":       "",
    }

    # Controles que serão atualizados
    grid         = ft.GridView(
        runs_count=2,
        max_extent=220,
        child_aspect_ratio=0.72,
        spacing=10,
        run_spacing=10,
        expand=True,
    )
    contador_txt = ft.Text(
        "0 clipes", size=12,
        color=C.ACCENT, weight=ft.FontWeight.W_700,
    )
    status_txt   = ft.Text("Carregando...", size=12, color=C.TEXT_SECONDARY)
    campo_busca  = ft.TextField(
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

    # ──────────────────────────────────────────────────────────────
    #  CARD
    # ──────────────────────────────────────────────────────────────

    def _galeria_card(item: dict) -> ft.Container:
        is_final   = item["tipo"] == "final"
        borda_cor  = C.SUCCESS + "55" if is_final else C.BORDER
        badge_cor  = C.SUCCESS if is_final else C.WARNING
        badge_txt  = "FINAL" if is_final else "RAW"

        def on_play(e):
            _abrir_video_nativo(item["path"])

        def on_pasta(e):
            _abrir_video_nativo(str(Path(item["path"]).parent))

        def on_delete(e):
            dlg = ft.AlertDialog(
                title=ft.Text(
                    "Remover clipe?",
                    color=C.TEXT_PRIMARY,
                    weight=ft.FontWeight.W_700,
                ),
                content=ft.Text(
                    f"'{item['arquivo']}' será apagado permanentemente.",
                    size=13,
                    color=C.TEXT_SECONDARY,
                ),
                bgcolor=C.SURFACE,
                shape=ft.RoundedRectangleBorder(radius=12),
                actions=[
                    ft.TextButton(
                        "Cancelar",
                        on_click=lambda e: page.close(dlg),
                        style=ft.ButtonStyle(color=C.TEXT_SECONDARY),
                    ),
                    ft.FilledButton(
                        "Remover",
                        on_click=lambda e: _confirmar_delete(dlg, item),
                        style=ft.ButtonStyle(
                            bgcolor=C.ERROR,
                            color=C.BG,
                            shape=ft.RoundedRectangleBorder(radius=6),
                        ),
                    ),
                ],
            )
            page.open(dlg)

        titulo_curto = (
            item["titulo"]
            if len(item["titulo"]) <= 38
            else item["titulo"][:38] + "…"
        )

        return ft.Container(
            border_radius=8,
            bgcolor=C.SURFACE,
            border=ft.Border(
                left=ft.BorderSide(1, borda_cor),
                right=ft.BorderSide(1, borda_cor),
                top=ft.BorderSide(1, borda_cor),
                bottom=ft.BorderSide(1, borda_cor),
            ),
            clip_behavior=ft.ClipBehavior.HARD_EDGE,
            animate=ft.Animation(200, ft.AnimationCurve.EASE_OUT),
            content=ft.Column(
                spacing=0,
                controls=[
                    # ── Thumbnail ──────────────────────────────────
                    ft.Container(
                        height=100,
                        border_radius=ft.BorderRadius(
                            top_left=8, top_right=8,
                            bottom_left=0, bottom_right=0,
                        ),
                        clip_behavior=ft.ClipBehavior.HARD_EDGE,
                        on_click=on_play,
                        content=ft.Stack(
                            controls=[
                                # Fundo gradiente
                                ft.Container(
                                    expand=True,
                                    border_radius=ft.BorderRadius(
                                        top_left=8, top_right=8,
                                        bottom_left=0, bottom_right=0,
                                    ),
                                    gradient=ft.LinearGradient(
                                        colors=[C.SURFACE_2, "#1A1A28"],
                                        begin=ft.Alignment(-1, -1),
                                        end=ft.Alignment(1, 1),
                                    ),
                                ),
                                # Botão play central
                                ft.Container(
                                    expand=True,
                                    alignment=ft.Alignment(0, 0),
                                    content=ft.IconButton(
                                        icon=ft.Icons.PLAY_CIRCLE_FILLED,
                                        icon_color=C.ACCENT + "DD",
                                        icon_size=44,
                                        tooltip="Reproduzir",
                                        on_click=on_play,
                                        style=ft.ButtonStyle(
                                            overlay_color=ft.Colors.TRANSPARENT,
                                            padding=ft.Padding(0, 0, 0, 0),
                                        ),
                                    ),
                                ),
                                # Badge FINAL / RAW
                                ft.Container(
                                    top=6, left=6,
                                    border_radius=4,
                                    bgcolor=C.BG + "CC",
                                    padding=ft.Padding(
                                        left=5, right=5, top=2, bottom=2,
                                    ),
                                    content=ft.Text(
                                        badge_txt,
                                        size=9,
                                        weight=ft.FontWeight.W_800,
                                        color=badge_cor,
                                        font_family="monospace",
                                    ),
                                ),
                                # Tamanho
                                ft.Container(
                                    bottom=6, left=6,
                                    border_radius=4,
                                    bgcolor=C.BG + "CC",
                                    padding=ft.Padding(
                                        left=6, right=6, top=3, bottom=3,
                                    ),
                                    content=ft.Text(
                                        item["duracao"],
                                        size=10,
                                        color=C.TEXT_PRIMARY,
                                        font_family="monospace",
                                    ),
                                ),
                            ],
                        ),
                    ),

                    # ── Info ────────────────────────────────────────
                    ft.Container(
                        padding=ft.Padding(
                            left=10, right=10, top=8, bottom=8,
                        ),
                        content=ft.Column(
                            spacing=4,
                            controls=[
                                ft.Text(
                                    titulo_curto,
                                    size=12,
                                    weight=ft.FontWeight.W_600,
                                    color=C.TEXT_PRIMARY,
                                    max_lines=2,
                                    overflow=ft.TextOverflow.ELLIPSIS,
                                ),
                                ft.Text(
                                    item["data"],
                                    size=10,
                                    color=C.TEXT_MUTED,
                                ),
                                ft.Row(
                                    spacing=0,
                                    alignment=ft.MainAxisAlignment.END,
                                    controls=[
                                        ft.IconButton(
                                            icon=ft.Icons.PLAY_ARROW,
                                            icon_color=C.CYAN,
                                            icon_size=16,
                                            tooltip="Reproduzir",
                                            on_click=on_play,
                                            style=ft.ButtonStyle(
                                                padding=ft.Padding(0, 0, 0, 0),
                                            ),
                                        ),
                                        ft.IconButton(
                                            icon=ft.Icons.FOLDER_OPEN_OUTLINED,
                                            icon_color=C.ACCENT,
                                            icon_size=16,
                                            tooltip="Abrir pasta",
                                            on_click=on_pasta,
                                            style=ft.ButtonStyle(
                                                padding=ft.Padding(0, 0, 0, 0),
                                            ),
                                        ),
                                        ft.IconButton(
                                            icon=ft.Icons.DELETE_OUTLINE,
                                            icon_color=C.ERROR,
                                            icon_size=16,
                                            tooltip="Remover",
                                            on_click=on_delete,
                                            style=ft.ButtonStyle(
                                                padding=ft.Padding(0, 0, 0, 0),
                                            ),
                                        ),
                                    ],
                                ),
                            ],
                        ),
                    ),
                ],
            ),
        )

    # ──────────────────────────────────────────────────────────────
    #  LÓGICA
    # ──────────────────────────────────────────────────────────────

    def _confirmar_delete(dlg, item: dict):
        page.close(dlg)
        try:
            Path(item["path"]).unlink(missing_ok=True)
        except Exception as e:
            status_txt.value = f"Erro ao remover: {e}"
            status_txt.color = C.ERROR
            page.update()
            return
        _recarregar()

    def _renderizar(busca: str = ""):
        busca     = busca.lower().strip()
        clipes    = _state["clipes"]
        filtrados = (
            [c for c in clipes
             if busca in c["titulo"].lower() or busca in c["arquivo"].lower()]
            if busca else clipes
        )

        grid.controls = [_galeria_card(c) for c in filtrados]

        total    = len(clipes)
        visíveis = len(filtrados)
        contador_txt.value = (
            f"{total} clipes" if not busca
            else f"{visíveis}/{total} clipes"
        )
        status_txt.value = "" if filtrados else "Nenhum clipe encontrado."
        status_txt.color = C.TEXT_SECONDARY
        page.update()

    def _recarregar(e=None):
        status_txt.value = "Atualizando..."
        status_txt.color = C.TEXT_SECONDARY
        page.update()

        def _carregar():
            _state["clipes"] = _listar_clipes()
            _renderizar(_state["busca"])

        threading.Thread(target=_carregar, daemon=True).start()

    def on_busca(e):
        _state["busca"] = e.control.value or ""
        _renderizar(_state["busca"])

    campo_busca.on_change = on_busca

    # Carrega ao abrir a aba
    _recarregar()

    # ──────────────────────────────────────────────────────────────
    #  LAYOUT
    # ──────────────────────────────────────────────────────────────

    return ft.Column(
        spacing=8,
        expand=True,
        controls=[
            # Header
            ft.Row(
                spacing=8,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    ft.Icon(ft.Icons.VIDEO_LIBRARY_OUTLINED, color=C.ACCENT, size=20),
                    ft.Text(
                        "Galeria",
                        size=20,
                        weight=ft.FontWeight.W_800,
                        color=C.TEXT_PRIMARY,
                    ),
                    ft.Container(expand=True),
                    ft.Container(
                        border_radius=20,
                        bgcolor=C.ACCENT_SOFT,
                        border=ft.Border(
                            left=ft.BorderSide(1, C.ACCENT + "44"),
                            right=ft.BorderSide(1, C.ACCENT + "44"),
                            top=ft.BorderSide(1, C.ACCENT + "44"),
                            bottom=ft.BorderSide(1, C.ACCENT + "44"),
                        ),
                        padding=ft.Padding(
                            left=10, right=10, top=4, bottom=4,
                        ),
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

            ft.Row(
                controls=[
                    ft.Text(
                        "Clipes prontos para publicação.",
                        size=13,
                        color=C.TEXT_SECONDARY,
                        expand=True,
                    ),
                    status_txt,
                ],
            ),

            ft.Container(height=4),

            # Busca
            ft.Row(
                spacing=8,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    campo_busca,
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
            ),

            ft.Container(height=4),

            # Grid
            grid,
        ],
    )
