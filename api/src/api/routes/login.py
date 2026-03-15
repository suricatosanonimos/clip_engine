"""
Rota de login de usuários - Clip Engine API
"""

from typing import Dict, Any
from fastapi import APIRouter, HTTPException, status, Request
from src.api.schemas import LoginUser, AuthResponse
from src.database.supabase_client import login_user

router = APIRouter(prefix='/auth', tags=['Autenticação'])


@router.post(
    '/login',
    status_code=status.HTTP_200_OK,
    response_model=AuthResponse,
    summary="Login de usuário",
    description="Autentica um usuário com email e senha"
)
async def login_endpoint(data: LoginUser) -> Dict[str, Any]:
    """
    Realiza o login do usuário no sistema.

    - **email**: Email do usuário
    - **senha**: Senha do usuário

    Retorna os dados do usuário e tokens de acesso.
    """
    # Validação básica
    if isinstance(data, dict):
        if not data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Dados de login não fornecidos"
            )

    try:
        # Chama a função de login do Supabase
        response = await login_user(
            email=data.email,
            password=data.senha
        )

        # Verifica se o login foi bem-sucedido
        if not response.user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Credenciais inválidas"
            )

        # Retorna resposta formatada
        return {
            "success": True,
            "message": "Login realizado com sucesso!",
            "user": {
                "id": response.user.id,
                "email": response.user.email,
                "nome": response.user.user_metadata.get('full_name', ''),
                "avatar_url": response.user.user_metadata.get('avatar_url'),
                "created_at": response.user.created_at
            },
            "session": {
                "access_token": response.session.access_token,
                "refresh_token": response.session.refresh_token,
                "expires_in": response.session.expires_in
            }
        }

    except Exception as e:
        error_msg = str(e).lower()

        # Tratamento específico para erros comuns do Supabase
        if "invalid login credentials" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Email ou senha incorretos"
            )
        elif "email not confirmed" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Email não confirmado. Verifique sua caixa de entrada"
            )
        elif "user not found" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Usuário não encontrado"
            )
        else:
            # Erro genérico
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Erro interno no servidor: {str(e)[:100]}"
            )


@router.post(
    '/login/test',
    status_code=status.HTTP_200_OK,
    summary="Endpoint de teste para login",
    description="Apenas para testar se a rota está funcionando"
)
async def test_login():
    """Endpoint de teste para verificar se a rota está acessível"""
    return {
        "message": "Rota de login funcionando!",
        "status": "OK",
        "endpoints": {
            "login": "/auth/login",
            "register": "/auth/register",
            "google": "/auth/google"
        }
    }
