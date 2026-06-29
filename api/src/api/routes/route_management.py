from fastapi import APIRouter, FastAPI
from typing import Any, Dict, List

# Metadata configuration for documentation
API_METADATA = {
    'title': 'Clip Engine API',
    'version': '1.0.0',
    'description': """
    Clip Engine - Transforme vídeos longos em Shorts e Reels automaticamente com IA.

    Main Features:
    - Face Tracking com MediaPipe em tempo real
    - Legendas Word-by-Word estilo Alex Hormozi
    - IA para encontrar os melhores momentos do vídeo
    - Processamento em pipeline com SSE em tempo real
    - Suporte a YouTube URL e upload de arquivos
    - Cloud Storage com Supabase (URLs assinadas por 7 dias)
    - App Android nativo em Flet
    - Dashboard com métricas e galeria de clipes
    """,
    'contact': {
        'name': 'Gilderlan Silva',
        'email': 'lansilva007gg@gmail.com',
        'url': 'https://github.com/suricatosanonimos/clip_engine',
    },
    'license_info': {
        'name': 'MIT',
        'url': 'https://opensource.org/licenses/MIT',
    },
    'terms_of_service': 'https://github.com/suricatosanonimos/clip_engine/blob/main/TERMS.md',
    'docs_url': '/docs',
    'redoc_url': '/redoc',
    'openapi_url': '/api/v1/openapi.json',
}


class RouterManager:
    """Centralized route manager with professional configuration"""
    
    def __init__(self) -> None:
        self.routes: Dict[str, APIRouter] = {}
        self.prefix = '/api/v1'
        self.configure_routes()

    def configure_routes(self):
        """Configures all system routes with standardized settings"""

        # -----------------------------------------------------
        #                      Video Processing
        # -----------------------------------------------------
        from src.api.routes.video_splitter import router as video_splitter
        
        video_router = APIRouter(
            prefix=self.prefix,
            tags=['video']
        )
        video_router.include_router(video_splitter)
        self.routes['video'] = video_router

    #     # -----------------------------------------------------
    #     #                      Gallery
    #     # -----------------------------------------------------
    #     from src.api.routes.gallery import router as gallery_router
        
    #     gallery = APIRouter(
    #         prefix=self.prefix,
    #         tags=['gallery']
    #     )
    #     gallery.include_router(gallery_router)
    #     self.routes['gallery'] = gallery

    #     # -----------------------------------------------------
    #     #                      Status / Health
    #     # -----------------------------------------------------
    #     from src.api.routes.status import router as status_router
        
    #     status = APIRouter(
    #         prefix=self.prefix,
    #         tags=['status']
    #     )
    #     status.include_router(status_router)
    #     self.routes['status'] = status

    #     # -----------------------------------------------------
    #     #                      Webhooks
    #     # -----------------------------------------------------
    #     from src.api.routes.webhooks import router as webhooks_router
        
    #     webhooks = APIRouter(
    #         prefix=self.prefix,
    #         tags=['webhooks']
    #     )
    #     webhooks.include_router(webhooks_router)
    #     self.routes['webhooks'] = webhooks

    #     # -----------------------------------------------------
    #     #                      Admin
    #     # -----------------------------------------------------
    #     from src.api.routes.admin import router as admin_router
        
    #     admin = APIRouter(
    #         prefix=self.prefix,
    #         tags=['admin']
    #     )
    #     admin.include_router(admin_router)
    #     self.routes['admin'] = admin

    def get_all_routers(self) -> List[APIRouter]:
        return list(self.routes.values())


# Global instance
router_manager = RouterManager()


def setup_routes(app: FastAPI):
    """Integrates all routers into the FastAPI application"""
    for router in router_manager.get_all_routers():
        app.include_router(router)
    return app


def get_api_metadata() -> Dict[str, Any]:
    return API_METADATA.copy()


__all__ = [
    'router_manager',
    'setup_routes',
    'get_api_metadata'
]