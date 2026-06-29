import uvicorn
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# logs in terminal
from src.utils.logs import logger as LOGGER

from fastapi import FastAPI
from contextlib import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

# rotas
from src.api.routes.route_management import setup_routes, get_api_metadata


# Import das funções de banco (serão implementadas depois)
async def init_database():
    """Inicializa o banco de dados."""
    # TODO: Implementar conexão com Supabase
    LOGGER.info('🔄 Inicializando conexão com Supabase...')
    return True

async def close_database():
    """Fecha a conexão com o banco de dados."""
    # TODO: Implementar fechamento da conexão
    LOGGER.info('🔒 Conexão com Supabase finalizada.')


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gerencia o ciclo de vida da aplicação."""
    load_dotenv()

    # Inicializa banco usando a nova configuração
    try:
        if await init_database():
            LOGGER.info('[200] Carregando dados inicias')
        else:
            LOGGER.error('[200] Falha ao inicializar')
    except Exception as e:
        LOGGER.error(f'[500] Erro crítico ao tentar iniciar a aplicação: {e}')

    yield

    await close_database()
    LOGGER.info('[200] API finalizada com sucesso.')


class Server:
    def __init__(self) -> None:
        metadata = get_api_metadata()
        if callable(metadata):
            metadata = metadata()

        self.api = FastAPI(**metadata, lifespan=lifespan)

        self.setup_middlewares()
        self.start_routes()

    def setup_middlewares(self):
        """Configura CORS."""
        origins = [
            'http://127.0.0.1:5000',
            'http://localhost:5173',
            'http://localhost:3000',
            'https://clipengine.kinghost.net',
            'https://www.clipengine.kinghost.net',
            'https://clip-engine.vercel.app',
            '*',  # Adicionado * para facilitar desenvolvimento, remova em produção.
        ]

        self.api.add_middleware(
            CORSMiddleware,
            allow_origins=origins,
            allow_credentials=True,
            allow_methods=['GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'OPTIONS'],
            allow_headers=['*'],
        )

    def start_routes(self):
        """Registra as rotas principais da aplicação."""
        setup_routes(self.api)

    def run(self, host: str = '0.0.0.0', port: int = 8000):
        """Inicia o servidor Uvicorn."""
        environment = os.getenv('INITIALIZE_MODE', 'development')

        # Configurações básicas do servidor
        start = {
            'development': {
                'app': 'main_api:app',
                'host': host,
                'port': port,
                'reload': True,
                'log_level': 'info',
                'access_log': True,
                'use_colors': True,
            },
            'production': {
                'app': 'main_api:app',
                'host': host,
                'port': port,
                'reload': False,
                'log_level': 'warning',
                'workers': int(os.getenv('WORKERS', 1)),
            },
        }

        if environment == 'DEVELOPMENT':
            LOGGER.info('🔧 Modo: Desenvolvimento ATIVO')
            uvicorn.run(**start.get('development'))  # type:ignore
        else:
            LOGGER.info('🚀 Modo: Produção ATIVO')
            uvicorn.run(**start.get('production'))  # type:ignore


# Instância global do app
app = Server().api


def main():
    """
    Função principal para executar o servidor Clip Engine.
    """
    LOGGER.info('-' * 60)
    LOGGER.info('🎬 Iniciando Clip Engine API...')
    LOGGER.info('📍 API disponível em: http://0.0.0.0:8000')
    LOGGER.info('📚 Documentação: http://0.0.0.0:8000/docs')
    LOGGER.info('📖 Redoc: http://0.0.0.0:8000/redoc')
    LOGGER.info('❤️  Health Check: http://0.0.0.0:8000/health')
    LOGGER.info('-' * 60)

    try:
        server = Server()
        server.run()
    except KeyboardInterrupt:
        LOGGER.info('\n🛑 Servidor interrompido pelo usuário')
    except Exception as e:
        print(f'❌ Erro ao iniciar servidor: {e}')
        LOGGER.error(f'Erro ao iniciar servidor: {e}')


if __name__ == '__main__':
    main()