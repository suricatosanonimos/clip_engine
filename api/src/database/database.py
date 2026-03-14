"""
Configuração da conexão com Supabase via Tortoise ORM
URL: https://uxnszfuxwxemlcgsdtaa.supabase.co
"""

from tortoise import Tortoise
import os
from dotenv import load_dotenv
import ssl

load_dotenv()

# Extraindo informações da URL do Supabase
# URL: https://uxnszfuxwxemlcgsdtaa.supabase.co
SUPABASE_PROJECT_ID = "uxnszfuxwxemlcgsdtaa"
SUPABASE_REGION = "aws"  # Ajuste conforme sua região

# Configuração da conexão com o banco PostgreSQL do Supabase
DATABASE_CONFIG = {
    "connections": {
        "default": {
            "engine": "tortoise.backends.asyncpg",
            "credentials": {
                "host": f"db.{SUPABASE_PROJECT_ID}.supabase.co",  # Host correto do banco
                "port": 5432,
                "user": "postgres",  # Usuário padrão do Supabase
                "password": os.getenv("SUPABASE_DB_PASSWORD"),  # Senha do banco (não é a anon key)
                "database": "postgres",
                "ssl": True,  # Supabase requer SSL
                "ssl_context": ssl.create_default_context(),  # Contexto SSL padrão
                "command_timeout": 60,
                "max_size": 20,  # Pool de conexões
                "min_size": 5,
            }
        }
    },
    "apps": {
        "models": {
            "models": ["src.models", "aerich.models"],
            "default_connection": "default",
        }
    },
    "use_tz": True,
    "timezone": "UTC"
}


async def init_db():
    """Inicializa conexão com o banco"""
    try:
        # IMPORTANTE: Para usar o Tortoise ORM, você precisa da senha do banco PostgreSQL
        # A SUPABASE_ANON_KEY é para a API REST, NÃO para o banco direto
        # Você precisa pegar a senha do banco em:
        # Supabase Dashboard -> Project Settings -> Database -> Password

        await Tortoise.init(config=DATABASE_CONFIG)

        # Verifica conexão
        conn = Tortoise.get_connection("default")
        await conn.execute_query("SELECT 1")

        print("✅ Conectado ao Supabase PostgreSQL via Tortoise ORM")
        print(f"📊 Projeto: {SUPABASE_PROJECT_ID}")

        # Em desenvolvimento, pode gerar schemas automaticamente
        if os.getenv("ENVIRONMENT") == "development":
            print("🔄 Gerando schemas...")
            await Tortoise.generate_schemas()
            print("✅ Schemas gerados com sucesso")

    except Exception as e:
        print(f"❌ Erro ao conectar ao banco: {e}")
        print("\n⚠️  IMPORTANTE: Você precisa configurar a senha do banco PostgreSQL!")
        print("1. Acesse: https://app.supabase.com/project/uxnszfuxwxemlcgsdtaa/settings/database")
        print("2. Em 'Database Settings' -> 'Connection string'")
        print("3. Use a senha que aparece em 'Password'")
        print("4. Adicione no arquivo .env: SUPABASE_DB_PASSWORD=sua_senha_aqui")
        raise


async def close_db():
    """Fecha conexão com o banco"""
    await Tortoise.close_connections()
    print("🔌 Conexões com banco fechadas")
