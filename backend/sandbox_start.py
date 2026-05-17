"""
sandbox_start.py — Create a VideoDB sandbox and write its ID to .env.

Run once before starting the backend:
    python sandbox_start.py

The sandbox ID is written to .env as VIDEODB_SANDBOX_ID so FastAPI picks it
up on the next reload. Stop the sandbox when done with sandbox_stop.py.
"""
import logging
import os
import re
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

ENV_PATH = Path(__file__).parent / ".env"


def update_env_var(key: str, value: str) -> None:
    """Write or update a single key=value line in .env."""
    env_content = ENV_PATH.read_text() if ENV_PATH.exists() else ""
    pattern = re.compile(rf"^{re.escape(key)}=.*$", re.MULTILINE)
    new_line = f"{key}={value}"
    if pattern.search(env_content):
        env_content = pattern.sub(new_line, env_content)
    else:
        env_content += f"\n{new_line}"
    ENV_PATH.write_text(env_content)
    logger.info("Written %s to .env", key)


def main() -> None:
    from dotenv import load_dotenv
    load_dotenv(ENV_PATH)

    api_key = os.getenv("VIDEO_DB_API_KEY", "")
    if not api_key:
        logger.error("VIDEO_DB_API_KEY not set in .env — cannot create sandbox")
        sys.exit(1)

    import videodb
    from videodb import SandboxTier

    logger.info("Connecting to VideoDB…")
    conn = videodb.connect(api_key=api_key)

    logger.info("Creating sandbox (tier=medium, idle_timeout=600s)…")
    sandbox = conn.create_sandbox(
        tier=SandboxTier.medium,
        idle_timeout=600,  # auto-stop after 10 min idle
    )
    logger.info("Sandbox created — id=%s status=%s", sandbox.id, sandbox.status)

    logger.info("Waiting for sandbox to become active (timeout=300s)…")
    sandbox.wait_for_ready(timeout=300, interval=5)
    logger.info("Sandbox active — id=%s tier=%s", sandbox.id, sandbox.tier)

    update_env_var("VIDEODB_SANDBOX_ID", sandbox.id)
    logger.info("Ready. Run: uvicorn main:app --reload --port 8000")


if __name__ == "__main__":
    main()
