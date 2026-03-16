"""
╔══════════════════════════════════════════════════════════════════╗
║  CLIP ENGINE — FastAPI                                           ║
╠══════════════════════════════════════════════════════════════════╣
║  Rotas:                                                          ║
║  POST /api/jobs                   → cria job no banco           ║
║  GET  /api/jobs                   → lista jobs do usuário       ║
║  POST /api/video/process          → dispara pipeline completo   ║
║  POST /api/video/upload           → upload + pipeline           ║
║  GET  /api/status/{task_id}       → snapshot do progresso       ║
║  GET  /api/status/{task_id}/stream→ SSE em tempo real           ║
║  POST /api/info/                  → info do vídeo (yt-dlp)      ║
║  POST /api/info/titles            → títulos virais (Brain IA)   ║
║  GET  /api/clips                  → lista clipes do usuário     ║
║  GET  /api/clips/{clip_id}        → detalhes de um clipe        ║
║  POST /api/clips/{clip_id}/refresh-url → renova signed URL      ║
║  POST /api/auth/register          → cria conta                  ║
║  POST /api/auth/login             → login                       ║
╠══════════════════════════════════════════════════════════════════╣
║  Iniciar:                                                        ║
║  cd clip_engine/api                                              ║
║  uvicorn main_api:app --reload --host 0.0.0.0 --port 8000       ║
╚══════════════════════════════════════════════════════════════════╝
"""

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
SRC_DIR  = ROOT_DIR / "src"

if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.routes.info     import router as info_router
from src.api.routes.status   import router as status_router
from src.api.routes.upload   import router as upload_router
from src.api.routes.video    import router as video_router
from src.api.routes.register import router as register_account
from src.api.routes.login    import router as login_in_account
from src.api.routes.clips    import router as clips_video
from src.api.routes.jobs     import router as jobs_router

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

app.state.limiter = Limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ──────────────────────────────────────────────────────────────────
#  CORS
# ──────────────────────────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ──────────────────────────────────────────────────────────────────
#  ROUTERS
# ──────────────────────────────────────────────────────────────────

app.include_router(jobs_router,      prefix="/api")   #  antes dos outros
app.include_router(video_router,     prefix="/api")
app.include_router(upload_router,    prefix="/api")
app.include_router(status_router,    prefix="/api")
app.include_router(info_router,      prefix="/api")
app.include_router(register_account, prefix="/api")
app.include_router(login_in_account, prefix="/api")
app.include_router(clips_video,      prefix="/api")

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
