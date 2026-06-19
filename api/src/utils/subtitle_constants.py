# ── Cores ASS ──────────────────────────────────────────────────
# Formato ASS: &HAABBGGRR& (alpha, blue, green, red — invertido)
COLORS = {
    "white": "&H00FFFFFF&",  # branco puro
    "yellow": "&H0000FFFF&",  # amarelo vibrante
    "blue": "&H00FF5500&",  # azul vivo
    "green": "&H0055FF55&",  # verde vibrante
    "black": "&H00000000&",  # preto
}

# Mapeamento de nomes do app → chave interna
COR_MAP = {
    "white": "white",
    "yellow": "yellow",
    "blue": "blue",
    "green": "green",
    "branco": "white",
    "amarelo": "yellow",
    "azul": "blue",
    "verde": "green",
}

# Cor padrão — branco com destaque amarelo nas palavras longas
DEFAULT_COR = "white"

# ── Censura ───────────────────────────────────────────────────
BAD_WORDS = {
    "suicidio": "sui***",
    "morte": "mo**e",
    "matar": "ma**r",
    "puta": "p**a",
    "caralho": "ca****o",
    "porra": "p***a",
    "viado": "vi***",
    "bicha": "bi***",
    "vagabundo": "vaga****o",
    "vagabunda": "vaga****a",
    "cú": "c*",
}

# ── Emojis ────────────────────────────────────────────────────
EMOJI_WORDS = {
    "amor": "❤️",
    "amo": "❤️",
    "paixão": "🔥",
    "apaixonado": "🔥",
    "feliz": "😊",
    "felicidade": "✨",
    "alegria": "🎉",
    "rir": "😂",
    "risos": "😂",
    "kkk": "😂",
    "kkkk": "😂",
    "haha": "😄",
    "gargalhada": "🤣",
    "dinheiro": "💰",
    "rico": "💸",
    "riqueza": "💎",
    "sucesso": "🚀",
    "vencer": "🏆",
    "vitória": "🥇",
    "ganhar": "🎯",
    "comida": "🍔",
    "fome": "🍽️",
    "comer": "🍕",
    "bebida": "🥤",
    "café": "☕",
    "cerveja": "🍺",
    "muito": "⚡",
    "demais": "💥",
    "caramba": "😮",
    "nossa": "😲",
    "uau": "✨",
    "top": "👑",
    "brabo": "🐐",
    "craque": "⭐",
    "gênio": "🧠",
    "mito": "🏛️",
    "lenda": "📜",
    "música": "🎵",
    "dançar": "💃",
    "funk": "🎧",
    "trap": "🎤",
    "beat": "🥁",
    "gol": "⚽",
    "jogar": "🎮",
    "jogo": "🎲",
    "casa": "🏠",
    "praia": "🏖️",
    "festa": "🎊",
    "role": "🎪",
    "balada": "🪩",
    "cachorro": "🐶",
    "gato": "🐱",
    "leão": "🦁",
    "tubarão": "🦈",
    "deus": "🙏",
    "amém": "🙌",
    "fé": "✨",
    "sorte": "🍀",
    "azar": "💔",
    "força": "💪",
    "foco": "🎯",
}


