#!/usr/bin/env python3
"""
install.py

Script de instalação automatizada do Clip Engine.
Resolve problemas de compatibilidade com MediaPipe e instala todas as dependências.

Uso:
    python3 install.py              # Instalação completa
    python3 install.py --check      # Apenas verifica dependências
    python3 install.py --fix-mediapipe  # Corrige apenas o MediaPipe
"""

import os
import platform
import subprocess
import sys
from pathlib import Path

# ══════════════════════════════════════════════════════════════
#  CONFIGURAÇÃO
# ══════════════════════════════════════════════════════════════

PYTHON_VERSION = f"{sys.version_info.major}.{sys.version_info.minor}"
IS_LINUX = platform.system() == "Linux"
IS_MAC = platform.system() == "Darwin"
IS_WINDOWS = platform.system() == "Windows"

# Versão compatível do MediaPipe (a 0.10.9 não existe mais)
# 0.10.18 é a última que funciona com a API antiga (mp.solutions)
# Versões >= 0.10.30 usam API nova (mp.tasks)
MEDIAPIPE_VERSION = "0.10.18"

# Dependências essenciais (sem versão fixa problemática)
CORE_DEPS = [
    "fastapi>=0.100.0",
    "uvicorn>=0.23.0",
    "yt-dlp>=2024.1.0",
    "faster-whisper>=1.0.0",
    "openai>=1.0.0",
    "opencv-python>=4.8.0",
    "numpy>=1.24.0,<2.0.0",  # Compatível com MediaPipe 0.10.x
    "python-dotenv>=1.0.0",
    "pydantic>=2.0.0",
    "httpx>=0.25.0",
    "aiofiles>=23.0.0",
    "python-multipart>=0.0.6",
    "supabase>=2.0.0",
    "Pillow>=10.0.0",
    "matplotlib>=3.7.0",
    "scipy>=1.11.0",
    "librosa>=0.10.0",
    "soundfile>=0.12.0",
    "pydub>=0.25.0",
    "moviepy>=2.0.0",
    "tqdm>=4.65.0",
    "rich>=13.0.0",
    "deep-translator>=1.11.0",
]

# MediaPipe + protobuf compatível
MEDIAPIPE_DEPS = [
    f"mediapipe=={MEDIAPIPE_VERSION}",
    "protobuf>=3.20.0,<4.0.0",  # MediaPipe 0.10.x precisa de protobuf 3.x
]

# Dependências opcionais
OPTIONAL_DEPS = [
    "black>=23.0.0",
    "flake8>=6.0.0",
    "isort>=5.12.0",
]


def print_banner():
    """Imprime banner de instalação."""
    print("\n" + "=" * 60)
    print("🎬 CLIP ENGINE - INSTALADOR")
    print("=" * 60)
    print(f"  Python: {PYTHON_VERSION}")
    print(f"  Sistema: {platform.system()} {platform.release()}")
    print(f"  Arquitetura: {platform.machine()}")
    print("=" * 60)


def run_pip(args, desc="Instalando"):
    """Executa pip com os argumentos fornecidos."""
    cmd = [sys.executable, "-m", "pip", "install"] + args
    print(f"\n📦 {desc}...")
    print(f"   {' '.join(cmd)}")

    try:
        subprocess.run(cmd, check=True, text=True)
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Erro: {e}")
        return False


def check_mediapipe():
    """Verifica se MediaPipe está instalado e funcionando."""
    print("\n🔍 Verificando MediaPipe...")

    try:
        import mediapipe as mp

        version = mp.__version__
        has_solutions = hasattr(mp, "solutions")
        print(f"   ✅ MediaPipe {version} instalado")
        print(
            f"   ✅ API 'solutions': {'Disponível' if has_solutions else 'INDISPONÍVEL'}"
        )
        return has_solutions
    except ImportError:
        print("   ❌ MediaPipe não instalado")
        return False
    except AttributeError:
        print("   ❌ MediaPipe instalado mas sem 'solutions' (API antiga)")
        return False


def fix_mediapipe():
    """
    Corrige o problema do MediaPipe.

    O problema: mediapipe==0.10.9 não existe mais.
    Versões >= 0.10.30 usam API nova (mp.tasks) e não têm mp.solutions.
    Solução: instalar mediapipe==0.10.18 + protobuf 3.x
    """
    print("\n🔧 CORRIGINDO MEDIAPIPE...")

    # 1. Desinstala versão atual
    print("   1. Removendo versão atual...")
    subprocess.run(
        [sys.executable, "-m", "pip", "uninstall", "mediapipe", "-y"],
        capture_output=True,
    )
    subprocess.run(
        [sys.executable, "-m", "pip", "uninstall", "protobuf", "-y"],
        capture_output=True,
    )

    # 2. Instala protobuf compatível primeiro
    print("   2. Instalando protobuf 3.20.3...")
    run_pip(["protobuf==3.20.3"], "protobuf")

    # 3. Instala MediaPipe 0.10.18
    print(f"   3. Instalando mediapipe=={MEDIAPIPE_VERSION}...")

    # Tenta com binário pré-compilado primeiro
    success = run_pip([f"mediapipe=={MEDIAPIPE_VERSION}"], "mediapipe")

    if not success:
        # Fallback: tenta versão mais recente com API nova
        print(
            "\n   ⚠️  MediaPipe 0.10.18 não disponível, tentando versão mais recente..."
        )
        print("   ℹ️  Isso exigirá ajustes no código para a nova API.")
        success = run_pip(["mediapipe>=0.10.30"], "mediapipe (latest)")

    # 4. Verifica
    if check_mediapipe():
        print("\n✅ MediaPipe corrigido com sucesso!")
        return True
    else:
        print("\n❌ Falha ao corrigir MediaPipe")
        print("   Tente instalar manualmente:")
        print(f"   pip install mediapipe=={MEDIAPIPE_VERSION} protobuf==3.20.3")
        return False


