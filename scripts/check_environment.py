"""Environment check script for MemoryMesh."""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def check_environment():
    """Check all required dependencies and services."""
    print("=" * 60)
    print("  MemoryMesh Environment Check")
    print("=" * 60)

    # Python version
    v = sys.version_info
    print(f"\n🐍 Python: {v.major}.{v.minor}.{v.micro}", end="")
    print(" ✅" if v.major == 3 and v.minor >= 10 else " ⚠️ (3.10+ recommended)")

    # Required packages
    packages = [
        "fastapi", "uvicorn", "falkordb", "streamlit",
        "pydantic", "httpx", "ollama", "pytest", "dotenv",
    ]
    print("\n📦 Packages:")
    for pkg in packages:
        try:
            mod = __import__(pkg)
            ver = getattr(mod, "__version__", "?")
            print(f"   ✅ {pkg}: {ver}")
        except ImportError:
            print(f"   ❌ {pkg}: NOT INSTALLED")

    # FalkorDB
    print("\n🗃️  FalkorDB:")
    try:
        from src.db.connection import check_connection
        if check_connection():
            print("   ✅ Connected")
        else:
            print("   ❌ Not available")
            print("   → Start with: docker run -d --name falkordb -p 6379:6379 falkordb/falkordb")
    except Exception as e:
        print(f"   ❌ Error: {e}")

    # Ollama
    print("\n🤖 Ollama:")
    try:
        from src.services.model_service import check_ollama_health
        health = check_ollama_health()
        if health["available"]:
            print(f"   ✅ Connected")
            if health["model_loaded"]:
                print(f"   ✅ Model: {health['model']}")
            else:
                print(f"   ⚠️  Model not found: {health['error']}")
        else:
            print(f"   ❌ {health['error']}")
    except Exception as e:
        print(f"   ❌ Error: {e}")

    # Docker
    print("\n🐳 Docker:")
    docker_ok = os.system("which docker > /dev/null 2>&1") == 0
    if docker_ok:
        print("   ✅ Docker found")
    else:
        print("   ❌ Docker not found")
        print("   → Install Docker Desktop or use Colima")

    print("\n" + "=" * 60)
    print("  Setup Commands:")
    print("=" * 60)
    print("""
1. Install FalkorDB:
   docker run -d --name falkordb -p 6379:6379 falkordb/falkordb

2. Install Ollama:
   brew install ollama   (or download from https://ollama.ai)

3. Start Ollama + pull model:
   ollama serve
   ollama pull qwen3:4b

4. Install Python dependencies:
   pip3 install -r requirements.txt

5. Start the API:
   cd memorymesh
   uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --reload

6. Start the UI:
   cd memorymesh
   streamlit run ui/app.py --server.port 8501

7. Seed demo data:
   cd memorymesh
   python3 scripts/seed_demo.py
""")


if __name__ == "__main__":
    check_environment()
