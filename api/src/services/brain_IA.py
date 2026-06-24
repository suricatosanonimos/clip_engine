"""
src/services/brain_IA.py

Serviço de IA para processamento de vídeos usando Groq API.
Gerencia momentos, títulos e análises com prompts externos.
"""

import json
import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Any

from dotenv import load_dotenv
from openai import OpenAI

# ── Configuração de Path ──────────────────────────────────────
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(ROOT_DIR))

try:
    from src.utils.logs import logger
except ImportError:
    import logging
    logger = logging.getLogger(__name__)

load_dotenv()


class Brain:
    """Classe principal para interação com IA (Groq)"""
    
    def __init__(self):
        self.API_KEY = os.getenv("GLOK_API")
        
        if not self.API_KEY:
            logger.warning("API_KEY não encontrada - usando fallback sem IA")
            self.client = None
        else:
            self.client = OpenAI(
                api_key=self.API_KEY,
                base_url="https://api.groq.com/openai/v1",
            )
        
        logger.info("Brain IA inicializado com sucesso")
    
    # ──────────────────────────────────────────────────────────────
    #  MÉTODOS PRINCIPAIS
    # ──────────────────────────────────────────────────────────────
    
    def encontrar_melhores_momentos(
        self, 
        transcricao: List[Dict], 
        duracao_video: float
    ) -> Dict[str, Any]:
        """
        Encontra os melhores momentos do vídeo baseado na transcrição.
        """
        if not self.client or not transcricao:
            logger.info("Usando fallback para momentos (sem client ou sem transcrição)")
            return self._fallback_momentos(transcricao, duracao_video)
        
        try:
            # Prepara transcrição
            transcricao_formatada = self._formatar_transcricao(transcricao)
            
            if len(transcricao_formatada) > 3000:
                transcricao_formatada = transcricao_formatada[:3000]
            
            # Monta prompt
            prompt = self._montar_prompt_momentos(transcricao_formatada)
            
            # Faz requisição
            response = self.client.chat.completions.create(
                model="openai/gpt-oss-120b",
                messages=[
                    {"role": "system", "content": "Você é um editor de vídeos especialista em identificar momentos virais."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.4,
                max_tokens=500,
            )
            
            content = response.choices[0].message.content
            logger.info(f"Resposta da IA (momentos): {content[:200]}...")
            
            # Extrai momentos do texto
            momentos = self._extrair_momentos_do_texto(content, duracao_video)
            
            if momentos:
                return {"momentos": momentos}
            
            logger.warning("Não foi possível extrair momentos, usando fallback")
            return self._fallback_momentos(transcricao, duracao_video)
            
        except Exception as e:
            logger.error(f"Erro na Brain IA (momentos): {e}")
            return self._fallback_momentos(transcricao, duracao_video)
    
    def generate_titles(
        self,
        video_title: str,
        description: str = "",
        count: int = 5,
        duration: int = 0,
        uploader: str = "",
    ) -> Dict[str, List[str]]:
        """
        Gera títulos virais para o vídeo usando IA.
        """
        if not self.client:
            logger.warning("Client não disponível para gerar títulos")
            return {"titles": self._fallback_titulos(video_title, count)}
        
        try:
            # Monta prompt melhorado
            prompt = self._montar_prompt_titulos(
                video_title, description, duration, uploader, count
            )
            
            # Faz requisição
            response = self.client.chat.completions.create(
                model="openai/gpt-oss-120b",
                messages=[
                    {"role": "system", "content": "Você é um especialista em marketing de conteúdo viral para YouTube Shorts e Reels. Crie títulos que geram cliques e engajamento."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.9,
                max_tokens=800,
            )
            
            content = response.choices[0].message.content
            logger.info(f"Resposta da IA (títulos): {content[:300]}...")
            
            # Extrai títulos do texto
            titles = self._extrair_titulos_do_texto(content, count)
            
            # Se extraiu títulos, retorna
            if titles and len(titles) > 1:
                # Remove duplicatas e limpa
                titles = self._limpar_titulos(titles)
                logger.info(f"✅ Títulos extraídos: {len(titles)} títulos")
                return {"titles": titles[:count]}
            
            # Se não extraiu ou só tem 1 título, tenta com o fallback
            logger.warning("Não foi possível extrair títulos suficientes, usando fallback")
            fallback_titles = self._fallback_titulos(video_title, count)
            
            # Mescla os títulos da IA com o fallback se tiver pelo menos 1
            if titles:
                combined = titles + fallback_titles
                combined = self._limpar_titulos(combined)
                return {"titles": combined[:count]}
            
            return {"titles": fallback_titles}
            
        except Exception as e:
            logger.error(f"Erro ao gerar títulos: {e}")
            return {"titles": self._fallback_titulos(video_title, count)}
    
    # ──────────────────────────────────────────────────────────────
    #  MONTAGEM DE PROMPTS (Melhorados)
    # ──────────────────────────────────────────────────────────────
    
    def _montar_prompt_momentos(self, transcricao: str) -> str:
        """Monta o prompt para encontrar melhores momentos"""
        return f"""
        Analise a transcrição abaixo e identifique os 3 momentos mais impactantes e virais.
        
        REGRAS:
        - Cada momento deve ter entre 3 e 10 segundos
        - Foque em frases que geram curiosidade, surpresa ou emoção
        - Priorize momentos que funcionam bem para Shorts/Reels
        
        FORMATO DE RESPOSTA (um momento por linha):
        Início: Xs, Fim: Ys - Texto do momento
        
        Transcrição:
        {transcricao}
        
        Responda APENAS com a lista de momentos no formato solicitado.
        """
    
    def _montar_prompt_titulos(
        self, 
        video_title: str, 
        description: str, 
        duration: int, 
        uploader: str, 
        count: int
    ) -> str:
        """Monta o prompt para gerar títulos (melhorado)"""
        prompt = f"""
        Crie {count} títulos criativos e virais para um vídeo do YouTube.
        
        Título original: "{video_title}"
        """
        
        if description:
            # Pega as primeiras 300 caracteres da descrição
            desc_curta = description[:300]
            prompt += f"\nDescrição: {desc_curta}..."
        
        if duration > 0:
            prompt += f"\nDuração: {duration // 60} minutos"
        
        if uploader:
            prompt += f"\nCanal: {uploader}"
        
        prompt += """
        
        REGRAS IMPORTANTES:
        1. Cada título deve ter entre 30 e 80 caracteres
        2. Use palavras que geram curiosidade: "segredo", "ninguém te conta", "realidade", "impactante"
        3. Crie títulos com ganchos emocionais
        4. Seja criativo, evitando clichês genéricos
        5. Títulos devem funcionar bem para Shorts/Reels
        6. NÃO repita o título original
        7. NÃO use o mesmo título mais de uma vez
        
        FORMATO DE RESPOSTA:
        Apenas liste os títulos, um por linha, sem numeração.
        
        Exemplo de estilo de títulos que funcionam:
        - O segredo que ninguém te conta sobre...
        - Como isso está mudando tudo...
        - A verdade por trás de...
        - Isso vai te surpreender...
        """
        
        return prompt
    
    # ──────────────────────────────────────────────────────────────
    #  EXTRAÇÃO DE DADOS DO TEXTO (Melhorada)
    # ──────────────────────────────────────────────────────────────
    
    def _extrair_momentos_do_texto(self, texto: str, duracao_video: float) -> List[Dict]:
        """
        Extrai momentos do texto da IA.
        """
        momentos = []
        linhas = texto.split('\n')
        
        # Padrões para encontrar momentos
        padroes = [
            # "Início: 5s, Fim: 12s - texto"
            r'(?:in[íi]cio|start)\s*:?\s*(\d+\.?\d*)\s*s?\s*(?:fim|end)\s*:?\s*(\d+\.?\d*)\s*s?\s*[-–]\s*(.+)',
            # "[00:05 - 00:12] texto"
            r'\[(\d+):(\d+)\s*[-–]\s*(\d+):(\d+)\]\s*(.+)',
            # "5s - 12s: texto"
            r'(\d+\.?\d*)\s*s?\s*[-–]\s*(\d+\.?\d*)\s*s?\s*:?\s*(.+)',
        ]
        
        for linha in linhas:
            linha = linha.strip()
            if not linha:
                continue
            
            for padrao in padroes:
                match = re.search(padrao, linha, re.IGNORECASE)
                if match:
                    grupos = match.groups()
                    
                    if len(grupos) == 3:
                        inicio = float(grupos[0])
                        fim = float(grupos[1])
                        texto_momento = grupos[2].strip()
                    elif len(grupos) == 5:
                        min_inicio = int(grupos[0])
                        sec_inicio = int(grupos[1])
                        min_fim = int(grupos[2])
                        sec_fim = int(grupos[3])
                        inicio = min_inicio * 60 + sec_inicio
                        fim = min_fim * 60 + sec_fim
                        texto_momento = grupos[4].strip()
                    else:
                        continue
                    
                    # Valida os tempos
                    if inicio < 0:
                        inicio = 0
                    if fim > duracao_video:
                        fim = duracao_video
                    if fim <= inicio:
                        fim = inicio + 5
                    
                    # Limpa o texto
                    texto_momento = re.sub(r'^["\']+|["\']+$', '', texto_momento)
                    
                    momentos.append({
                        "inicio": int(inicio),
                        "fim": int(fim),
                        "texto": texto_momento[:100],
                        "razao": "Extraído da resposta da IA"
                    })
                    break
        
        return momentos[:3]
    
    def _extrair_titulos_do_texto(self, texto: str, count: int) -> List[str]:
        """
        Extrai títulos do texto da IA (melhorado para capturar títulos em lista).
        """
        titulos = []
        
        # Primeiro, tenta separar por quebras de linha
        linhas = texto.strip().split('\n')
        
        # Se o texto tem poucas linhas, tenta separar por outros delimitadores
        if len(linhas) <= 2:
            # Tenta separar por pontos finais seguidos de espaço
            if '. ' in texto:
                partes = texto.split('. ')
                if len(partes) > 1:
                    linhas = [p.strip() for p in partes if p.strip()]
            # Tenta separar por " - " ou " | "
            elif ' - ' in texto or ' | ' in texto:
                separador = ' - ' if ' - ' in texto else ' | '
                partes = texto.split(separador)
                if len(partes) > 1:
                    linhas = [p.strip() for p in partes if p.strip()]
        
        # Processa cada linha
        for linha in linhas:
            linha = linha.strip()
            if not linha:
                continue
            
            # Remove marcadores de lista (numeração, bullets, etc)
            linha = re.sub(r'^[\d]+[\.\)]\s*', '', linha)
            linha = re.sub(r'^[-\*\•]\s*', '', linha)
            linha = re.sub(r'^["\']+|["\']+$', '', linha)
            
            # Remove palavras que indicam que não é um título
            if any(palavra in linha.lower() for palavra in ['aqui estão', 'lista de', 'títulos:', 'titulos:', 'resposta:']):
                continue
            
            # Verifica se é um título válido (tem mais de 10 caracteres e menos de 150)
            if len(linha) > 10 and len(linha) < 150:
                # Remove caracteres indesejados
                linha = re.sub(r'^["\']+|["\']+$', '', linha)
                
                # Não adiciona se for igual ao anterior
                if titulos and linha == titulos[-1]:
                    continue
                
                titulos.append(linha)
                
                if len(titulos) >= count:
                    break
        
        # Se não encontrou títulos suficientes, tenta extrair do texto completo
        if len(titulos) < 2:
            # Procura por padrões de título (frases curtas com sentido)
            frases = re.findall(r'[A-Z][^.!?]*[.!?]', texto)
            for frase in frases:
                frase = frase.strip()
                if 15 < len(frase) < 120 and frase not in titulos:
                    titulos.append(frase)
                    if len(titulos) >= count:
                        break
        
        return titulos
    
    def _limpar_titulos(self, titulos: List[str]) -> List[str]:
        """
        Limpa e remove duplicatas da lista de títulos.
        """
        vistos = set()
        limpos = []
        
        for titulo in titulos:
            titulo = titulo.strip()
            if not titulo:
                continue
            
            # Normaliza para verificar duplicatas
            chave = titulo.lower()
            if chave in vistos:
                continue
            vistos.add(chave)
            
            limpos.append(titulo)
        
        return limpos
    
    # ──────────────────────────────────────────────────────────────
    #  FORMATADORES
    # ──────────────────────────────────────────────────────────────
    
    def _formatar_transcricao(self, transcricao: List[Dict]) -> str:
        """Formata transcrição para o prompt"""
        linhas = []
        for item in transcricao[:30]:
            start = item.get("start", 0)
            text = item.get("text", "")[:150]
            minutos = int(start // 60)
            segundos = int(start % 60)
            linhas.append(f"[{minutos:02d}:{segundos:02d}] {text}")
        return "\n".join(linhas)
    
    # ──────────────────────────────────────────────────────────────
    #  FALLBACKS (Com títulos mais criativos)
    # ──────────────────────────────────────────────────────────────
    
    def _fallback_momentos(self, transcricao: List[Dict], duracao_video: float) -> Dict:
        """Fallback: gera momentos baseados na transcrição ou divisão do vídeo."""
        logger.info("Executando Fallback de momentos")
        
        momentos = []
        
        if transcricao:
            ultimos = transcricao[-3:] if len(transcricao) >= 3 else transcricao
            
            for i, item in enumerate(ultimos):
                start = item.get("start", 0)
                end = min(item.get("end", start + 8), duracao_video)
                text = item.get("text", "")[:80]
                
                momentos.append({
                    "id": i + 1,
                    "inicio": int(start),
                    "fim": int(end),
                    "texto": text if text else f"Destaque {i+1}",
                    "razao": "Momento de destaque (fallback)"
                })
        
        if not momentos and duracao_video > 0:
            parte = duracao_video / 4
            for i in range(3):
                start = duracao_video - (parte * (i + 1))
                end = min(start + parte, duracao_video)
                momentos.append({
                    "id": i + 1,
                    "inicio": int(max(0, start)),
                    "fim": int(end),
                    "texto": f"Destaque {i+1}",
                    "razao": "Divisão automática"
                })
        
        return {"momentos": momentos}
    
    def _fallback_titulos(self, video_title: str, count: int) -> List[str]:
        """
        Fallback: gera títulos mais criativos sem IA.
        """
        logger.info("Gerando títulos de fallback")
        
        # Remove o nome do canal e outras informações do título
        titulo_base = video_title
        # Remove "| Nome do Canal"
        titulo_base = re.sub(r'\s*[|:]\s*[^|:]+$', '', titulo_base)
        # Remove "Prof.", "Dr.", etc
        titulo_base = re.sub(r'^(Prof\.|Dr\.|Mestre)\s+', '', titulo_base)
        
        templates = [
            f"{titulo_base}",
            f"{titulo_base} - O que ninguém te conta",
            f"🔥 A verdade sobre {titulo_base}",
            f"{titulo_base} - Você precisa saber disso",
            f"Como {titulo_base} está mudando o jogo",
            f"{titulo_base} - Os melhores momentos",
            f"IMPACTANTE: {titulo_base}",
            f"O segredo por trás de {titulo_base}",
            f"{titulo_base} - Resumo completo",
            f"Por que {titulo_base} está viralizando?",
        ]
        
        titulos = []
        vistos = set()
        
        for template in templates:
            titulo = template
            
            # Se o título for muito longo, encurta
            if len(titulo) > 80:
                titulo = titulo[:77] + "..."
            
            chave = titulo.lower()
            if chave not in vistos:
                vistos.add(chave)
                titulos.append(titulo)
            
            if len(titulos) >= count:
                break
        
        return titulos