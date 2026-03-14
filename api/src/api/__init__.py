from .routes.video import router as video_router
from .routes.status import router as status_router
from .routes.info import router as info_router
from .routes.upload import router as upload_router
from .titles.transcription import router as transcription_router

__all__ = [
    "video_router",
    "status_router",
    "info_router",
    "transcription_router",
]
