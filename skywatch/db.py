"""SQLite store: connection, migrations, and the write operations (ADR-0003).

This module is the only place that speaks SQL. Migrations are forward-only,
tracked via PRAGMA user_version, and applied on every connect.
"""

from __future__ import annotations

import sqlite3
from datetime import timedelta
from typing import TYPE_CHECKING, Iterable

from skywatch.model import ForecastHour, Pass, parse_utc, to_utc_z

if TYPE_CHECKING:
    from skywatch.verdict import Verdict

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
    # 2: verdicts, digest dedup, and digest audit on cycles (milestone 3).
    # Verdicts denormalize the pass fields because pass rows are replaced
    # wholesale on each successful fetch (ADR-0003): no FKs into passes.
    """
    ALTER TABLE cycles ADD COLUMN digest_status TEXT NOT NULL DEFAULT '-';

    CREATE TABLE verdicts (
        id INTEGER PRIMARY KEY,
        cycle_id INTEGER NOT NULL REFERENCES cycles (id),
        pass_source TEXT NOT NULL,
        start_utc TEXT NOT NULL,
        culmination_utc TEXT NOT NULL,
        end_utc TEXT NOT NULL,
        max_elevation_deg REAL NOT NULL,
        start_compass TEXT NOT NULL,
        end_compass TEXT NOT NULL,
        visible INTEGER NOT NULL,
        verdict TEXT NOT NULL CHECK (verdict IN ('go', 'maybe', 'skip')),
        reason TEXT NOT NULL,
        cloud_cover_pct INTEGER,
        created_at_utc TEXT NOT NULL
    );
    CREATE INDEX idx_verdicts_cycle ON verdicts (cycle_id);
    CREATE INDEX idx_verdicts_start ON verdicts (start_utc);

    CREATE TABLE digests (
        id INTEGER PRIMARY KEY,
        local_date TEXT NOT NULL UNIQUE,
        sent_at_utc TEXT NOT NULL,
        subject TEXT NOT NULL,
        pass_count INTEGER NOT NULL
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


def future_passes(conn: sqlite3.Connection, now_utc: str) -> list[Pass]:
    rows = conn.execute(
        "SELECT * FROM passes WHERE start_utc >= ? ORDER BY start_utc", (now_utc,)
    ).fetchall()
    return [
        Pass(
            source=row["source"],
            start_utc=row["start_utc"],
            culmination_utc=row["culmination_utc"],
            end_utc=row["end_utc"],
            max_elevation_deg=row["max_elevation_deg"],
            start_azimuth_deg=row["start_azimuth_deg"],
            end_azimuth_deg=row["end_azimuth_deg"],
            start_compass=row["start_compass"],
            end_compass=row["end_compass"],
            visible=bool(row["visible"]),
        )
        for row in rows
    ]


def forecast_map(conn: sqlite3.Connection) -> dict[str, int]:
    return {
        row["hour_utc"]: row["cloud_cover_pct"]
        for row in conn.execute("SELECT hour_utc, cloud_cover_pct FROM forecast_hours")
    }


def insert_verdicts(
    conn: sqlite3.Connection,
    cycle_id: int,
    verdicts: Iterable["Verdict"],
    created_at_utc: str,
) -> None:
    with conn:
        conn.executemany(
            """
            INSERT INTO verdicts (
                cycle_id, pass_source, start_utc, culmination_utc, end_utc,
                max_elevation_deg, start_compass, end_compass, visible,
                verdict, reason, cloud_cover_pct, created_at_utc
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    cycle_id, v.pass_.source, v.pass_.start_utc,
                    v.pass_.culmination_utc, v.pass_.end_utc,
                    v.pass_.max_elevation_deg, v.pass_.start_compass,
                    v.pass_.end_compass, int(v.pass_.visible),
                    v.verdict, v.reason, v.cloud_cover_pct, created_at_utc,
                )
                for v in verdicts
            ],
        )


def latest_cycle(conn: sqlite3.Connection) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM cycles ORDER BY id DESC LIMIT 1"
    ).fetchone()


def latest_verdicts(conn: sqlite3.Connection, now_utc: str) -> list[sqlite3.Row]:
    """Upcoming verdicts from the most recent cycle that produced any."""
    return conn.execute(
        """
        SELECT * FROM verdicts
        WHERE cycle_id = (SELECT MAX(cycle_id) FROM verdicts)
          AND end_utc >= ?
        ORDER BY start_utc
        """,
        (now_utc,),
    ).fetchall()


def digest_already_sent(conn: sqlite3.Connection, local_date: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM digests WHERE local_date = ?", (local_date,)
    ).fetchone()
    return row is not None


def record_digest(
    conn: sqlite3.Connection,
    local_date: str,
    sent_at_utc: str,
    subject: str,
    pass_count: int,
) -> None:
    with conn:
        conn.execute(
            """
            INSERT INTO digests (local_date, sent_at_utc, subject, pass_count)
            VALUES (?, ?, ?, ?)
            """,
            (local_date, sent_at_utc, subject, pass_count),
        )


def prune(conn: sqlite3.Connection, now_utc: str, retention_days: int) -> dict[str, int]:
    """Delete rows older than the retention window (docs/specs/operations.md).

    Verdicts go when they ended before the cutoff OR when their owning cycle
    is being pruned (whichever comes first), so the cycles delete never trips
    the foreign key.
    """
    cutoff = to_utc_z(parse_utc(now_utc) - timedelta(days=retention_days))
    cutoff_date = cutoff[:10]
    with conn:
        counts = {
            "passes": conn.execute(
                "DELETE FROM passes WHERE end_utc < ?", (cutoff,)
            ).rowcount,
            "forecast_hours": conn.execute(
                "DELETE FROM forecast_hours WHERE hour_utc < ?", (cutoff,)
            ).rowcount,
            "verdicts": conn.execute(
                """
                DELETE FROM verdicts WHERE end_utc < ?
                   OR cycle_id IN (SELECT id FROM cycles WHERE started_at_utc < ?)
                """,
                (cutoff, cutoff),
            ).rowcount,
            "cycles": conn.execute(
                "DELETE FROM cycles WHERE started_at_utc < ?", (cutoff,)
            ).rowcount,
            "digests": conn.execute(
                "DELETE FROM digests WHERE local_date < ?", (cutoff_date,)
            ).rowcount,
        }
    return {table: n for table, n in counts.items() if n}


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
    digest_status: str = "-",
) -> None:
    with conn:
        conn.execute(
            """
            UPDATE cycles
            SET finished_at_utc = ?, passes_status = ?, forecast_status = ?,
                digest_status = ?
            WHERE id = ?
            """,
            (finished_at_utc, passes_status, forecast_status, digest_status, cycle_id),
        )
