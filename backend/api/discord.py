"""
api/discord.py — Discord webhook share route.

POST /discord/share — sends a clip embed to a Discord channel via webhook.
No OAuth required — uses a pre-configured webhook URL.
"""
import logging
import httpx
from fastapi import APIRouter, HTTPException
from schemas.agent import DiscordShareInput
from config import DISCORD_WEBHOOK_URL

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/share")
async def share_to_discord(body: DiscordShareInput):
    """Send a clip embed to Discord via webhook."""
    webhook_url = body.webhook_url or DISCORD_WEBHOOK_URL
    if not webhook_url:
        raise HTTPException(
            status_code=400,
            detail="No Discord webhook URL configured. Set DISCORD_WEBHOOK_URL in .env.",
        )

    store    = get_store()
    analysis = await store.get_analysis(body.session_id)
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")

    clip = next((c for c in analysis.clips if c.id == body.moment_id), None)
    if not clip:
        raise HTTPException(status_code=404, detail="Clip not found")

    embed = {
        "title": f"🎮 GameSense Clip — {clip.type.upper()}",
        "description": clip.commentary,
        "color": 0xCCFF00,
        "fields": [
            {"name": "Type",     "value": clip.type,                    "inline": True},
            {"name": "Duration", "value": f"{clip.duration:.1f}s",       "inline": True},
        ],
        "url": clip.stream_url,
        "footer": {"text": "Shared via GameSense.ai"},
    }
    payload = {
        "content": "📡 New clip from GameSense:",
        "embeds": [embed],
    }

    logger.info(
        "Sending Discord share — session=%s moment=%s webhook=%s",
        body.session_id, body.moment_id, webhook_url[:40] + "…",
    )

    async with httpx.AsyncClient() as client:
        response = await client.post(webhook_url, json=payload, timeout=10.0)

    if response.status_code not in (200, 204):
        logger.error(
            "Discord webhook failed — status=%d body=%s",
            response.status_code, response.text[:200],
        )
        raise HTTPException(
            status_code=502,
            detail=f"Discord webhook returned {response.status_code}",
        )

    logger.info("Discord share sent successfully")
    return {"status": "shared", "moment_id": body.moment_id}


def get_store():
    from main import app
    return app.state.store
