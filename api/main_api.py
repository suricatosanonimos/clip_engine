"""
╔══════════════════════════════════════════════════════════════════╗
║  CLIP ENGINE — FastAPI                                           ║
╠══════════════════════════════════════════════════════════════════╣
║  Rotas:                                                          ║
║  POST /api/video/process          → dispara pipeline completo   ║
║  GET  /api/status/{task_id}       → polling do progresso        ║
║  POST /api/info/                  → info do vídeo (yt-dlp)      ║
║  POST /api/info/titles            → títulos virais (Brain IA)   ║
║  POST /api/transcription/         → Whisper + Brain IA          ║
╠══════════════════════════════════════════════════════════════════╣
║  Estrutura esperada:                                             ║
║  clip_engine/                                                    ║
║  ├── app/          ← Flet                                        ║
║  └── api/                                                        ║
║      ├── main_api.py   ← este arquivo                           ║
║      └── src/                                                    ║
║          ├── api/routes/                                         ║
║          ├── controllers/                                        ║
║          ├── services/                                           ║
║          ├── config/                                             ║
║          └── utils/                                              ║
╠══════════════════════════════════════════════════════════════════╣
║  Iniciar:                                                        ║
║  cd clip_engine/api                                              ║
║  uvicorn main_api:app --reload --host 0.0.0.0 --port 8000       ║
╚══════════════════════════════════════════════════════════════════╝
"""

import sys
from pathlib import Path

# Garante que `src` seja encontrado independente de onde o processo é iniciado.
# Após mover para clip_engine/api/, este arquivo fica em:
#   clip_engine/api/main_api.py
# e os módulos em:
#   clip_engine/api/src/controllers, src/services, etc.
ROOT_DIR = Path(__file__).resolve().parent          # clip_engine/api/
SRC_DIR  = ROOT_DIR / "src"                         # clip_engine/api/src/

if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

# ── imports das rotas (agora `src` está no path) ──────────────────
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.routes.info          import router as info_router
from src.api.routes.status        import router as status_router
from src.api.titles.transcription import router as transcription_router
from src.api.routes.upload       import router as upload_router
from src.api.routes.video         import router as video_router

# ──────────────────────────────────────────────────────────────────
#  APP
# ──────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Clip Engine API",
    description=(
        "API para processamento automático de vídeos do YouTube em clipes "
        "para Shorts/Reels com tracking de rostos, legendas e análise de IA."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# ──────────────────────────────────────────────────────────────────
#  CORS — libera o app Flet (e qualquer origem em dev)
# ──────────────────────────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],        # em produção troque pelo domínio do app
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ──────────────────────────────────────────────────────────────────
#  ROUTERS
# ──────────────────────────────────────────────────────────────────

app.include_router(video_router,         prefix="/api")
app.include_router(upload_router,        prefix="/api")
app.include_router(status_router,        prefix="/api")
app.include_router(info_router,          prefix="/api")
app.include_router(transcription_router, prefix="/api")

# ──────────────────────────────────────────────────────────────────
#  HEALTH CHECK
# ──────────────────────────────────────────────────────────────────

@app.get("/", tags=["Health"])
async def root():
    return {"status": "ok", "app": "Clip Engine API", "version": "1.0.0"}


@app.get("/health", tags=["Health"])
async def health():
    return {"status": "healthy"}


# ──────────────────────────────────────────────────────────────────
#  ENTRYPOINT
# ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main_api:app", host="0.0.0.0", port=8000, reload=True)
