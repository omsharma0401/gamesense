"""
main.py — FastAPI application entry point for GameSense backend.

Startup: initialises SQLite + Graphiti, loads config, mounts all routers.
CORS: allows http://localhost:3000 (Next.js frontend).

Run:
    uvicorn main:app --reload --port 8000
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Configure root logger before any other imports
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialise stores and providers on startup; clean up on shutdown."""
    logger.info("GameSense backend starting…")

    # ── Initialise stores ─────────────────────────────────────────────────────
    from memory.session_store import SQLiteSessionStore
    from memory.graph_store   import GraphitiGraphStore
    from llm.openrouter_provider import OpenRouterProvider

    store = SQLiteSessionStore()
    graph = GraphitiGraphStore()
    llm   = OpenRouterProvider()

    await store.init()
    await graph.init()

    # Attach to app.state so routes can access them
    app.state.store = store
    app.state.graph = graph
    app.state.llm   = llm

    # Agent refs — set by session routes during a session
    app.state.capture_agent    = None
    app.state.indexing_agent   = None
    app.state.moment_agent     = None
    app.state.live_coach_agent = None

    logger.info("GameSense backend ready — listening on http://localhost:8000")
    yield

    # ── Shutdown ──────────────────────────────────────────────────────────────
    logger.info("GameSense backend shutting down…")
    await store.close()
    logger.info("Shutdown complete")


app = FastAPI(
    title="GameSense API",
    description="Real-time AI coaching backend for gamers.",
    version="1.0.0",
    lifespan=lifespan,
)

# ── CORS ──────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────────────────
from api.session     import router as session_router
from api.analysis    import router as analysis_router
from api.clips       import router as clips_router
from api.discord     import router as discord_router
from api.suggestions import router as suggestions_router

app.include_router(session_router,     prefix="/session",     tags=["Session"])
app.include_router(analysis_router,    prefix="/analysis",    tags=["Analysis"])
app.include_router(clips_router,       prefix="/clips",       tags=["Clips"])
app.include_router(discord_router,     prefix="/discord",     tags=["Discord"])
app.include_router(suggestions_router, prefix="/suggestions", tags=["Suggestions"])


@app.get("/health")
async def health():
    """Quick health check — used by the frontend to verify the backend is alive."""
    return {"status": "ok", "service": "gamesense-api"}
