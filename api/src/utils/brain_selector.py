#!/usr/bin/env python3
"""
src/utils/brain_selector.py

Fase 2: Analisa os clipes com IA e seleciona os melhores momentos
"""

import asyncio
import json
import sys
from pathlib import Path
from typing import List, Dict, Optional

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT_DIR))

from src.services.brain_IA import Brain
from src.controllers.whisper.model import model
from src.utils.logs import logger


class BrainSelector:
    def __init__(self):
        self.brain_ia = Brain()
        self.whisper_instance = None

    def _get_whisper(self):
        """Obtém instância do Whisper (lazy loading)"""
        if self.whisper_instance is None:
            self.whisper_instance = model()
        return self.whisper_instance

    async def transcrever_clipe(self, video_path: Path) -> List[Dict]:
        """Transcreve um único clipe e retorna frases com timestamps"""
        logger.info(f"🎙️ Transcrevendo: {video_path.name}")
        
        whisper_instance = self._get_whisper()
        
        # Executa a transcrição em thread separada
        loop = asyncio.get_event_loop()
        
        try:
            segments, _ = await loop.run_in_executor(
                None,
                lambda: whisper_instance.transcribe(
                    str(video_path),
                    beam_size=5,
                    word_timestamps=True,
                    best_of=5,
                    language="pt",
                    initial_prompt="Áudio em português do Brasil",
                    temperature=0.0,
                    condition_on_previous_text=False,
                ),
            )
            
            # Agrupa palavras em frases
            frases = []
            texto_atual = ""
            start_atual = None
            
            for segment in segments:
                if hasattr(segment, 'words') and segment.words:
                    for word in segment.words:
                        if start_atual is None:
                            start_atual = word.start
                        texto_atual += " " + word.word
                        
                        # Pausa maior que 0.5s ou pontuação = fim de frase
                        if hasattr(word, 'end') and word.end:
                            # Verifica se é fim de frase (ponto, exclamação, interrogação)
                            if texto_atual.strip().endswith(('.', '!', '?')):
                                frases.append({
                                    "start": start_atual,
                                    "end": word.end,
                                    "text": texto_atual.strip()
                                })
                                texto_atual = ""
                                start_atual = None
                            # Ou se a pausa foi grande
                            elif hasattr(word, 'end') and hasattr(word, 'start'):
                                if word.end - word.start > 0.5:
                                    frases.append({
                                        "start": start_atual,
                                        "end": word.end,
                                        "text": texto_atual.strip()
                                    })
                                    texto_atual = ""
                                    start_atual = None
            
            # Adiciona o último texto se sobrou
            if texto_atual.strip():
                frases.append({
                    "start": start_atual or 0,
                    "end": segment.end if hasattr(segment, 'end') else 0,
                    "text": texto_atual.strip()
                })
            
            return frases
            
        except Exception as e:
            logger.error(f"❌ Erro na transcrição: {e}")
            return []

    async def analisar_clipe(self, clipe: Dict) -> Dict:
        """Analisa um clipe e retorna se é interessante"""
        video_path = Path(clipe["path"])
        
        if not video_path.exists():
            logger.warning(f"❌ Arquivo não encontrado: {video_path}")
            clipe["analise"] = "erro"
            clipe["interessante"] = False
            clipe["score"] = 0
            return clipe
        
        # Transcrever
        frases = await self.transcrever_clipe(video_path)
        
        if not frases:
            logger.warning(f"⚠️ Sem fala detectada em: {video_path.name}")
            clipe["analise"] = "sem_fala"
            clipe["interessante"] = False
            clipe["score"] = 0
            return clipe
        
        # IA analisa
        try:
            resultado = self.brain_ia.encontrar_melhores_momentos(frases, clipe["duration"])
            
            # Valida o resultado ANTES de acessar "momentos"
            if resultado and isinstance(resultado, dict):
                momentos = resultado.get("momentos", [])
                if momentos and len(momentos) > 0:
                    clipe["analise"] = "interessante"
                    clipe["interessante"] = True
                    clipe["momentos"] = momentos
                    clipe["score"] = len(momentos)
                else:
                    clipe["analise"] = "sem_interesse"
                    clipe["interessante"] = False
                    clipe["score"] = 0
            else:
                logger.warning(f"⚠️ Resultado inválido da IA para: {video_path.name}")
                clipe["analise"] = "sem_interesse"
                clipe["interessante"] = False
                clipe["score"] = 0
                
        except Exception as e:
            logger.error(f"❌ Erro na análise da IA: {e}")
            clipe["analise"] = "erro_ia"
            clipe["interessante"] = False
            clipe["score"] = 0
        
        return clipe

    async def selecionar_melhores_clipes(self, clipes_json_path: str) -> List[Dict]:
        """Carrega clipes do JSON, analisa cada um e seleciona os melhores"""
        # Carrega os clipes
        with open(clipes_json_path, "r", encoding="utf-8") as f:
            clipes = json.load(f)
        
        print(f"\n📊 Analisando {len(clipes)} clipes com IA...")
        print("-" * 50)
        
        resultados = []
        for i, clipe in enumerate(clipes, 1):
            print(f"🔍 Analisando clip {i}/{len(clipes)}: {clipe['filename']}")
            resultado = await self.analisar_clipe(clipe)
            resultados.append(resultado)
            
            if resultado.get("interessante"):
                score = resultado.get("score", 0)
                print(f"   ✅ INTERESSANTE (score: {score})")
            else:
                motivo = resultado.get("analise", "desconhecido")
                print(f"   ⏩ Descartar ({motivo})")
        
        # Seleciona apenas os interessantes
        selecionados = [r for r in resultados if r.get("interessante")]
        
        # Ordena por score (maior primeiro)
        selecionados.sort(key=lambda x: x.get("score", 0), reverse=True)
        
        # Salvar resultados completos
        output_dir = Path(clipes_json_path).parent
        resultados_path = output_dir / "analise_completa.json"
        with open(resultados_path, "w", encoding="utf-8") as f:
            json.dump(resultados, f, ensure_ascii=False, indent=2)
        
        selecionados_path = output_dir / "clipes_selecionados.json"
        with open(selecionados_path, "w", encoding="utf-8") as f:
            json.dump(selecionados, f, ensure_ascii=False, indent=2)
        
        print("\n" + "=" * 50)
        print(f"✅ Análise concluída!")
        print(f"   📊 Total analisados: {len(resultados)}")
        print(f"   🎯 Selecionados: {len(selecionados)}")
        print(f"   💾 Resultados: {resultados_path}")
        print(f"   💾 Selecionados: {selecionados_path}")
        
        return selecionados


