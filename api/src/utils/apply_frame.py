#!/usr/bin/env python3
"""
src/utils/apply_frame.py
Aplica moldura/background em vídeos 9:16 com GUI interativa.
Mostra todos os vídeos disponíveis, configura visualmente e aplica em lote.
Compatível com Linux e Windows (usa tkinter nativo).
"""
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple
# ══════════════════════════════════════════════════════════════
#  VERIFICAÇÃO DE DEPENDÊNCIAS (tkinter)
# ══════════════════════════════════════════════════════════════
def _ensure_tkinter():
    _TKINTER_PATHS = [
        "/usr/lib/python3.{v}/tkinter",
        "/usr/lib/python3/python{v}/tkinter",
        "/usr/lib/python3.{v}/lib-dynload",
    ]
    try:
        import tkinter as tk
        from tkinter import ttk, filedialog, messagebox
        return tk, ttk, filedialog, messagebox
    except ImportError:
        import platform
        system = platform.system()
        py_ver = f"{sys.version_info.major}.{sys.version_info.minor}"
        if system == "Linux":
            for path_template in _TKINTER_PATHS:
                path = path_template.format(v=py_ver)
                if os.path.exists(path) and path not in sys.path:
                    sys.path.append(path)
            try:
                import tkinter as tk
                from tkinter import ttk, filedialog, messagebox
                return tk, ttk, filedialog, messagebox
            except ImportError:
                pass
            tk_pkg = f"python{py_ver}-tk"
            result = subprocess.run(["dpkg", "-l", tk_pkg], capture_output=True, text=True)
            if "ii" not in result.stdout:
                print(f"\n❌ Pacote {tk_pkg} não instalado.")
                print(f"   Execute: sudo apt-get install -y {tk_pkg}")
                sys.exit(1)
            print(f"\n⚠️  {tk_pkg} instalado mas não acessível pelo venv.")
            print("   Solução: python3 -m venv --system-site-packages .venv")
            sys.exit(1)
        elif system == "Windows":
            print("tkinter deve vir com o Python.")
            sys.exit(1)
        else:
            print(f"Instale tkinter para {system}.")
            sys.exit(1)
tk, ttk, filedialog, messagebox = _ensure_tkinter()
# ══════════════════════════════════════════════════════════════
#  CONSTANTES
# ══════════════════════════════════════════════════════════════
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
ASSETS_DIR = ROOT_DIR / "assets"
RAW_CLIPS_DIR = ROOT_DIR / "processed_videos" / "raw_clips"
FINAL_CLIPS_DIR = ROOT_DIR / "processed_videos" / "final_clips"
CANVAS_W = 360
CANVAS_H = 640
SCALE = 2.0
# Tamanho dos handles de redimensionamento (cantos/bordas)
HANDLE_SIZE = 8
# ══════════════════════════════════════════════════════════════
#  FUNÇÕES AUXILIARES
# ══════════════════════════════════════════════════════════════
def find_all_videos() -> List[Path]:
    videos = []
    for d in [RAW_CLIPS_DIR, FINAL_CLIPS_DIR]:
        if d.exists():
            videos.extend(sorted(d.glob("*.mp4")))
    return videos
def find_all_frames() -> List[Path]:
    if not ASSETS_DIR.exists():
        return []
    return sorted(ASSETS_DIR.glob("*.png"))
def get_video_info(video_path: Path) -> Dict:
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration,size",
             "-show_entries", "stream=width,height", "-of", "json", str(video_path)],
            capture_output=True, text=True, check=True
        )
        data = json.loads(result.stdout)
        fmt = data.get("format", {})
        streams = data.get("streams", [])
        vs = next((s for s in streams if s.get("codec_type") == "video"), {})
        return {
            "duration": float(fmt.get("duration", 0)),
            "size_mb": int(fmt.get("size", 0)) / (1024 * 1024),
            "width": int(vs.get("width", 0)),
            "height": int(vs.get("height", 0)),
        }
    except Exception:
        return {"duration": 0, "size_mb": 0, "width": 0, "height": 0}
