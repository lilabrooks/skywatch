"""SQLite store: connection, migrations, and the write operations (ADR-0003).

This module is the only place that speaks SQL. Migrations are forward-only,
tracked via PRAGMA user_version, and applied on every connect.
"""

from __future__ import annotations

import sqlite3
from typing import Iterable

from skywatch.model import ForecastHour, Pass

MIGRATIONS = [
    # 1: source tables and cycle audit (milestone 2)
    """
    CREATE TABLE passes (
        id INTEGER PRIMARY KEY,
        source TEXT NOT NULL,
        start_utc TEXT NOT NULL,
        culmination_utc TEXT NOT NULL,
        end_utc TEXT NOT NULL,
        max_elevation_deg REAL NOT NULL,
        start_azimuth_deg REAL NOT NULL,
        end_azimuth_deg REAL NOT NULL,
        start_compass TEXT NOT NULL,
        end_compass TEXT NOT NULL,
        visible INTEGER NOT NULL,
        fetched_at_utc TEXT NOT NULL
    );
    CREATE INDEX idx_passes_start ON passes (start_utc);

    CREATE TABLE forecast_hours (
        id INTEGER PRIMARY KEY,
        source TEXT NOT NULL,
        hour_utc TEXT NOT NULL,
        cloud_cover_pct INTEGER NOT NULL,
        fetched_at_utc TEXT NOT NULL,
        UNIQUE (source, hour_utc)
    );

    CREATE TABLE cycles (
        id INTEGER PRIMARY KEY,
        started_at_utc TEXT NOT NULL,
        finished_at_utc TEXT,
        passes_status TEXT NOT NULL DEFAULT 'pending',
        forecast_status TEXT NOT NULL DEFAULT 'pending'
    );
    """,
]


def connect(path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    migrate(conn)
    return conn


def migrate(conn: sqlite3.Connection) -> None:
    version = conn.execute("PRAGMA user_version").fetchone()[0]
    for number in range(version + 1, len(MIGRATIONS) + 1):
        with conn:
            conn.executescript(MIGRATIONS[number - 1])
            conn.execute(f"PRAGMA user_version = {int(number)}")


def replace_future_passes(
    conn: sqlite3.Connection,
    source: str,
    now_utc: str,
    passes: Iterable[Pass],
    fetched_at_utc: str,
) -> None:
    """On a successful fetch, swap out the stored future for this source.

    Past rows are history and stay; a failed fetch must not call this at all,
    so predictions survive upstream outages (ADR-0003).
    """
    with conn:
        conn.execute(
            "DELETE FROM passes WHERE source = ? AND start_utc >= ?",
            (source, now_utc),
        )
        conn.executemany(
            """
            INSERT INTO passes (
                source, start_utc, culmination_utc, end_utc, max_elevation_deg,
                start_azimuth_deg, end_azimuth_deg, start_compass, end_compass,
                visible, fetched_at_utc
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    p.source, p.start_utc, p.culmination_utc, p.end_utc,
                    p.max_elevation_deg, p.start_azimuth_deg, p.end_azimuth_deg,
                    p.start_compass, p.end_compass, int(p.visible), fetched_at_utc,
                )
                for p in passes
            ],
        )


def upsert_forecast_hours(
    conn: sqlite3.Connection, hours: Iterable[ForecastHour], fetched_at_utc: str
) -> None:
    with conn:
        conn.executemany(
            """
            INSERT INTO forecast_hours (source, hour_utc, cloud_cover_pct, fetched_at_utc)
            VALUES (?, ?, ?, ?)
            ON CONFLICT (source, hour_utc) DO UPDATE SET
                cloud_cover_pct = excluded.cloud_cover_pct,
                fetched_at_utc = excluded.fetched_at_utc
            """,
            [(h.source, h.hour_utc, h.cloud_cover_pct, fetched_at_utc) for h in hours],
        )


def start_cycle(conn: sqlite3.Connection, started_at_utc: str) -> int:
    with conn:
        cursor = conn.execute(
            "INSERT INTO cycles (started_at_utc) VALUES (?)", (started_at_utc,)
        )
    return cursor.lastrowid


def finish_cycle(
    conn: sqlite3.Connection,
    cycle_id: int,
    finished_at_utc: str,
    passes_status: str,
    forecast_status: str,
) -> None:
    with conn:
        conn.execute(
            """
            UPDATE cycles
            SET finished_at_utc = ?, passes_status = ?, forecast_status = ?
            WHERE id = ?
            """,
            (finished_at_utc, passes_status, forecast_status, cycle_id),
        )
