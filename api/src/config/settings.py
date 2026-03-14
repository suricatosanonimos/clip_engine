import os
import shutil
import sys
from typing import Optional


class ConfigFmmpeg:
    def __init__(self, preset: Optional[str] = "slow") -> None:
        # Códigos ANSI para estilização
        self._BLUE_BG = "\033[44;37m"  # Fundo azul com texto branco
        self._RESET = "\033[0m"  # Reseta para o padrão do terminal

        # Config default
        self.codec_video = "-c:v libx264"
        self.crf = "18"  # recomendados entre 18 e 28 (quanto menor, maior a qualidade).
        self.preset = preset or "slow"  # Opções: ultrafast slow
        self.codec_audio = "-c:a aac"
        self.bitrate_audio = "-b:a 320k"
        self.debug = "-ss 00:00:00 -to 00:00:10"

    def _fmmpeg_existe(self):

        if sys.platform == "linux":
            command_ffmpeg = "/usr/bin/ffmpeg"

        return os.path.isfile(command_ffmpeg) if command_ffmpeg else False

    def get_config(self):
        return {
            "path_ffmpeg": shutil.which("ffmpeg"),
            "codec_video": self.codec_video,
            "crf": self.crf,
            "preset": self.preset,
            "codec_audio": self.codec_audio,
            "bitrate_audio": self.bitrate_audio,
            "debug": self.debug,
        }


class Colors:
    """Cores ANSI para estilização do terminal"""

    # Estilos de texto
    BOLD = "\033[1m"
    UNDERLINE = "\033[4m"
    ITALIC = "\033[3m"
    RESET = "\033[0m"

    # Cores de texto (foreground)
    BLACK = "\033[30m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"

    # Cores brilhantes (texto)
    BRIGHT_BLACK = "\033[90m"
    BRIGHT_RED = "\033[91m"
    BRIGHT_GREEN = "\033[92m"
    BRIGHT_YELLOW = "\033[93m"
    BRIGHT_BLUE = "\033[94m"
    BRIGHT_MAGENTA = "\033[95m"
    BRIGHT_CYAN = "\033[96m"
    BRIGHT_WHITE = "\033[97m"

    # Cores de fundo (background)
    BG_BLACK = "\033[40m"
    BG_RED = "\033[41m"
    BG_GREEN = "\033[42m"
    BG_YELLOW = "\033[43m"
    BG_BLUE = "\033[44m"
    BG_MAGENTA = "\033[45m"
    BG_CYAN = "\033[46m"
    BG_WHITE = "\033[47m"

    # Cores de fundo brilhantes
    BG_BRIGHT_BLACK = "\033[100m"
    BG_BRIGHT_RED = "\033[101m"
    BG_BRIGHT_GREEN = "\033[102m"
    BG_BRIGHT_YELLOW = "\033[103m"
    BG_BRIGHT_BLUE = "\033[104m"
    BG_BRIGHT_MAGENTA = "\033[105m"
    BG_BRIGHT_CYAN = "\033[106m"
    BG_BRIGHT_WHITE = "\033[107m"

    # Combinações úteis (texto + fundo)
    SUCCESS = f"{GREEN}{BG_BLACK}"  # Verde no fundo preto
    ERROR = f"{RED}{BG_BLACK}"  # Vermelho no fundo preto
    WARNING = f"{YELLOW}{BG_BLACK}"  # Amarelo no fundo preto
    INFO = f"{BLUE}{BG_BLACK}"  # Azul no fundo preto

    # Combinações com fundo colorido
    SUCCESS_BG = f"{BLACK}{BG_GREEN}"  # Texto preto no fundo verde
    ERROR_BG = f"{WHITE}{BG_RED}"  # Texto branco no fundo vermelho
    WARNING_BG = f"{BLACK}{BG_YELLOW}"  # Texto preto no fundo amarelo
    INFO_BG = f"{WHITE}{BG_BLUE}"  # Texto branco no fundo azul

    @staticmethod
    def colorize(text: str, color: str, bg_color: str = "") -> str:
        """
        Aplica cores a um texto

        Args:
            text: Texto a ser colorido
            color: Cor do texto (ex: Colors.RED)
            bg_color: Cor de fundo (opcional)

        Returns:
            Texto colorido
        """
        return f"{color}{bg_color}{text}{Colors.RESET}"

    @staticmethod
    def success(text: str) -> str:
        """Retorna texto em verde (sucesso)"""
        return f"{Colors.GREEN}{text}{Colors.RESET}"

    @staticmethod
    def error(text: str) -> str:
        """Retorna texto em vermelho (erro)"""
        return f"{Colors.RED}{text}{Colors.RESET}"

    @staticmethod
    def warning(text: str) -> str:
        """Retorna texto em amarelo (aviso)"""
        return f"{Colors.YELLOW}{text}{Colors.RESET}"

    @staticmethod
    def info(text: str) -> str:
        """Retorna texto em azul (informação)"""
        return f"{Colors.BLUE}{text}{Colors.RESET}"

    @staticmethod
    def success_bg(text: str) -> str:
        """Retorna texto com fundo verde"""
        return f"{Colors.BG_GREEN}{Colors.BLACK}{text}{Colors.RESET}"

    @staticmethod
    def error_bg(text: str) -> str:
        """Retorna texto com fundo vermelho"""
        return f"{Colors.BG_RED}{Colors.WHITE}{text}{Colors.RESET}"

    @staticmethod
    def warning_bg(text: str) -> str:
        """Retorna texto com fundo amarelo"""
        return f"{Colors.BG_YELLOW}{Colors.BLACK}{text}{Colors.RESET}"

    @staticmethod
    def info_bg(text: str) -> str:
        """Retorna texto com fundo azul"""
        return f"{Colors.BG_BLUE}{Colors.WHITE}{text}{Colors.RESET}"

    @staticmethod
    def bold(text: str) -> str:
        """Retorna texto em negrito"""
        return f"{Colors.BOLD}{text}{Colors.RESET}"

    @staticmethod
    def underline(text: str) -> str:
        """Retorna texto sublinhado"""
        return f"{Colors.UNDERLINE}{text}{Colors.RESET}"

    @staticmethod
    def progress_bar(percent: float, width: int = 30) -> str:
        """
        Cria uma barra de progresso colorida

        Args:
            percent: Percentual (0-100)
            width: Largura da barra em caracteres

        Returns:
            Barra de progresso colorida
        """
        filled = int(width * percent / 100)
        bar = "█" * filled + "░" * (width - filled)

        if percent < 50:
            color = Colors.RED
        elif percent < 80:
            color = Colors.YELLOW
        else:
            color = Colors.GREEN

        return f"{color}{bar}{Colors.RESET} {percent:.1f}%"
