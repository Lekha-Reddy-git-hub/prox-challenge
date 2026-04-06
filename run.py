"""
Single entry point to run the Vulcan OmniPro 220 Agent.
Starts both the FastAPI backend and Vite frontend dev server.
"""

import os
import sys
import subprocess
import signal
import time
from pathlib import Path

ROOT = Path(__file__).parent
BACKEND_DIR = ROOT
FRONTEND_DIR = ROOT / "frontend"


def check_env():
    env_path = ROOT / ".env"
    if not env_path.exists():
        print("\n" + "=" * 60)
        print("ERROR: .env file not found!")
        print("")
        print("  cp .env.example .env")
        print("  # Then add your ANTHROPIC_API_KEY")
        print("=" * 60 + "\n")
        sys.exit(1)

    with open(env_path) as f:
        content = f.read()
    if "your-api-key-here" in content or "ANTHROPIC_API_KEY=" not in content:
        print("\n" + "=" * 60)
        print("WARNING: ANTHROPIC_API_KEY not set in .env")
        print("The backend will start but API calls will fail.")
        print("=" * 60 + "\n")


def check_deps():
    # Check Python deps
    try:
        import fastapi  # noqa: F401
        import anthropic  # noqa: F401
    except ImportError:
        print("Installing Python dependencies...")
        subprocess.run([sys.executable, "-m", "pip", "install", "-r", str(ROOT / "requirements.txt")], check=True)

    # Check frontend deps
    node_modules = FRONTEND_DIR / "node_modules"
    if not node_modules.exists():
        print("Installing frontend dependencies...")
        subprocess.run(["npm", "install"], cwd=str(FRONTEND_DIR), check=True, shell=True)


def main():
    check_env()
    check_deps()

    print("\n" + "=" * 60)
    print("  Vulcan OmniPro 220 Agent")
    print("  Backend:  http://localhost:8000")
    print("  Frontend: http://localhost:5173")
    print("=" * 60 + "\n")

    processes = []

    try:
        # Start backend
        backend = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "backend.main:app",
             "--host", "0.0.0.0", "--port", "8000", "--reload"],
            cwd=str(ROOT),
        )
        processes.append(backend)

        # Start frontend
        frontend = subprocess.Popen(
            ["npm", "run", "dev"],
            cwd=str(FRONTEND_DIR),
            shell=True,
        )
        processes.append(frontend)

        # Wait for either to exit
        while True:
            for p in processes:
                if p.poll() is not None:
                    raise KeyboardInterrupt
            time.sleep(1)

    except KeyboardInterrupt:
        print("\nShutting down...")
        for p in processes:
            try:
                p.terminate()
                p.wait(timeout=5)
            except Exception:
                p.kill()
        print("Done.")


if __name__ == "__main__":
    main()
