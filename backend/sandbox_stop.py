"""
sandbox_stop.py — Stop the running VideoDB sandbox.

Run when done to avoid burning hackathon credits:
    python sandbox_stop.py
"""
import logging
import os
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def main() -> None:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent / ".env")

    api_key    = os.getenv("VIDEO_DB_API_KEY", "")
    sandbox_id = os.getenv("VIDEODB_SANDBOX_ID", "")

    if not api_key:
        logger.error("VIDEO_DB_API_KEY not set")
        sys.exit(1)
    if not sandbox_id:
        logger.error("VIDEODB_SANDBOX_ID not set — nothing to stop")
        sys.exit(1)

    import videodb
    conn    = videodb.connect(api_key=api_key)
    sandbox = conn.get_sandbox(sandbox_id)

    logger.info("Stopping sandbox — id=%s status=%s", sandbox.id, sandbox.status)
    sandbox.stop()
    sandbox.wait_for_stop(timeout=120)
    logger.info("Sandbox stopped — final status=%s", sandbox.status)


if __name__ == "__main__":
    main()
