# src/services/brain_IA.py
import json
import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional

from dotenv import load_dotenv
from openai import OpenAI

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(ROOT_DIR))

try:
    from src.utils.logs import logger
except ImportError:
    import logging
    logger = logging.getLogger(__name__)

load_dotenv()


class Brain:
    def __init__(self):
        self.API_KEY = os.getenv("GLOK_API")
        
        if not self.API_KEY:
            logger.warning("API_KEY não encontrada")
            self.client = None
        else:
            self.client = OpenAI(
                api_key=self.API_KEY,
                base_url="https://api.groq.com/openai/v1",
            )
        
        self.prompt_momentos = self._get_momentos_template()
        logger.info("Brain IA inicializado com sucesso")

    def _get_momentos_template(self) -> str:
        return """
        Analise a transcrição do vídeo e escolha os 3 momentos mais impactantes.

        REGRAS:
        - Cada momento deve ter entre 3 e 10 segundos de duração
        - Escolha momentos no FINAL do vídeo (últimos 30%)
        - Foque em frases que geram curiosidade
        - Retorne APENAS o JSON, sem texto antes ou depois

        Transcrição:
        {transcription}

        FORMATO:
        {"momentos": [{"inicio": 5, "fim": 12, "texto": "frase aqui", "razao": "motivo"}]}
        """

    def encontrar_melhores_momentos(
        self, transcricao: List[Dict], duracao_video: float
    ) -> Dict:
        if not self.client:
            return self._fallback_momentos(transcricao, duracao_video)

        try:
            # Limitar tamanho da transcrição (últimos 30% do vídeo)
            limite_inicio = duracao_video * 0.7
            transcricao_filtrada = [
                t for t in transcricao 
                if t.get("start", 0) >= limite_inicio
            ]
            
            if not transcricao_filtrada:
                transcricao_filtrada = transcricao[-10:]  # Últimas 10 frases
            
            transcricao_formatada = self._formatar_transcricao(transcricao_filtrada)
            
            # Limitar tamanho do texto (evitar 413 Payload Too Large)
            if len(transcricao_formatada) > 3000:
                transcricao_formatada = transcricao_formatada[:3000]
            
            prompt = self.prompt_momentos.format(transcription=transcricao_formatada)

            response = self.client.chat.completions.create(
                model="openai/gpt-oss-120b",
                messages=[
                    {"role": "system", "content": "Você é um editor de vídeos. Responda apenas com JSON válido."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.3,
                max_tokens=500,
            )

            content = response.choices[0].message.content
            resultado = self._extrair_json_robusto(content)

            if resultado and self._validar_momentos(resultado):
                return resultado

            logger.warning("JSON inválido da API, usando fallback")
            return self._fallback_momentos(transcricao, duracao_video)

        except Exception as e:
            logger.error(f"Erro na Brain IA: {e}")
            return self._fallback_momentos(transcricao, duracao_video)

    def _extrair_json_robusto(self, texto: str) -> Optional[Dict]:
        if not texto:
            return None
        try:
            return json.loads(texto.strip())
        except json.JSONDecodeError:
            match = re.search(r"(\{.*\})", texto, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group(1))
                except:
                    pass
        return None

    def _formatar_transcricao(self, transcricao: List[Dict]) -> str:
        linhas = []
        for i, item in enumerate(transcricao[:30]):  # Máximo 30 frases
            start = item.get("start", 0)
            end = item.get("end", start + 3)
            text = item.get("text", "")[:100]
            linhas.append(f"[{int(start//60):02d}:{int(start%60):02d}] {text}")
        return "\n".join(linhas)

    def _validar_momentos(self, data: Dict) -> bool:
        if not isinstance(data, dict) or "momentos" not in data:
            return False
        momentos = data.get("momentos", [])
        if not momentos:
            return False
        for m in momentos:
            if not all(k in m for k in ["inicio", "fim"]):
                return False
        return True

    def _fallback_momentos(self, transcricao: List[Dict], duracao_video: float) -> Dict:
        """Fallback: pega 3 momentos do final do vídeo"""
        logger.info("Executando Fallback de momentos")
        
        # Pega os últimos 3 trechos do final do vídeo
        momentos = []
        if transcricao:
            # Foca no final do vídeo
            ultimos = transcricao[-3:] if len(transcricao) >= 3 else transcricao
            
            for i, item in enumerate(ultimos):
                start = item.get("start", 0)
                end = min(item.get("end", start + 8), duracao_video)
                text = item.get("text", "")[:80]
                
                momentos.append({
                    "id": i + 1,
                    "inicio": int(start),
                    "fim": int(end),
                    "texto": text,
                    "razao": "Momento de destaque (fallback)"
                })
        
        # Se não há transcrição, divide o vídeo em 3 partes iguais
        if not momentos:
            parte = duracao_video / 4
            for i in range(3):
                start = duracao_video - (parte * (i + 1))
                end = min(start + parte, duracao_video)
                momentos.append({
                    "id": i + 1,
                    "inicio": int(start),
                    "fim": int(end),
                    "texto": f"Destaque {i+1}",
                    "razao": "Divisão automática"
                })
        
        return {"momentos": momentos}