def install_requirements():
    """Instala todas as dependências."""
    print("\n📦 INSTALANDO DEPENDÊNCIAS...")

    all_deps = CORE_DEPS + MEDIAPIPE_DEPS

    for dep in all_deps:
        name = dep.split(">=")[0].split("==")[0].split("<")[0]
        run_pip([dep], name)

    print("\n✅ Dependências core instaladas!")


def install_optional():
    """Instala dependências opcionais."""
    resp = (
        input("\n📦 Instalar dependências opcionais (black, flake8, isort)? (s/n): ")
        .strip()
        .lower()
    )
    if resp == "s":
        for dep in OPTIONAL_DEPS:
            name = dep.split(">=")[0]
            run_pip([dep], name)


def generate_requirements():
    """Gera um requirements.txt compatível."""
    print("\n📝 Gerando requirements.txt...")

    requirements = [
        "# Clip Engine - Requirements",
        "# Gerado automaticamente pelo install.py",
        "",
        "# Core",
    ]

    requirements.extend(CORE_DEPS)
    requirements.append("")
    requirements.append("# MediaPipe (compatível com API solutions)")
    requirements.extend(MEDIAPIPE_DEPS)
    requirements.append("")
    requirements.append("# Opcionais")
    requirements.extend(OPTIONAL_DEPS)

    req_path = Path(__file__).parent / "requirements.txt"
    with open(req_path, "w") as f:
        f.write("\n".join(requirements) + "\n")

    print(f"   ✅ requirements.txt gerado em: {req_path}")


def verify_installation():
    """Verifica se todas as dependências críticas estão funcionando."""
    print("\n🔍 VERIFICANDO INSTALAÇÃO...")

    checks = {
        "fastapi": "FastAPI",
        "uvicorn": "Uvicorn",
        "yt_dlp": "yt-dlp",
        "faster_whisper": "faster-whisper",
        "openai": "OpenAI",
        "cv2": "OpenCV",
        "numpy": "NumPy",
        "mediapipe": "MediaPipe",
        "PIL": "Pillow",
        "matplotlib": "Matplotlib",
        "librosa": "Librosa",
        "moviepy": "MoviePy",
        "deep_translator": "Deep Translator",
        "dotenv": "python-dotenv",
    }

    all_ok = True
    for module, name in checks.items():
        try:
            __import__(module)
            print(f"   ✅ {name}")
        except ImportError:
            print(f"   ❌ {name} - NÃO ENCONTRADO")
            all_ok = False

    # Verificação especial do MediaPipe
    if not check_mediapipe():
        all_ok = False

    return all_ok


def main():
    """Função principal."""
    import argparse

    parser = argparse.ArgumentParser(description="Instalador do Clip Engine")
    parser.add_argument(
        "--check", action="store_true", help="Apenas verifica dependências"
    )
    parser.add_argument(
        "--fix-mediapipe", action="store_true", help="Corrige apenas o MediaPipe"
    )
    parser.add_argument(
        "--generate-req", action="store_true", help="Gera requirements.txt"
    )

    args = parser.parse_args()

    print_banner()

    if args.check:
        verify_installation()
        return

    if args.generate_req:
        generate_requirements()
        return

    if args.fix_mediapipe:
        fix_mediapipe()
        return

    # Instalação completa
    print("\n🚀 INICIANDO INSTALAÇÃO COMPLETA...")

    # 1. Upgrade pip
    run_pip(["--upgrade", "pip"], "Upgrading pip")

    # 2. Instalar dependências core
    install_requirements()

    # 3. Corrigir MediaPipe se necessário
    if not check_mediapipe():
        fix_mediapipe()

    # 4. Opcionais
    install_optional()

    # 5. Gerar requirements.txt
    generate_requirements()

    # 6. Verificação final
    print("\n" + "=" * 60)
    if verify_installation():
        print("\n✅ INSTALAÇÃO CONCLUÍDA COM SUCESSO!")
        print("   Execute: python3 run_pipeline.py")
    else:
        print("\n⚠️  Algumas dependências não foram instaladas.")
        print("   Verifique os erros acima.")

    print("=" * 60)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Instalação interrompida.")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Erro: {e}")
        sys.exit(1)