def _get_screen_geometry(root) -> str:
    """Calcula geometria adaptativa baseada na tela."""
    sw = root.winfo_screenwidth()
    sh = root.winfo_screenheight()
    w = min(1000, sw - 100)
    h = min(780, sh - 100)
    x = (sw - w) // 2
    y = (sh - h) // 2
    return f"{w}x{h}+{x}+{y}"
# ══════════════════════════════════════════════════════════════
#  GUI PRINCIPAL
# ══════════════════════════════════════════════════════════════
class FrameApplierGUI:
    """GUI completa com redimensionamento flexível e janela adaptativa."""
    
    def __init__(self):
        self.frame_path = None
        self.video_area = {"x": 110, "y": 235, "w": 500, "h": 890}
        self.all_videos = find_all_videos()
        self.all_frames = find_all_frames()
        self.result = None
        
        # Estado de arrasto/redimensionamento
        self._drag_mode = None      # "move", "resize_n", "resize_s", etc.
        self._drag_start_x = 0
        self._drag_start_y = 0
        self._drag_start_area = {}
        
        self._create_gui()
    
    def _create_gui(self):
        self.root = tk.Tk()
        self.root.title("🎬 Clip Engine - Moldura/Background")
        
        # Geometria adaptativa
        geom = _get_screen_geometry(self.root)
        self.root.geometry(geom)
        self.root.minsize(950, 650)
        self.root.configure(bg="#1a1a2e")
        
        # CRIA status_var ANTES de tudo
        self.status_var = tk.StringVar(value="Pronto. Arraste o retângulo para mover. Bordas para redimensionar.")
        
        # Estilo escuro
        style = ttk.Style()
        style.theme_use("clam")
        style.configure(".", background="#1a1a2e", foreground="white", font=("Arial", 9))
        style.configure("TLabel", background="#1a1a2e", foreground="white")
        style.configure("TButton", font=("Arial", 10, "bold"), padding=6)
        style.configure("TScale", background="#1a1a2e")
        style.configure("TFrame", background="#1a1a2e")
        style.configure("TLabelframe", background="#1a1a2e", foreground="#00d4ff")
        style.configure("TLabelframe.Label", background="#1a1a2e", foreground="#00d4ff", 
                       font=("Arial", 10, "bold"))
        
        # ═══════════════════════════════════════════════════════
        # HEADER
        # ═══════════════════════════════════════════════════════
        tk.Label(self.root, text="🖼️  CONFIGURAR MOLDURA & APLICAR",
                font=("Arial", 14, "bold"), bg="#1a1a2e", fg="#00d4ff",
                height=1).pack(pady=5, fill="x")
        
        # ═══════════════════════════════════════════════════════
        # BOTÕES NO TOPO (sempre visíveis)
        # ═══════════════════════════════════════════════════════
        btn_top_frame = tk.Frame(self.root, bg="#1a1a2e")
        btn_top_frame.pack(fill="x", padx=10, pady=2)
        
        apply_btn = tk.Button(btn_top_frame, text="✅ APLICAR MOLDURA", 
                             command=self._on_apply,
                             bg="#00cc66", fg="white", font=("Arial", 12, "bold"),
                             padx=20, pady=8, bd=0, cursor="hand2",
                             activebackground="#00ff88", activeforeground="black")
        apply_btn.pack(side="left", padx=5)
        
        reset_btn = tk.Button(btn_top_frame, text="🔄 Reset",
                             command=self._on_reset,
                             bg="#444444", fg="white", font=("Arial", 10),
                             padx=15, pady=5, bd=0, cursor="hand2")
        reset_btn.pack(side="left", padx=5)
        
        cancel_btn = tk.Button(btn_top_frame, text="❌ Cancelar",
                              command=self._on_cancel,
                              bg="#cc3333", fg="white", font=("Arial", 10),
                              padx=15, pady=5, bd=0, cursor="hand2")
        cancel_btn.pack(side="left", padx=5)
        
        # Status (à direita dos botões)
        tk.Label(btn_top_frame, textvariable=self.status_var,
                bg="#1a1a2e", fg="#888888", anchor="w", padx=10,
        ).pack(side="right", fill="x", expand=True)
        
        # ═══════════════════════════════════════════════════════
        # PAINEL PRINCIPAL (2 colunas)
        # ═══════════════════════════════════════════════════════
        main_panel = ttk.Frame(self.root)
        main_panel.pack(fill="both", expand=True, padx=10, pady=2)
        
        left_col = ttk.Frame(main_panel)
        left_col.pack(side="left", fill="both", expand=True, padx=(0, 5))
        
        right_col = ttk.Frame(main_panel)
        right_col.pack(side="right", fill="both", expand=True, padx=(5, 0))
        
        self._build_left_column(left_col)
        self._build_right_column(right_col)
    
    def _build_left_column(self, parent):
        """Preview + controles."""
        # Seletor de moldura
        frame_sel = ttk.LabelFrame(parent, text="📁 Moldura", padding=8)
        frame_sel.pack(fill="x", pady=(0, 5))
        
        frame_names = [f.name for f in self.all_frames] if self.all_frames else ["(nenhuma)"]
        self.frame_var = tk.StringVar(value=frame_names[0] if self.all_frames else "")
        
        frame_combo = ttk.Combobox(frame_sel, textvariable=self.frame_var, 
                                   values=frame_names, state="readonly")
        frame_combo.pack(fill="x")
        frame_combo.bind("<<ComboboxSelected>>", self._on_frame_changed)
        
        # Canvas preview
        canvas_frame = tk.Frame(parent, bg="#0a0a1e", bd=2, relief="sunken")
        canvas_frame.pack(pady=5)
        
        self.canvas = tk.Canvas(canvas_frame, width=CANVAS_W, height=CANVAS_H,
                               bg="#0a0a1e", highlightthickness=0)
        self.canvas.pack()
        
        # Retângulo do vídeo
        self.video_rect = self.canvas.create_rectangle(0, 0, 100, 100,
            outline="#00ff88", width=2, fill="", dash=(5, 3), tags="video_rect")
        
        self.video_label = self.canvas.create_text(0, 0, text="🎬 VÍDEO",
            fill="#00ff88", font=("Arial", 9, "bold"), tags="video_rect")
        
        # Handles de redimensionamento (8 pontos: 4 cantos + 4 bordas)
        self._handles = {}
        handle_tags = ["nw", "n", "ne", "e", "se", "s", "sw", "w"]
        for tag in handle_tags:
            h = self.canvas.create_rectangle(0, 0, HANDLE_SIZE, HANDLE_SIZE,
                fill="#00ff88", outline="#00aa44", tags=("handle", tag))
            self._handles[tag] = h
        
        # Bind eventos para TODOS os itens
        for item in [self.video_rect, self.video_label] + list(self._handles.values()):
            self.canvas.tag_bind(item, "<Button-1>", self._on_mouse_down)
            self.canvas.tag_bind(item, "<B1-Motion>", self._on_mouse_move)
        self.canvas.tag_bind("video_rect", "<ButtonRelease-1>", self._on_mouse_up)
        for h in self._handles.values():
            self.canvas.tag_bind(h, "<ButtonRelease-1>", self._on_mouse_up)
        
        # Cursor muda sobre handles
        self.canvas.tag_bind("handle", "<Enter>", lambda e: self.canvas.config(cursor="fleur"))
        self.canvas.tag_bind("handle", "<Leave>", lambda e: self.canvas.config(cursor=""))
        
        # Controles
        ctrl = ttk.LabelFrame(parent, text="📐 Ajustes", padding=8)
        ctrl.pack(fill="x", pady=5)
        
        ttk.Label(ctrl, text="Tamanho (%):").grid(row=0, column=0, sticky="w")
        self.scale_var = tk.DoubleVar(value=70)
        ttk.Scale(ctrl, from_=20, to=100, variable=self.scale_var,
                 orient="horizontal", command=self._on_scale_change,
        ).grid(row=0, column=1, sticky="ew", padx=5)
        self.scale_label = ttk.Label(ctrl, text="70%", width=5)
        self.scale_label.grid(row=0, column=2)
        
        coord = ttk.Frame(ctrl)
        coord.grid(row=1, column=0, columnspan=3, pady=8)
        
        vars_list = []
        for lbl, default, max_val in [
            ("X:", 110, 720), ("Y:", 235, 1280), ("L:", 500, 720), ("A:", 890, 1280)
        ]:
            ttk.Label(coord, text=lbl).pack(side="left", padx=1)
            var = tk.IntVar(value=default)
            vars_list.append(var)
            ttk.Spinbox(coord, from_=0, to=max_val, textvariable=var,
                       width=5, command=self._on_coord_change).pack(side="left", padx=1)
        
        self.x_var, self.y_var, self.w_var, self.h_var = vars_list
        ctrl.columnconfigure(1, weight=1)
        
        # Info rápida
        self.dim_label = ttk.Label(ctrl, text="", foreground="#888888")
        self.dim_label.grid(row=2, column=0, columnspan=3, pady=(5, 0))
        
        if self.all_frames:
            self._load_frame(self.all_frames[0])
    
    def _build_right_column(self, parent):
        """Lista de vídeos."""
        videos_frame = ttk.LabelFrame(parent, text="🎬 Vídeos Disponíveis", padding=8)
        videos_frame.pack(fill="both", expand=True)
        
        sel_frame = ttk.Frame(videos_frame)
        sel_frame.pack(fill="x", pady=(0, 5))
        ttk.Button(sel_frame, text="Todos", command=self._select_all).pack(side="left", padx=2)
        ttk.Button(sel_frame, text="Nenhum", command=self._select_none).pack(side="left", padx=2)
        
        list_frame = ttk.Frame(videos_frame)
        list_frame.pack(fill="both", expand=True)
        
        self.video_listbox = tk.Listbox(list_frame, bg="#0a0a1e", fg="white",
            selectmode="multiple", font=("Arial", 9), activestyle="none")
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.video_listbox.yview)
        self.video_listbox.configure(yscrollcommand=scrollbar.set)
        self.video_listbox.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        self.video_paths = []
        for v in self.all_videos:
            info = get_video_info(v)
            origin = "📼" if "raw_clips" in str(v) else "🎬"
            label = f"{origin} {v.name} ({info['size_mb']:.1f}MB)"
            self.video_listbox.insert("end", label)
            self.video_paths.append(v)
        
        self.video_listbox.select_set(0, "end")
        
        self.video_count_var = tk.StringVar(value=f"{len(self.all_videos)} vídeo(s)")
        ttk.Label(videos_frame, textvariable=self.video_count_var).pack(pady=(5, 0))
    
    # ══════════════════════════════════════════════════════════
    #  EVENTOS DE MOUSE (MOVER + REDIMENSIONAR)
    # ══════════════════════════════════════════════════════════
    
    def _get_handle_under_mouse(self, event) -> Optional[str]:
        """Retorna qual handle está sob o mouse."""
        # Verifica proximidade dos cantos/bordas (com margem de tolerância)
        va = self.video_area
        sx, sy = SCALE, SCALE
        mx, my = event.x * sx, event.y * sy
        
        margin = 15 * SCALE  # tolerância em pixels reais
        
        # Cantos
        if abs(mx - va["x"]) < margin and abs(my - va["y"]) < margin:
            return "nw"
        if abs(mx - (va["x"] + va["w"])) < margin and abs(my - va["y"]) < margin:
            return "ne"
        if abs(mx - va["x"]) < margin and abs(my - (va["y"] + va["h"])) < margin:
            return "sw"
        if abs(mx - (va["x"] + va["w"])) < margin and abs(my - (va["y"] + va["h"])) < margin:
            return "se"
        
        # Bordas
        if abs(mx - va["x"]) < margin and va["y"] < my < va["y"] + va["h"]:
            return "w"
        if abs(mx - (va["x"] + va["w"])) < margin and va["y"] < my < va["y"] + va["h"]:
            return "e"
        if abs(my - va["y"]) < margin and va["x"] < mx < va["x"] + va["w"]:
            return "n"
        if abs(my - (va["y"] + va["h"])) < margin and va["x"] < mx < va["x"] + va["w"]:
            return "s"
        
        # Dentro do retângulo
        if va["x"] < mx < va["x"] + va["w"] and va["y"] < my < va["y"] + va["h"]:
            return "move"
        
        return None
    
    def _on_mouse_down(self, event):
        """Detecta modo: mover ou redimensionar."""
        mode = self._get_handle_under_mouse(event)
        
        if mode is None:
            return
        
        self._drag_mode = mode
        self._drag_start_x = event.x
        self._drag_start_y = event.y
        self._drag_start_area = dict(self.video_area)
        
        # Muda cursor
        cursors = {
            "move": "fleur",
            "n": "top_side", "s": "bottom_side",
            "e": "right_side", "w": "left_side",
            "nw": "top_left_corner", "ne": "top_right_corner",
            "sw": "bottom_left_corner", "se": "bottom_right_corner",
        }
        self.canvas.config(cursor=cursors.get(mode, "fleur"))
    
    def _on_mouse_move(self, event):
        """Move ou redimensiona."""
        if self._drag_mode is None:
            # Atualiza cursor
            mode = self._get_handle_under_mouse(event)
            cursors = {
                "move": "fleur", "n": "top_side", "s": "bottom_side",
                "e": "right_side", "w": "left_side",
                "nw": "top_left_corner", "ne": "top_right_corner",
                "sw": "bottom_left_corner", "se": "bottom_right_corner",
            }
            self.canvas.config(cursor=cursors.get(mode, ""))
            return
        
        dx = (event.x - self._drag_start_x) * SCALE
        dy = (event.y - self._drag_start_y) * SCALE
        va = self._drag_start_area
        
        if self._drag_mode == "move":
            self.video_area["x"] = max(0, min(va["x"] + int(dx), 720 - self.video_area["w"]))
            self.video_area["y"] = max(0, min(va["y"] + int(dy), 1280 - self.video_area["h"]))
        
        elif self._drag_mode == "e":
            self.video_area["w"] = max(100, va["w"] + int(dx))
            self.video_area["w"] = min(self.video_area["w"], 720 - va["x"])
        elif self._drag_mode == "w":
            new_w = max(100, va["w"] - int(dx))
            self.video_area["x"] = va["x"] + va["w"] - new_w
            self.video_area["x"] = max(0, self.video_area["x"])
            self.video_area["w"] = new_w
        elif self._drag_mode == "s":
            self.video_area["h"] = max(100, va["h"] + int(dy))
            self.video_area["h"] = min(self.video_area["h"], 1280 - va["y"])
        elif self._drag_mode == "n":
            new_h = max(100, va["h"] - int(dy))
            self.video_area["y"] = va["y"] + va["h"] - new_h
            self.video_area["y"] = max(0, self.video_area["y"])
            self.video_area["h"] = new_h
        
        elif self._drag_mode == "se":
            self.video_area["w"] = max(100, va["w"] + int(dx))
            self.video_area["w"] = min(self.video_area["w"], 720 - va["x"])
            self.video_area["h"] = max(100, va["h"] + int(dy))
            self.video_area["h"] = min(self.video_area["h"], 1280 - va["y"])
        elif self._drag_mode == "sw":
            new_w = max(100, va["w"] - int(dx))
            self.video_area["x"] = va["x"] + va["w"] - new_w
            self.video_area["x"] = max(0, self.video_area["x"])
            self.video_area["w"] = new_w
            self.video_area["h"] = max(100, va["h"] + int(dy))
            self.video_area["h"] = min(self.video_area["h"], 1280 - va["y"])
        elif self._drag_mode == "ne":
            self.video_area["w"] = max(100, va["w"] + int(dx))
            self.video_area["w"] = min(self.video_area["w"], 720 - va["x"])
            new_h = max(100, va["h"] - int(dy))
            self.video_area["y"] = va["y"] + va["h"] - new_h
            self.video_area["y"] = max(0, self.video_area["y"])
            self.video_area["h"] = new_h
        elif self._drag_mode == "nw":
            new_w = max(100, va["w"] - int(dx))
            self.video_area["x"] = va["x"] + va["w"] - new_w
            self.video_area["x"] = max(0, self.video_area["x"])
            self.video_area["w"] = new_w
            new_h = max(100, va["h"] - int(dy))
            self.video_area["y"] = va["y"] + va["h"] - new_h
            self.video_area["y"] = max(0, self.video_area["y"])
            self.video_area["h"] = new_h
        
        self._update_preview()
        self._update_spinboxes()
        self._update_handles()
    
    def _on_mouse_up(self, event):
        self._drag_mode = None
        self.canvas.config(cursor="")
        self._update_handles()
    
    def _update_handles(self):
        """Atualiza posição dos handles de redimensionamento."""
        va = self.video_area
        sx, sy = SCALE, SCALE
        hs = HANDLE_SIZE
        
        positions = {
            "nw": (va["x"]/sx - hs/2, va["y"]/sy - hs/2),
            "n":  ((va["x"] + va["w"]/2)/sx - hs/2, va["y"]/sy - hs/2),
            "ne": ((va["x"] + va["w"])/sx - hs/2, va["y"]/sy - hs/2),
            "e":  ((va["x"] + va["w"])/sx - hs/2, (va["y"] + va["h"]/2)/sy - hs/2),
            "se": ((va["x"] + va["w"])/sx - hs/2, (va["y"] + va["h"])/sy - hs/2),
            "s":  ((va["x"] + va["w"]/2)/sx - hs/2, (va["y"] + va["h"])/sy - hs/2),
            "sw": (va["x"]/sx - hs/2, (va["y"] + va["h"])/sy - hs/2),
            "w":  (va["x"]/sx - hs/2, (va["y"] + va["h"]/2)/sy - hs/2),
        }
        
        for tag, (hx, hy) in positions.items():
            if tag in self._handles:
                self.canvas.coords(self._handles[tag], hx, hy, hx + hs, hy + hs)
    
    # ══════════════════════════════════════════════════════════
    #  DEMAIS EVENTOS
    # ══════════════════════════════════════════════════════════
    
    def _on_frame_changed(self, event=None):
        name = self.frame_var.get()
        for f in self.all_frames:
            if f.name == name:
                self._load_frame(f)
                break
    
    def _load_frame(self, frame_path: Path):
        self.frame_path = frame_path
        self.canvas.delete("frame_bg")
        try:
            from PIL import Image, ImageTk
            img = Image.open(frame_path)
            img = img.resize((CANVAS_W, CANVAS_H), Image.LANCZOS)
            self.frame_image = ImageTk.PhotoImage(img)
            self.canvas.create_image(0, 0, anchor="nw", image=self.frame_image, tags="frame_bg")
        except ImportError:
            self.canvas.create_text(CANVAS_W/2, CANVAS_H/2,
                text="pip install Pillow\npara preview",
                fill="#666", font=("Arial", 10), tags="frame_bg")
        self.canvas.tag_raise("video_rect")
        self.canvas.tag_raise("handle")
        self._update_preview()
        self._update_handles()
        self.status_var.set(f"Moldura: {frame_path.name}")
    
    def _on_scale_change(self, event=None):
        scale = self.scale_var.get() / 100
        self.video_area["w"] = int(720 * scale)
        self.video_area["h"] = int(1280 * scale)
        self.video_area["x"] = (720 - self.video_area["w"]) // 2
        self.video_area["y"] = (1280 - self.video_area["h"]) // 2
        self.scale_label.config(text=f"{int(self.scale_var.get())}%")
        self._update_preview()
        self._update_spinboxes()
        self._update_handles()
    
    def _on_coord_change(self):
        try:
            self.video_area["x"] = self.x_var.get()
            self.video_area["y"] = self.y_var.get()
            self.video_area["w"] = self.w_var.get()
            self.video_area["h"] = self.h_var.get()
            self._update_preview()
            self._update_handles()
        except (ValueError, tk.TclError):
            pass
    
    def _update_preview(self):
        va = self.video_area
        sx, sy = SCALE, SCALE
        self.canvas.coords(self.video_rect,
            va["x"]/sx, va["y"]/sy, (va["x"]+va["w"])/sx, (va["y"]+va["h"])/sy)
        cx = (va["x"] + va["w"]/2) / sx
        cy = (va["y"] + va["h"]/2) / sy
        self.canvas.coords(self.video_label, cx, cy)
        self.dim_label.config(text=f"{va['w']}×{va['h']}px em ({va['x']},{va['y']})")
    
    def _update_spinboxes(self):
        va = self.video_area
        self.x_var.set(va["x"]); self.y_var.set(va["y"])
        self.w_var.set(va["w"]); self.h_var.set(va["h"])
    
    def _select_all(self): self.video_listbox.select_set(0, "end")
    def _select_none(self): self.video_listbox.select_clear(0, "end")
    
    def _get_selected_videos(self) -> List[Path]:
        return [self.video_paths[i] for i in self.video_listbox.curselection() if i < len(self.video_paths)]
    
    def _on_reset(self):
        self.video_area = {"x": 110, "y": 235, "w": 500, "h": 890}
        self.scale_var.set(70)
        self.scale_label.config(text="70%")
        self._update_preview()
        self._update_spinboxes()
        self._update_handles()
        self.status_var.set("Configuração resetada.")
    
    def _on_apply(self):
        videos = self._get_selected_videos()
        if not videos:
            messagebox.showwarning("Aviso", "Selecione pelo menos um vídeo.")
            return
        if not self.frame_path:
            messagebox.showwarning("Aviso", "Selecione uma moldura.")
            return
        confirm = messagebox.askyesno("Confirmar",
            f"Aplicar moldura em {len(videos)} vídeo(s)?\n\n"
            f"Moldura: {self.frame_path.name}\n"
            f"Área: {self.video_area['w']}×{self.video_area['h']}\n"
            f"Posição: ({self.video_area['x']}, {self.video_area['y']})")
        if not confirm:
            return
        self.result = {
            "frame_path": str(self.frame_path),
            "video_area": dict(self.video_area),
            "videos": [str(v) for v in videos],
        }
        self.root.destroy()
    
    def _on_cancel(self):
        self.result = None
        self.root.destroy()
    
    def run(self) -> Optional[Dict]:
        self.root.update_idletasks()
        self.root.mainloop()
        return self.result
