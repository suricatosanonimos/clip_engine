"""
src/controllers/whisper/__init__.py

Carregamento do modelo Whisper para transcrição de áudio.
Com verificação de modelos instalados e interface amigável.
"""

import os
import sys
from pathlib import Path
from typing import Optional, List, Tuple

ROOT_DIR = Path(__file__).resolve().parent.parent.parent.parent
sys.path.append(str(ROOT_DIR))


from faster_whisper import WhisperModel
from src.utils.logs import logger


# ── Cores ANSI (sem dependência externa) ──
class Colors:
    """Cores ANSI para terminal (fallback se settings.py não disponível)"""

    BOLD = "\033[1m"
    RESET = "\033[0m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"
    BG_BLUE = "\033[44m"
    BG_GREEN = "\033[42m"
    BG_RED = "\033[41m"
    BG_YELLOW = "\033[43m"
    BG_MAGENTA = "\033[45m"
    BG_CYAN = "\033[46m"
    BG_BLACK = "\033[40m"
    BRIGHT_WHITE = "\033[97m"
    BLACK = "\033[30m"

    @staticmethod
    def success(text: str) -> str:
        return f"{Colors.GREEN}{text}{Colors.RESET}"

    @staticmethod
    def error(text: str) -> str:
        return f"{Colors.RED}{text}{Colors.RESET}"

    @staticmethod
    def warning(text: str) -> str:
        return f"{Colors.YELLOW}{text}{Colors.RESET}"

    @staticmethod
    def info(text: str) -> str:
        return f"{Colors.CYAN}{text}{Colors.RESET}"

    @staticmethod
    def bold(text: str) -> str:
        return f"{Colors.BOLD}{text}{Colors.RESET}"

    @staticmethod
    def header(text: str) -> str:
        return (
            f"{Colors.BG_BLUE}{Colors.BRIGHT_WHITE}{Colors.BOLD} {text} {Colors.RESET}"
        )

    @staticmethod
    def highlight(text: str) -> str:
        return f"{Colors.BG_MAGENTA}{Colors.WHITE}{Colors.BOLD} {text} {Colors.RESET}"


# Importa Colors do settings se disponível
try:
    from src.config.settings import Colors as SettingsColors

    Colors = SettingsColors
except ImportError:
    pass

# Configuração
CACHE_DIR = Path.home() / ".cache" / "whisper-models"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# Singleton
_MODEL = None

# ── Modelos disponíveis ──
AVAILABLE_MODELS = {
    "tiny": {
        "size": "~75 MB",
        "speed": "⚡⚡⚡⚡⚡ (muito rápido)",
        "accuracy": "⭐⭐ (baixa)",
        "vram": "~1 GB",
        "recommended": "Testes rápidos, áudio limpo",
    },
    "tiny.en": {
        "size": "~75 MB",
        "speed": "⚡⚡⚡⚡⚡ (muito rápido)",
        "accuracy": "⭐⭐ (baixa, apenas inglês)",
        "vram": "~1 GB",
        "recommended": "Inglês apenas, testes",
    },
    "base": {
        "size": "~145 MB",
        "speed": "⚡⚡⚡⚡ (rápido)",
        "accuracy": "⭐⭐⭐ (média)",
        "vram": "~1 GB",
        "recommended": "Uso geral, qualidade razoável",
    },
    "small": {
        "size": "~488 MB",
        "speed": "⚡⚡⚡ (moderado)",
        "accuracy": "⭐⭐⭐⭐ (boa)",
        "vram": "~2 GB",
        "recommended": "Bom equilíbrio qualidade/velocidade",
    },
    "medium": {
        "size": "~1.5 GB",
        "speed": "⚡⚡ (lento)",
        "accuracy": "⭐⭐⭐⭐⭐ (excelente)",
        "vram": "~5 GB",
        "recommended": "Alta qualidade, podcasts",
    },
    "large-v2": {
        "size": "~3 GB",
        "speed": "⚡ (muito lento)",
        "accuracy": "⭐⭐⭐⭐⭐ (máxima)",
        "vram": "~10 GB",
        "recommended": "Máxima precisão, servidores",
    },
    "large-v3": {
        "size": "~3 GB",
        "speed": "⚡ (muito lento)",
        "accuracy": "⭐⭐⭐⭐⭐ (máxima - melhor)",
        "vram": "~10 GB",
        "recommended": "Melhor modelo disponível",
    },
}


