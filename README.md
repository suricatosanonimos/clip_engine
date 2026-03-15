<div align="center">
<img src="icon.png" alt="Clip Engine Logo" width="200">

🎬 Clip Engine

<img src="https://img.shields.io/badge/python-3.11%2B-blue" alt="Python Version">
<img src="https://img.shields.io/badge/license-MIT-green" alt="License">
<img src="https://img.shields.io/badge/status-active--development-brightgreen" alt="Status">
<img src="https://img.shields.io/badge/year-2026-orange" alt="Year">

<h3>Transforme vídeos longos em Shorts/Reels incríveis automaticamente! 🚀</h3>
</div>

📋 Sobre o Projeto

O Clip Engine é um motor inteligente que processa vídeos automaticamente para criar clipes prontos para YouTube Shorts, Instagram Reels e TikTok.

Ele faz todo o trabalho pesado para você:

🎯 Detecta quem está falando e aplica zoom automático dinâmico.

📝 Gera legendas interativas palavra por palavra com emojis e censura automática.

🎨 Efeitos visuais dinâmicos com inserção de imagens baseadas em contexto.

⚡ Processamento em lote otimizado para alta performance.

🤖 IA Avançada para transcrição (Whisper) e detecção facial (MediaPipe).

🎥 VEJA O RESULTADO!

Aqui está um exemplo real do processamento automático do Clip Engine:

