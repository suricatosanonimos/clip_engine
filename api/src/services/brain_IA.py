import json
import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional

from dotenv import load_dotenv
from openai import OpenAI

# Configuração de caminhos e logs
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
        self.API_KEY = os.getenv(
            "GLOK_API"
        )  # Verifique se o nome da chave está correto no .env

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
        Você é um editor de vídeos especialista em retenção (Hooks).
        Sua tarefa é analisar a transcrição e escolher 3 momentos impactantes que ocorram PREFERENCIALMENTE no FINAL do vídeo (últimos 30% da duração).
        Esses momentos servirão como "spoilers" ou "previsões" no início do vídeo para prender a atenção.

        REGRAS:
        - Cada momento: 3 a 8 segundos.
        - Foque em frases que gerem curiosidade ou mostrem a conclusão de uma ideia.
        - Não sobrepor horários.
        - Retorne APENAS o JSON.

        TRANSCRIÇÃO:
        {transcription}

        FORMATO:
        {{
            "momentos": [
                {{
                    "id": 1,
                    "inicio": "MM:SS",
                    "fim": "MM:SS",
                    "texto": "...",
                    "razao": "Por que esse spoiler é bom?"
                }}
            ]
        }}
        """

    def encontrar_melhores_momentos(
        self, transcricao: List[Dict], duracao_video: float
    ) -> Dict:
        if not self.client:
            return self._fallback_momentos(transcricao)

        try:
            transcricao_formatada = self._formatar_transcricao(transcricao)
            prompt = self.prompt_momentos.format(transcription=transcricao_formatada)

            response = self.client.chat.completions.create(
                model="openai/gpt-oss-20b",  # Modelo estável do Groq
                messages=[
                    {
                        "role": "system",
                        "content": "Você é um assistente que responde apenas em JSON puro.",
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.1,  # Menor temperatura = mais precisão no formato
                max_tokens=1000,
                response_format={"type": "json_object"},  # Força o modo JSON
            )

            content = response.choices[0].message.content

            # Tenta extrair o JSON de forma robusta
            resultado = self._extrair_json_robusto(content)

            if resultado and self._validar_momentos(resultado):
                return resultado

            logger.warning("JSON inválido da API, usando fallback")
            return self._fallback_momentos(transcricao)

        except Exception as e:
            logger.error(f"Erro na Brain IA: {e}")
            return self._fallback_momentos(transcricao)

    def _extrair_json_robusto(self, texto: str) -> Optional[Dict]:
        """Limpa o texto e extrai o JSON ignorando ruídos externos."""
        if not texto:
            return None

        try:
            # 1. Tenta o parse direto (caso venha limpo)
            return json.loads(texto.strip())
        except json.JSONDecodeError:
            try:
                # 2. Busca o conteúdo entre a primeira '{' e a última '}'
                # O DOTALL faz o '.' aceitar quebras de linha
                match = re.search(r"(\{.*\})", texto, re.DOTALL)
                if match:
                    json_str = match.group(1)
                    return json.loads(json_str)
            except Exception as e:
                logger.error(f"Falha crítica ao parsear JSON: {e}")
                logger.debug(f"Conteúdo problemático: {texto}")
        return None

    def _formatar_transcricao(self, transcricao: List[Dict]) -> str:
        return "\n".join(
            [
                f"[{self._segundos_para_timestamp(i['start'])} -> {self._segundos_para_timestamp(i['end'])}] {i['text']}"
                for i in transcricao
            ]
        )

    def _segundos_para_timestamp(self, segundos: float) -> str:
        return f"{int(segundos // 60):02d}:{int(segundos % 60):02d}"

    def _validar_momentos(self, data: Dict) -> bool:
        return (
            isinstance(data, dict) and "momentos" in data and len(data["momentos"]) > 0
        )

    def _fallback_momentos(self, transcricao: List[Dict]) -> Dict:
        """Fallback simplificado para garantir que o código não quebre."""
        logger.info("Executando Fallback de momentos")
        # Pega os primeiros 3 trechos como emergência
        momentos = []
        for i, item in enumerate(transcricao[:3]):
            momentos.append(
                {
                    "id": i + 1,
                    "inicio": self._segundos_para_timestamp(item["start"]),
                    "fim": self._segundos_para_timestamp(item["end"]),
                    "duracao": round(item["end"] - item["start"], 1),
                    "texto": item["text"],
                    "razao": "Fallback local",
                    "tipo": "interessante",
                }
            )
        return {
            "momentos": momentos,
            "total_segundos": 15.0,
            "analise": "Análise local (fallback)",
        }


if __name__ == "__main__":
    brain = Brain()
    exemplo = [
        {"start": 2.5, "end": 7.0, "text": "E aí galera, hoje o segredo é incrível!"},
        {"start": 7.5, "end": 12.0, "text": "Isso vai mudar sua vida para sempre."},
        {"start": 12.5, "end": 16.0, "text": "Acredite se quiser, mas aconteceu."},
    ]
    print(
        json.dumps(
            brain.encontrar_melhores_momentos(exemplo, 30.0),
            indent=2,
            ensure_ascii=False,
        )
    )