def _clear_screen():
    """Limpa a tela do terminal."""
    os.system("cls" if os.name == "nt" else "clear")


def _check_installed_models() -> List[str]:
    """Verifica quais modelos já estão baixados no cache."""
    if not CACHE_DIR.exists():
        return []

    installed = []
    for model_name in AVAILABLE_MODELS:
        model_dir = (
            CACHE_DIR
            / "models--Systran--faster-whisper"
            / f"faster-whisper-{model_name}"
        )
        if model_dir.exists() and any(model_dir.iterdir()):
            installed.append(model_name)

    return installed


def _print_models_table():
    """Imprime tabela formatada com modelos disponíveis."""
    installed = _check_installed_models()

    print(f"\n{Colors.success(' 📦 MODELOS WHISPER DISPONÍVEIS ')}")
    print(f"{Colors.info('   Cache:')} {CACHE_DIR}")
    print()

    # Cabeçalho
    header = "  {:<12} {:<10} {:<22} {:<18} {:<12}".format(
        "Modelo", "Tamanho", "Velocidade", "Qualidade", "Status"
    )
    print(Colors.bold(header))
    print(f"  {'─' * 74}")

    for model_name, info in AVAILABLE_MODELS.items():
        if model_name in installed:
            status = Colors.success("✅ Instalado")
        else:
            status = Colors.warning("⬇️  Não instalado")

        # Destaca modelos recomendados
        if model_name in ("base", "small"):
            prefix = "⭐ "
        else:
            prefix = "   "

        print(
            f"  {prefix}{model_name:<10} {info['size']:<10} {info['speed']:<22} {info['accuracy']:<18} {status}"
        )

    print()
    print(
        f"  {Colors.info('💡 Recomendação:')} 'base' para testes, 'small' para produção"
    )
    print(f"  {Colors.info('📝 Comando:')} model('small')  ou  model('base')")
    print()


def _print_welcome_message():
    """Imprime mensagem de boas-vindas quando nenhum modelo está instalado."""
    installed = _check_installed_models()

    if installed:
        # Já tem modelos instalados
        modelos_str = ", ".join(installed)
        print(f"\n{Colors.success('✅ Modelos instalados:')} {modelos_str}")
        return

    # Nenhum modelo instalado - mostra guia completo
    _clear_screen()

    print(f"\n{Colors.success(' 🎙️  WHISPER - PRIMEIRA CONFIGURAÇÃO  ')}")
    print()
    print(f"  {Colors.bold('Bem-vindo ao sistema de transcrição!')}")
    print(f"  {Colors.info('Nenhum modelo Whisper encontrado no cache.')}")
    print()
    print(
        f"  {Colors.warning('⚠️  Na primeira execução, o modelo será baixado automaticamente.')}"
    )
    print(
        f"  {Colors.info('   O download pode levar alguns minutos dependendo da sua conexão.')}"
    )
    print()

    _print_models_table()

    print(f"  {Colors.info(' 🚀 COMO USAR ')}")

    # Usa variáveis para evitar backslash em f-strings
    exemplo1 = "   from src.controllers.whisper import model"
    exemplo2 = '   whisper = model("base")  # ou "small", "medium", etc.'

    print(f"  {Colors.info(exemplo1)}")
    print(f"  {Colors.info(exemplo2)}")
    print()
    print(f"  {Colors.info('📂 Os modelos são salvos em:')} {CACHE_DIR}")
    print(
        f"  {Colors.info('🔄 Para trocar de modelo, basta chamar model() com outro nome.')}"
    )
    print()


def _print_model_download_progress(model_name: str):
    """Imprime indicador de progresso durante o download."""
    print(f"\n  {Colors.info('⬇️  Baixando modelo:')} {Colors.bold(model_name)}")
    print(f"  {Colors.warning('   Isso pode levar alguns minutos...')}")
    print(f"  {Colors.info('   O modelo ficará em cache para usos futuros.')}")
    print()