# ══════════════════════════════════════════════════════════════
#  CLASSE DE APLICAÇÃO
# ══════════════════════════════════════════════════════════════
class FrameApplier:
    def __init__(self, frame_path: str, video_area: Optional[Dict[str, int]] = None,
                 crf: int = 20, preset: str = "fast"):
        self.frame_path = Path(frame_path)
        if not self.frame_path.exists():
            raise FileNotFoundError(f"Moldura não encontrada: {frame_path}")
        self.video_area = video_area or {"x": 110, "y": 235, "w": 500, "h": 890}
        self.crf = crf
        self.preset = preset
    
    @classmethod
    def from_gui(cls, frame_path: str, video_path: Optional[str] = None) -> Optional["FrameApplier"]:
        gui = FrameApplierGUI()
        result = gui.run()
        return cls(frame_path=result["frame_path"], video_area=result["video_area"]) if result else None
    
    def apply_to_video(self, video_path: str, output_path: Optional[str] = None) -> Optional[Dict]:
        video = Path(video_path)
        if not video.exists():
            print(f"❌ Vídeo não encontrado: {video_path}")
            return None
        if output_path is None:
            output_path = video.parent / f"{video.stem}_framed{video.suffix}"
        output = Path(output_path)
        va = self.video_area
        # input 0 = moldura (em loop, pois é uma imagem estática) -> FUNDO em 720x1280
        # input 1 = vídeo -> redimensionado para a área da GUI e sobreposto POR CIMA
        #
        # IMPORTANTE: usamos force_original_aspect_ratio=increase + crop (em vez de
        # "decrease") para que o vídeo SEMPRE preencha 100% da área w x h configurada
        # na GUI, recortando o excesso de forma centralizada. Com "decrease" o vídeo
        # apenas "encaixa" dentro da área sem cortar — se a proporção do clipe não for
        # idêntica à proporção da caixa verde (que pode ser redimensionada livremente),
        # sobra um vão vazio ancorado no canto superior-esquerdo, e o vídeo parece
        # "deslocado" para a direita ou para baixo dependendo do clipe. increase+crop
        # elimina essa ambiguidade: a posição e o tamanho finais são sempre exatos.
        # shortest=1 garante que o vídeo (finito) determine a duração final,
        # já que a moldura em loop nunca chega ao fim por conta própria.
        filter_complex = (
            f"[0:v]scale=720:1280[bg];"
            f"[1:v]scale={va['w']}:{va['h']}:force_original_aspect_ratio=increase,"
            f"crop={va['w']}:{va['h']}[vid];"
            f"[bg][vid]overlay={va['x']}:{va['y']}:shortest=1[out]"
        )
        cmd = ["ffmpeg", "-loop", "1", "-i", str(self.frame_path), "-i", str(video),
            "-filter_complex", filter_complex, "-map", "[out]", "-map", "1:a?",
            "-c:v", "libx264", "-preset", self.preset, "-crf", str(self.crf),
            "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k",
            "-movflags", "+faststart", "-y", str(output)]
        print(f"   🖼️  {video.name}", end=" ")
        try:
            subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
            if output.exists() and output.stat().st_size > 0:
                size_mb = output.stat().st_size / (1024 * 1024)
                print(f"✅ {size_mb:.1f} MB")
                return {"filename": output.name, "path": str(output), "size_mb": round(size_mb, 2), "frame_applied": True}
        except subprocess.CalledProcessError as e:
            print(f"❌ Erro: {e.stderr[-200:]}")
        return None
    
    def apply_to_all(self, video_paths: List[str], output_dir: Optional[str] = None,
                    remove_originals: bool = True) -> List[Dict]:
        output_dir = Path(output_dir) if output_dir else Path(video_paths[0]).parent
        output_dir.mkdir(parents=True, exist_ok=True)
        va = self.video_area
        print(f"\n{'='*60}")
        print(f"🖼️  APLICANDO MOLDURA A {len(video_paths)} VÍDEOS")
        print(f"{'='*60}")
        print(f"   Moldura: {self.frame_path.name}")
        print(f"   Área: {va['w']}×{va['h']} em ({va['x']},{va['y']})")
        print("-" * 60)
        results = []
        for i, vp in enumerate(video_paths, 1):
            vp = Path(vp)
            output = output_dir / f"{vp.stem}_framed{vp.suffix}"
            print(f"   🎬 {i}/{len(video_paths)}:", end=" ")
            r = self.apply_to_video(str(vp), str(output))
            if r:
                results.append(r)
                if remove_originals and vp != output:
                    try: vp.unlink()
                    except: pass
        if remove_originals:
            print(f"\n   🗑️  {len(results)} originais removidos")
        print(f"\n✅ {len(results)}/{len(video_paths)} vídeos processados")
        return results
def main():
    print("\n🖱️  Abrindo configurador de moldura...")
    gui = FrameApplierGUI()
    result = gui.run()
    if result is None:
        print("\n⚠️  Cancelado.")
        return
    applier = FrameApplier(frame_path=result["frame_path"], video_area=result["video_area"])
    applier.apply_to_all(video_paths=result["videos"], remove_originals=True)
if __name__ == "__main__":
    main()