"""
database/supabase_client.py

Cliente Supabase para toda a aplicação.
Lê credenciais do .env na raiz do projeto (api/).

Variáveis necessárias:
  SUPABASE_URL          → URL do projeto
  SUPABASE_ANON_KEY     → chave pública (operações de usuário)
  SUPABASE_SERVICE_KEY  → service role key (operações administrativas)
                          Se não existir, usa ANON_KEY como fallback.

Para obter a SERVICE_KEY:
  Supabase dashboard → Settings → API → service_role (secret)
"""

import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from supabase import Client, create_client

# ── Carrega .env da raiz de api/ ──────────────────────────────────
_env_path = Path(__file__).resolve().parent.parent.parent / ".env"
load_dotenv(dotenv_path=_env_path)

SUPABASE_URL         = os.getenv("SUPABASE_URL",         "")
SUPABASE_ANON_KEY    = os.getenv("SUPABASE_ANON_KEY",    "")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "")

# ── Singleton para cliente anon ───────────────────────────────────
_client_anon: Optional[Client] = None


def get_supabase_client() -> Client:
    """
    Retorna cliente Supabase com chave anon (singleton).
    Usado para operações vinculadas ao usuário autenticado.
    """
    global _client_anon
    if _client_anon is None:
        if not SUPABASE_URL:
            raise ValueError("SUPABASE_URL não encontrada no .env")
        if not SUPABASE_ANON_KEY:
            raise ValueError("SUPABASE_ANON_KEY não encontrada no .env")
        _client_anon = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
        print("✅ Cliente Supabase (anon) inicializado")
    return _client_anon


def get_supabase_admin_client() -> Client:
    """
    Retorna cliente Supabase com service role key.
    Usado para operações administrativas: inserir em public.clips,
    atualizar public.jobs, upload para Storage, etc.

    Se SUPABASE_SERVICE_KEY não estiver no .env, usa ANON_KEY como fallback
    (funciona para desenvolvimento, mas perde acesso a dados protegidos por RLS).
    """
    if not SUPABASE_URL:
        raise ValueError("SUPABASE_URL não encontrada no .env")

    key = SUPABASE_SERVICE_KEY or SUPABASE_ANON_KEY
    if not key:
        raise ValueError("Nenhuma chave Supabase encontrada no .env")

    if not SUPABASE_SERVICE_KEY:
        print("⚠️  SUPABASE_SERVICE_KEY não encontrada — usando ANON_KEY como fallback.")
        print("    Adicione a SERVICE_KEY no .env para operações administrativas completas.")

    return create_client(SUPABASE_URL, key)


# ──────────────────────────────────────────────────────────────────
#  AUTH — funções de conveniência
# ──────────────────────────────────────────────────────────────────

async def register_user(email: str, password: str, full_name: str = None):
    """Cria um novo usuário no Supabase Auth."""
    client  = get_supabase_client()
    options = {"data": {"full_name": full_name}} if full_name else {}
    return client.auth.sign_up({
        "email":    email,
        "password": password,
        "options":  options,
    })


async def login_user(email: str, password: str):
    """Faz login com e-mail e senha."""
    client = get_supabase_client()
    return client.auth.sign_in_with_password({
        "email":    email,
        "password": password,
    })


async def logout(token: str = None):
    """Faz logout do usuário atual."""
    return get_supabase_client().auth.sign_out()


async def get_usuario_atual(token: str = None):
    """Retorna o usuário atualmente logado."""
    return get_supabase_client().auth.get_user()


async def login_com_google(redirect_to: str = None):
    """Inicia login com Google OAuth."""
    client  = get_supabase_client()
    options = {"redirect_to": redirect_to} if redirect_to else {}
    return client.auth.sign_in_with_oauth({
        "provider": "google",
        "options":  options,
    })


async def resetar_senha(email: str, redirect_to: str = None):
    """Envia e-mail para reset de senha."""
    client  = get_supabase_client()
    options = {"redirect_to": redirect_to} if redirect_to else {}
    return client.auth.reset_password_for_email(email, options)


async def refresh_token(refresh_token: str):
    """Renova o token de acesso."""
    return get_supabase_client().auth.refresh_session(refresh_token)


async def deletar_usuario(user_id: str):
    """Deleta um usuário (requer service role key)."""
    return get_supabase_admin_client().auth.admin.delete_user(user_id)


async def listar_usuarios():
    """Lista todos os usuários (requer service role key)."""
    return get_supabase_admin_client().auth.admin.list_users()