def load_model(model_size: str = "base") -> WhisperModel:
    """
    Carrega (ou retorna em cache) o modelo Whisper.

    Args:
        model_size: Nome do modelo (tiny, base, small, medium, large-v2, large-v3)

    Returns:
        Instância do WhisperModel pronta para uso
    """
    global _MODEL

    # Valida o modelo solicitado
    if model_size not in AVAILABLE_MODELS:
        available = ", ".join(AVAILABLE_MODELS.keys())
        logger.error(f"Modelo '{model_size}' não encontrado. Disponíveis: {available}")
        raise ValueError(
            f"Modelo '{model_size}' inválido. Use um dos seguintes: {available}"
        )

    # Se já carregado, reutiliza
    if _MODEL is not None:
        logger.debug(f"Reutilizando modelo já carregado: {model_size}")
        return _MODEL

    # Verifica se precisa baixar
    installed = _check_installed_models()
    is_first_time = model_size not in installed

    if is_first_time:
        _print_model_download_progress(model_size)

    logger.info(f"Carregando modelo Whisper: {model_size} (primeira vez pode demorar)")

    try:
        _MODEL = WhisperModel(
            model_size,
            device="cpu",
            compute_type="int8",
            download_root=str(CACHE_DIR),
            local_files_only=False,
        )

        if is_first_time:
            size_mb = _get_model_size_mb(model_size)
            print(f"\n  {Colors.success('✅ Modelo baixado e carregado com sucesso!')}")
            msg_modelo = f"   Modelo: {model_size} (~{size_mb} MB)"
            print(f"  {Colors.info(msg_modelo)}")
            print(
                f"  {Colors.info('   Nas próximas execuções, o carregamento será instantâneo.')}"
            )

        logger.info(f"✅ Modelo carregado com sucesso: {model_size}")
        return _MODEL

    except Exception as e:
        logger.error(f"❌ Erro ao carregar modelo {model_size}: {e}")

        # Mensagem amigável de erro
        print(f"\n  {Colors.error('❌ ERRO AO CARREGAR MODELO')}")
        msg_erro = f"   {e}"
        print(f"  {Colors.warning(msg_erro)}")
        print(f"\n  {Colors.info('💡 Possíveis soluções:')}")
        print(f"  {Colors.info('   1. Verifique sua conexão com a internet')}")
        print(f"  {Colors.info('   2. Libere espaço em disco (mínimo 1-3 GB)')}")

        msg_tiny = '   3. Tente um modelo menor: model("tiny")'
        print(f"  {Colors.info(msg_tiny)}")
        print(
            f"  {Colors.info('   4. Verifique permissões de escrita em:')} {CACHE_DIR}"
        )
        raise


def _get_model_size_mb(model_name: str) -> str:
    """Retorna o tamanho estimado do modelo."""
    size_str = AVAILABLE_MODELS.get(model_name, {}).get("size", "?")
    return size_str.replace("~", "").replace(" MB", "").replace(" GB", "000")


def get_model(model_size: Optional[str] = None) -> WhisperModel:
    """
    Interface pública para obter o modelo Whisper.
    Mostra guia na primeira execução.

    Args:
        model_size: Nome do modelo. Se None, usa 'base'.

    Returns:
        Instância do WhisperModel
    """
    # Mostra mensagem de boas-vindas se nenhum modelo instalado
    installed = _check_installed_models()
    if not installed:
        _print_welcome_message()

    return load_model(model_size or "base")


def list_models():
    """Lista todos os modelos disponíveis e seu status."""
    _print_models_table()


# Para compatibilidade com código existente
model = get_model


# ══════════════════════════════════════════════════════════════
#  Ao importar o módulo, mostra status
# ══════════════════════════════════════════════════════════════
if __name__ == "__main__":
    _print_welcome_message()
    print(f"\n{Colors.info('📝 Testando carregamento do modelo base...')}")
    m = get_model("base")
    print(f"\n{Colors.success('✅ Modelo carregado! Pronto para transcrição.')}")
