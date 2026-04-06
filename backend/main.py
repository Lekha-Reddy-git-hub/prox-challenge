"""
FastAPI backend for the Vulcan OmniPro 220 Agent.
Provides chat API with SSE streaming and serves knowledge base assets.
"""

import os
import json
import uuid
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import StreamingResponse, JSONResponse
from dotenv import load_dotenv

load_dotenv()

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
KNOWLEDGE_DIR = Path(__file__).parent.parent / "knowledge"


@asynccontextmanager
async def lifespan(app: FastAPI):
    if not ANTHROPIC_API_KEY or ANTHROPIC_API_KEY == "your-api-key-here":
        print("\n" + "=" * 60)
        print("ERROR: ANTHROPIC_API_KEY not set!")
        print("Please add your API key to the .env file:")
        print("  ANTHROPIC_API_KEY=sk-ant-...")
        print("=" * 60 + "\n")
    else:
        print("\n" + "=" * 60)
        print("Vulcan OmniPro 220 Agent - Backend Running")
        print(f"Knowledge base: {KNOWLEDGE_DIR}")
        print("=" * 60 + "\n")
    yield


app = FastAPI(title="Vulcan OmniPro 220 Agent", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve knowledge page images as static files
pages_dir = KNOWLEDGE_DIR / "pages"
if pages_dir.exists():
    app.mount("/api/pages", StaticFiles(directory=str(pages_dir)), name="pages")

# Also serve product images
product_dir = Path(__file__).parent.parent
app.mount("/api/product", StaticFiles(directory=str(product_dir)), name="product")


def get_agent():
    from backend.agent import VulcanAgent
    return VulcanAgent(api_key=ANTHROPIC_API_KEY)


_agent = None


def agent():
    global _agent
    if _agent is None:
        _agent = get_agent()
    return _agent


@app.post("/api/chat")
async def chat(request: Request):
    """Handle chat messages with SSE streaming."""
    body = await request.json()
    message = body.get("message", "")
    session_id = body.get("session_id", str(uuid.uuid4()))
    images = body.get("images", [])

    if not message and not images:
        return JSONResponse({"error": "Message or images required"}, status_code=400)

    if not ANTHROPIC_API_KEY or ANTHROPIC_API_KEY == "your-api-key-here":
        return JSONResponse(
            {"error": "ANTHROPIC_API_KEY not configured. Please add it to .env"},
            status_code=500,
        )

    def generate():
        try:
            for chunk in agent().chat(session_id, message, images if images else None):
                yield f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"
        except Exception as e:
            error_msg = str(e)
            if "authentication" in error_msg.lower() or "api key" in error_msg.lower():
                yield f"data: {json.dumps({'type': 'error', 'content': 'Invalid API key. Please check your ANTHROPIC_API_KEY in .env'})}\n\n"
            elif "rate" in error_msg.lower():
                yield f"data: {json.dumps({'type': 'error', 'content': 'Rate limited. Please wait a moment and try again.'})}\n\n"
            else:
                yield f"data: {json.dumps({'type': 'error', 'content': f'Error: {error_msg}'})}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/api/clear")
async def clear_session(request: Request):
    """Clear conversation history for a session."""
    body = await request.json()
    session_id = body.get("session_id")
    if session_id:
        agent().clear_session(session_id)
    return {"status": "cleared"}


@app.get("/api/health")
async def health():
    """Health check endpoint."""
    return {
        "status": "ok",
        "api_key_configured": bool(ANTHROPIC_API_KEY and ANTHROPIC_API_KEY != "your-api-key-here"),
        "knowledge_base_loaded": (KNOWLEDGE_DIR / "sections.json").exists(),
    }
