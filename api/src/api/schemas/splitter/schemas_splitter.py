
from pydantic import BaseModel, Field

class CutRequest(BaseModel):
    video_path: str = Field(..., description="Caminho do vídeo a ser cortado")
    num_clipes: int = Field(3, ge=1, le=30, description="Número de clipes")
    duracao: int = Field(90, ge=10, le=300, description="Duração de cada clipe em segundos")
    zoom: float = Field(1.15, ge=0.5, le=2.0, description="Fator de zoom (1.0=normal, 1.15=15% menos zoom)")
    com_gancho: bool = Field(True, description="Extrair e adicionar gancho/introdução")
    formato: str = Field("9:16", description="Formato de saída (9:16 ou 16:9)")

class ClipeInfo(BaseModel):
    clip_id: int
    filename: str
    path: str
    start: float
    end: float
    duration: float
    size_mb: float
    resolution: str

class CutResponse(BaseModel):
    status: str
    mensagem: str
    total_clipes: int
    clipes: list = []