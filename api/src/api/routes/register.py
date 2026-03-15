"""
Rota de registro de usuários - Clip Engine API
"""

from typing import Dict, Any
from fastapi import APIRouter, HTTPException, status, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from src.api.schemas import RegisterUser
from src.database.supabase_client import register_user
import asyncio

router = APIRouter(prefix='/auth', tags=['Autenticação'])


@router.post(
    '/register',
    status_code=status.HTTP_201_CREATED,
    response_model=Dict[str, Any],
    summary="Registrar novo usuário",
    description="Cria uma nova conta de usuário no Supabase Auth"
)
async def register_user_endpoint(data: RegisterUser) -> Dict[str, Any]:
    """
    Registra um novo usuário no sistema.

    - **nome**: Nome completo do usuário
    - **email**: Email válido do usuário
    - **senha**: Senha com mínimo de 6 caracteres

    Retorna os dados do usuário criado e tokens de acesso.
    """
    try:
        # Registro normal sem admin
        response = await register_user(
            email=data.email,
            password=data.senha,
            full_name=data.nome
        )

        # Verifica se o registro foi bem-sucedido
        if not response.user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Erro ao criar usuário"
            )

        # Converte datetime para string se necessário
        created_at = response.user.created_at
        if hasattr(created_at, 'isoformat'):
            created_at = created_at.isoformat()

        # Retorna resposta formatada
        return {
            "success": True,
            "message": "Usuário criado com sucesso! Verifique seu email para confirmar a conta.",
            "user": {
                "id": response.user.id,
                "email": data.email,
                "nome": data.nome,
                "created_at": created_at
            },
            "session": {
                "access_token": response.session.access_token if response.session else None,
                "refresh_token": response.session.refresh_token if response.session else None,
                "expires_in": response.session.expires_in if response.session else None
            } if response.session else None
        }

    except Exception as e:
        error_msg = str(e).lower()

        # Tratamento específico para rate limit
        if "429" in str(e) or "too many requests" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Muitas tentativas. Aguarde alguns minutos e tente novamente."
            )
        # Tratamento específico para erros comuns do Supabase
        elif "already registered" in error_msg or "already exists" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Este email já está cadastrado"
            )
        elif "password" in error_msg and "weak" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Senha muito fraca. Use uma combinação de letras, números e símbolos"
            )
        elif "email" in error_msg and "invalid" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email inválido"
            )
        else:
            # Erro genérico
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Erro interno no servidor: {str(e)[:100]}"
            )