<!-- BEGIN YOUTUBE-CARDS -->
[![ONDE ESTÀ O RESTANTE DO DINHEIRO DO BLUZEIRA ?](https://ytcards.demolab.com/?id=e7RqpPVQ0mg&title=ONDE+EST%C3%80+O+RESTANTE+DO+DINHEIRO+DO+BLUZEIRA+%3F&lang=en&timestamp=1773337454&background_color=%230d1117&title_color=%23ffffff&stats_color=%23dedede&max_title_lines=1&width=250&border_radius=5 "ONDE ESTÀ O RESTANTE DO DINHEIRO DO BLUZEIRA ?")](https://www.youtube.com/shorts/e7RqpPVQ0mg)
[![BLUZEIA NÃO QUIS ABRIR A PORTA](https://ytcards.demolab.com/?id=-r2U_PGeILk&title=BLUZEIA+N%C3%83O+QUIS+ABRIR+A+PORTA&lang=en&timestamp=1773271581&background_color=%230d1117&title_color=%23ffffff&stats_color=%23dedede&max_title_lines=1&width=250&border_radius=5 "BLUZEIA NÃO QUIS ABRIR A PORTA")](https://www.youtube.com/shorts/-r2U_PGeILk)
[![COMO A IA MOVIMENTA BILHÕES E VOCÊ NEM IMAGINA](https://ytcards.demolab.com/?id=VzWNptoU3bY&title=COMO+A+IA+MOVIMENTA+BILH%C3%95ES+E+VOC%C3%8A+NEM+IMAGINA&lang=en&timestamp=1773201238&background_color=%230d1117&title_color=%23ffffff&stats_color=%23dedede&max_title_lines=1&width=250&border_radius=5 "COMO A IA MOVIMENTA BILHÕES E VOCÊ NEM IMAGINA")](https://www.youtube.com/shorts/VzWNptoU3bY)
[![A Loirinha Da Odonto Tá Na Maldade ( Nobru vlogs )](https://ytcards.demolab.com/?id=x-rsuYYfk0Y&title=A+Loirinha+Da+Odonto+T%C3%A1+Na+Maldade+%28+Nobru+vlogs+%29&lang=en&timestamp=1773153906&background_color=%230d1117&title_color=%23ffffff&stats_color=%23dedede&max_title_lines=1&width=250&border_radius=5 "A Loirinha Da Odonto Tá Na Maldade ( Nobru vlogs )")](https://www.youtube.com/shorts/x-rsuYYfk0Y)
[![PROGRAMADOR APOSENTADO CRIA ALGO INCRÍVEL](https://ytcards.demolab.com/?id=OU_kph4x3ac&title=PROGRAMADOR+APOSENTADO+CRIA+ALGO+INCR%C3%8DVEL&lang=en&timestamp=1773100613&background_color=%230d1117&title_color=%23ffffff&stats_color=%23dedede&max_title_lines=1&width=250&border_radius=5 "PROGRAMADOR APOSENTADO CRIA ALGO INCRÍVEL")](https://www.youtube.com/shorts/OU_kph4x3ac)
[![Estoura o balão e enconte seu amor PT 1](https://ytcards.demolab.com/?id=Yv2T95K55R4&title=Estoura+o+bal%C3%A3o+e+enconte+seu+amor+PT+1&lang=en&timestamp=1773093308&background_color=%230d1117&title_color=%23ffffff&stats_color=%23dedede&max_title_lines=1&width=250&border_radius=5 "Estoura o balão e enconte seu amor PT 1")](https://www.youtube.com/shorts/Yv2T95K55R4)
<!-- END YOUTUBE-CARDS -->

Nota: Se o vídeo não carregar acima, você pode visualizá-lo diretamente na pasta processed_videos/final_clips/.

✨ Funcionalidades

Funcionalidade

Descrição

🎯 Zoom Inteligente

IA que acompanha o rosto do falante ativo

📝 Legendas Dinâmicas

Estilo "Alex Hormozi" com cores e emojis 🎉

😄 Memes Automáticos

Imagens engraçadas aparecem por gatilhos de palavras

🎬 Corte Automático

Segmentação inteligente em formatos verticais (9:16)

🛡️ Censura Inteligente

Detecta e mascara palavras sensíveis automaticamente

⚡ Performance O(log n)

Algoritmos otimizados para busca e corte rápido

🚀 Como Instalar

Pré-requisitos

Python 3.11+

FFmpeg instalado e configurado no seu PATH

Git

Passo a Passo

# 1. Clone o repositório
git clone [https://github.com/Gilderlan0101/clip_engine.git](https://github.com/Gilderlan0101/clip_engine.git)
cd clip_engine

# 2. Crie um ambiente virtual
python3.11 -m venv .venv
source .venv/bin/activate  # No Windows use: .venv\Scripts\activate

# 3. Instale as dependências
pip install -r requirements.txt


🎮 Como Usar

1️⃣ Processar um vídeo completo

Coloque seu vídeo na pasta downloads/ e execute:

python src/utils/ffm_peg.py --video meu_video.mp4


2️⃣ Personalizar a geração de clipes

# Define quantidade de clipes e duração específica
python src/utils/ffm_peg.py --video meu_video.mp4 --num-shots 10 --duration 60


3️⃣ Apenas Transcrição e Legendas

python src/services/transcriber.py


📁 Estrutura do Projeto

clip_engine/
├── icon.png                 # Logo do projeto
├── downloads/               # Entrada de vídeos originais
├── processed_videos/
│   ├── raw_clips/           # Segmentos brutos
│   └── final_clips/         # Vídeos finais editados e legendados
├── imagens_efeitos/          # Banco de imagens para memes contextuais
├── src/
│   ├── controllers/         # Lógica de controle do fluxo
│   ├── services/            # Serviços de IA (Transcrição e Detecção)
│   └── utils/               # Utilitários de vídeo e FFmpeg
├── requirements.txt
└── README.md


⚙️ Personalização

Adicionar novos gatilhos visuais (Memes)

Adicione a imagem em imagens_efeitos/.

O sistema mapeia automaticamente o nome do arquivo para palavras-chave detectadas no áudio.

Lista Negra de Palavras (Censura)

Edite o dicionário BAD_WORDS em src/services/transcriber.py:

BAD_WORDS = {
    "palavra_ruim": "p*******",
    "outra_palavra": "o****_*******"
}


🧠 Performance & Algoritmos

Implementamos lógica de baixo nível para garantir eficiência:

Busca de Frames: Complexidade O(log n) usando indexação temporal.

Detecção Facial: Processamento paralelo via Mediapipe.

Transcrição: Utilização de faster-whisper com suporte a aceleração por hardware (CUDA).

🤝 Contribuindo

Faça um Fork do projeto.

Crie uma Branch para sua feature (git checkout -b feature/NovaFuncao).

Dê um Commit nas suas mudanças (git commit -m 'feat: Adiciona nova função').

Dê um Push para a branch (git push origin feature/NovaFuncao).

Abra um Pull Request.

👨‍💻 Autor

Gilderlan0101

GitHub: @Gilderlan0101

Email: lansilva007gg@gmail.com

<div align="center">
<p>Se este projeto foi útil para você, considere dar uma ⭐ no repositório!</p>
<p>Feito com ❤️ e muita ☕ por Gilderlan em 2026</p>
</div>
