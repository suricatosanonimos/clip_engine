"""
Modelos de dados da aplicação.
"""

from dataclasses import dataclass, field


@dataclass
class ClipSugerido:
    id: int
    titulo: str
    inicio: str
    fim: str
    duracao: str
    score: float  # 0.0 a 1.0
    motivo: str
    status: str = "pendente"  # pendente | renderizando | pronto | erro
    progresso: float = 0.0


@dataclass
class Projeto:
    id: int
    url: str
    titulo: str
    duracao: str
    status: str = "aguardando"
    progresso_geral: float = 0.0
    clipes: list = field(default_factory=list)