async def main():
    import sys
    from pathlib import Path
    
    # Verificar modelo Whisper
    try:
        whisper_instance = model()
        print("✅ Whisper disponível!")
    except Exception as e:
        print(f"❌ Erro ao carregar Whisper: {e}")
        sys.exit(1)
    
    # Caminho do JSON gerado na Fase 1
    base_dir = Path("/home/dev/Code/clip_engine/parts")
    clipes_json = base_dir / "A_REALIDADE_DA_GUERRA_NA_UCRÂNIA_CRISTIAN_GALVÃO_RELATA_AS_PIORES_PARTES_DO_CONFRONTO_clipes.json"
    
    if not clipes_json.exists():
        print(f"❌ Arquivo não encontrado: {clipes_json}")
        print("   Execute primeiro a Fase 1 (video_splitter_fast.py)")
        sys.exit(1)
    
    print("=" * 60)
    print("🧠 FASE 2: Brain IA - Selecionando melhores clipes")
    print("=" * 60)
    
    selector = BrainSelector()
    selecionados = await selector.selecionar_melhores_clipes(str(clipes_json))
    
    print("\n🏆 Clipes selecionados para processamento final:")
    for i, clip in enumerate(selecionados, 1):
        score = clip.get('score', 0)
        momentos = clip.get('momentos', [])
        print(f"   {i}. {clip['filename']}")
        print(f"      Score: {score} | Momentos: {len(momentos)}")
        if momentos:
            for m in momentos[:2]:  # Mostra os 2 primeiros momentos
                print(f"      🎯 {m.get('texto', '')[:50]}... ({m.get('inicio',0)}s-{m.get('fim',0)}s)")


if __name__ == "__main__":
    asyncio.run(main())