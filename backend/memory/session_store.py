"""
memory/session_store.py — SQLite-backed implementation of BaseSessionStore.

Uses aiosqlite for fully async reads/writes. All writes are serialised through
a single asyncio.Lock to prevent concurrent write corruption.

Schema:
  sessions   — one row per gaming session
  moments    — one row per detected moment, FK → sessions
  analyses   — one row per post-session analysis (JSON blob)
  briefings  — one row per coaching brief
  highlights — one row per highlight reel
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Optional

import aiosqlite

from memory.interfaces import BaseSessionStore
from schemas.session import (
    Session, SessionSummary, Moment, Briefing,
    AnalysisResult, HighlightReel, Score, Clip,
)
from config import SQLITE_DB_PATH

logger = logging.getLogger(__name__)

# Module-level write lock — shared across all instances
_write_lock = asyncio.Lock()


class SQLiteSessionStore(BaseSessionStore):
    """
    Async SQLite session store. One connection per store instance.
    Safe for concurrent reads; all writes are serialised via _write_lock.
    """

    def __init__(self, db_path: str | None = None):
        self._db_path = str(db_path or SQLITE_DB_PATH)
        self._conn: aiosqlite.Connection | None = None
        logger.info("SQLiteSessionStore configured — db=%s", self._db_path)

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    async def init(self) -> None:
        """Open connection and create tables if they don't exist."""
        logger.info("Initialising SQLite DB at %s", self._db_path)
        self._conn = await aiosqlite.connect(self._db_path)
        self._conn.row_factory = aiosqlite.Row
        await self._create_tables()
        logger.info("SQLite DB ready")

    async def close(self) -> None:
        if self._conn:
            await self._conn.close()
            logger.info("SQLite connection closed")

    async def _create_tables(self) -> None:
        assert self._conn
        await self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS sessions (
                id              TEXT PRIMARY KEY,
                player_id       TEXT NOT NULL,
                genre           TEXT NOT NULL,
                status          TEXT NOT NULL DEFAULT 'active',
                video_id        TEXT,
                rtstream_id     TEXT,
                score_overall   INTEGER,
                score_mechanics INTEGER,
                score_decision  INTEGER,
                score_consistency INTEGER,
                moments_detected INTEGER DEFAULT 0,
                highlights_url  TEXT,
                started_at      TEXT NOT NULL,
                ended_at        TEXT
            );

            CREATE TABLE IF NOT EXISTS moments (
                id              TEXT PRIMARY KEY,
                session_id      TEXT NOT NULL,
                type            TEXT NOT NULL,
                timestamp_ms    INTEGER NOT NULL,
                description     TEXT NOT NULL,
                significance    INTEGER NOT NULL,
                clip_url        TEXT,
                commentary      TEXT,
                created_at      TEXT NOT NULL,
                FOREIGN KEY (session_id) REFERENCES sessions(id)
            );

            CREATE INDEX IF NOT EXISTS idx_moments_session
                ON moments(session_id, timestamp_ms);

            CREATE TABLE IF NOT EXISTS analyses (
                session_id  TEXT PRIMARY KEY,
                data        TEXT NOT NULL,      -- full AnalysisResult JSON
                created_at  TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS briefings (
                id          TEXT PRIMARY KEY,
                player_id   TEXT NOT NULL,
                data        TEXT NOT NULL,      -- full Briefing JSON
                created_at  TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_briefings_player
                ON briefings(player_id, created_at DESC);

            CREATE TABLE IF NOT EXISTS highlights (
                session_id  TEXT PRIMARY KEY,
                data        TEXT NOT NULL,      -- full HighlightReel JSON
                created_at  TEXT NOT NULL
            );
        """)
        await self._conn.commit()
        logger.debug("SQLite tables created / verified")

    # ── Session CRUD ──────────────────────────────────────────────────────────

    async def create_session(self, session: Session) -> None:
        logger.info("Creating session row — id=%s genre=%s", session.id, session.genre)
        async with _write_lock:
            assert self._conn
            await self._conn.execute(
                """INSERT INTO sessions
                   (id, player_id, genre, status, video_id, rtstream_id,
                    moments_detected, started_at, ended_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    session.id, session.player_id, session.genre, session.status,
                    session.video_id, session.rtstream_id,
                    session.moments_detected,
                    session.started_at.isoformat(),
                    session.ended_at.isoformat() if session.ended_at else None,
                ),
            )
            await self._conn.commit()

    async def get_session(self, session_id: str) -> Optional[Session]:
        assert self._conn
        async with self._conn.execute(
            "SELECT * FROM sessions WHERE id = ?", (session_id,)
        ) as cursor:
            row = await cursor.fetchone()
        if not row:
            logger.debug("Session not found — id=%s", session_id)
            return None
        return self._row_to_session(row)

    async def update_session(self, session: Session) -> None:
        logger.info("Updating session — id=%s status=%s", session.id, session.status)
        async with _write_lock:
            assert self._conn
            await self._conn.execute(
                """UPDATE sessions SET
                   status=?, video_id=?, rtstream_id=?,
                   score_overall=?, score_mechanics=?, score_decision=?,
                   score_consistency=?, moments_detected=?, highlights_url=?,
                   ended_at=?
                   WHERE id=?""",
                (
                    session.status, session.video_id, session.rtstream_id,
                    session.score.overall if session.score else None,
                    session.score.mechanics if session.score else None,
                    session.score.decision_making if session.score else None,
                    session.score.consistency if session.score else None,
                    session.moments_detected,
                    session.highlights_url,
                    session.ended_at.isoformat() if session.ended_at else None,
                    session.id,
                ),
            )
            await self._conn.commit()

    async def get_active_session(self) -> Optional[Session]:
        assert self._conn
        async with self._conn.execute(
            "SELECT * FROM sessions WHERE status = 'active' ORDER BY started_at DESC LIMIT 1"
        ) as cursor:
            row = await cursor.fetchone()
        if not row:
            return None
        logger.debug("Active session found — id=%s", row["id"])
        return self._row_to_session(row)

    async def get_session_history(
        self, player_id: str, limit: int = 10
    ) -> list[SessionSummary]:
        assert self._conn
        async with self._conn.execute(
            """SELECT id, genre, score_overall, score_mechanics, score_decision,
                      score_consistency, moments_detected, started_at, ended_at
               FROM sessions
               WHERE player_id = ? AND status != 'active'
               ORDER BY started_at DESC
               LIMIT ?""",
            (player_id, limit),
        ) as cursor:
            rows = await cursor.fetchall()

        summaries = [
            SessionSummary(
                id=r["id"],
                genre=r["genre"],
                score=r["score_overall"],
                mechanics=r["score_mechanics"],
                decision_making=r["score_decision"],
                consistency=r["score_consistency"],
                moments_detected=r["moments_detected"] or 0,
                started_at=r["started_at"],
                ended_at=r["ended_at"],
            )
            for r in rows
        ]
        logger.debug("Fetched %d sessions for player=%s", len(summaries), player_id)
        return summaries

    # ── Moment CRUD ───────────────────────────────────────────────────────────

    async def add_moment(self, moment: Moment) -> None:
        logger.info(
            "Adding moment — session=%s type=%s ts=%dms significance=%d",
            moment.session_id, moment.type, moment.timestamp_ms, moment.significance,
        )
        async with _write_lock:
            assert self._conn
            await self._conn.execute(
                """INSERT OR IGNORE INTO moments
                   (id, session_id, type, timestamp_ms, description,
                    significance, clip_url, commentary, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    moment.id, moment.session_id, moment.type,
                    moment.timestamp_ms, moment.description,
                    moment.significance, moment.clip_url, moment.commentary,
                    moment.created_at.isoformat(),
                ),
            )
            # Bump the moment counter on the parent session
            await self._conn.execute(
                "UPDATE sessions SET moments_detected = moments_detected + 1 WHERE id = ?",
                (moment.session_id,),
            )
            await self._conn.commit()

    async def get_moments(self, session_id: str) -> list[Moment]:
        assert self._conn
        async with self._conn.execute(
            "SELECT * FROM moments WHERE session_id = ? ORDER BY timestamp_ms ASC",
            (session_id,),
        ) as cursor:
            rows = await cursor.fetchall()

        moments = [self._row_to_moment(r) for r in rows]
        logger.debug("Fetched %d moments for session=%s", len(moments), session_id)
        return moments

    # ── Analysis ──────────────────────────────────────────────────────────────

    async def save_analysis(self, analysis: AnalysisResult) -> None:
        logger.info("Saving analysis — session=%s score=%d", analysis.session_id, analysis.score.overall)
        async with _write_lock:
            assert self._conn
            from datetime import datetime
            await self._conn.execute(
                """INSERT OR REPLACE INTO analyses (session_id, data, created_at)
                   VALUES (?, ?, ?)""",
                (
                    analysis.session_id,
                    analysis.model_dump_json(),
                    datetime.utcnow().isoformat(),
                ),
            )
            await self._conn.commit()

    async def get_analysis(self, session_id: str) -> Optional[AnalysisResult]:
        assert self._conn
        async with self._conn.execute(
            "SELECT data FROM analyses WHERE session_id = ?", (session_id,)
        ) as cursor:
            row = await cursor.fetchone()
        if not row:
            return None
        return AnalysisResult.model_validate_json(row["data"])

    # ── Briefing ──────────────────────────────────────────────────────────────

    async def save_briefing(self, briefing: Briefing) -> None:
        logger.info("Saving briefing — player=%s", briefing.player_id)
        async with _write_lock:
            assert self._conn
            await self._conn.execute(
                """INSERT INTO briefings (id, player_id, data, created_at)
                   VALUES (?, ?, ?, ?)""",
                (
                    briefing.id,
                    briefing.player_id,
                    briefing.model_dump_json(),
                    briefing.created_at.isoformat(),
                ),
            )
            await self._conn.commit()

    async def get_latest_briefing(self, player_id: str) -> Optional[Briefing]:
        assert self._conn
        async with self._conn.execute(
            """SELECT data FROM briefings
               WHERE player_id = ?
               ORDER BY created_at DESC LIMIT 1""",
            (player_id,),
        ) as cursor:
            row = await cursor.fetchone()
        if not row:
            return None
        return Briefing.model_validate_json(row["data"])

    # ── Highlight Reel ────────────────────────────────────────────────────────

    async def save_highlight_reel(self, reel: HighlightReel) -> None:
        logger.info("Saving highlight reel — session=%s status=%s", reel.session_id, reel.status)
        async with _write_lock:
            assert self._conn
            await self._conn.execute(
                """INSERT OR REPLACE INTO highlights (session_id, data, created_at)
                   VALUES (?, ?, ?)""",
                (
                    reel.session_id,
                    reel.model_dump_json(),
                    reel.created_at.isoformat(),
                ),
            )
            await self._conn.commit()

    async def get_highlight_reel(self, session_id: str) -> Optional[HighlightReel]:
        assert self._conn
        async with self._conn.execute(
            "SELECT data FROM highlights WHERE session_id = ?", (session_id,)
        ) as cursor:
            row = await cursor.fetchone()
        if not row:
            return None
        return HighlightReel.model_validate_json(row["data"])

    # ── Row → Model helpers ───────────────────────────────────────────────────

    @staticmethod
    def _row_to_session(row: aiosqlite.Row) -> Session:
        from datetime import datetime
        score = None
        if row["score_overall"] is not None:
            score = Score(
                overall=row["score_overall"],
                mechanics=row["score_mechanics"],
                decision_making=row["score_decision"],
                consistency=row["score_consistency"],
            )
        return Session(
            id=row["id"],
            player_id=row["player_id"],
            genre=row["genre"],
            status=row["status"],
            video_id=row["video_id"],
            rtstream_id=row["rtstream_id"],
            score=score,
            moments_detected=row["moments_detected"] or 0,
            highlights_url=row["highlights_url"],
            started_at=datetime.fromisoformat(row["started_at"]),
            ended_at=datetime.fromisoformat(row["ended_at"]) if row["ended_at"] else None,
        )

    @staticmethod
    def _row_to_moment(row: aiosqlite.Row) -> Moment:
        from datetime import datetime
        return Moment(
            id=row["id"],
            session_id=row["session_id"],
            type=row["type"],
            timestamp_ms=row["timestamp_ms"],
            description=row["description"],
            significance=row["significance"],
            clip_url=row["clip_url"],
            commentary=row["commentary"],
            created_at=datetime.fromisoformat(row["created_at"]),
        )
