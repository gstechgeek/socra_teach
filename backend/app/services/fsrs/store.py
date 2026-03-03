from __future__ import annotations

import asyncio
from typing import Any

import pyarrow as pa  # type: ignore[import-untyped]
import pyarrow.compute as pc  # type: ignore[import-untyped]

from app.services.rag.store import get_db

# ── Table names ───────────────────────────────────────────────────────────────

_REVIEW_CARDS_TABLE = "review_cards"
_REVIEW_LOGS_TABLE = "review_logs"
_CONCEPTS_TABLE = "concepts"
_CONCEPT_PREREQS_TABLE = "concept_prerequisites"
_CONCEPT_MASTERY_TABLE = "concept_mastery"
_DAILY_STATS_TABLE = "daily_stats"

# ── PyArrow schemas ───────────────────────────────────────────────────────────

REVIEW_CARD_SCHEMA = pa.schema(
    [
        pa.field("card_id", pa.string()),
        pa.field("front", pa.string()),
        pa.field("back", pa.string()),
        pa.field("concept_id", pa.string()),
        pa.field("source_message_id", pa.string()),
        pa.field("session_id", pa.string()),
        pa.field("state", pa.int32()),
        pa.field("step", pa.int32()),
        pa.field("stability", pa.float64()),
        pa.field("difficulty", pa.float64()),
        pa.field("due", pa.string()),
        pa.field("last_review", pa.string()),
        pa.field("reps", pa.int32()),
        pa.field("lapses", pa.int32()),
        pa.field("created_at", pa.string()),
    ]
)

REVIEW_LOG_SCHEMA = pa.schema(
    [
        pa.field("log_id", pa.string()),
        pa.field("card_id", pa.string()),
        pa.field("rating", pa.int32()),
        pa.field("review_datetime", pa.string()),
        pa.field("review_duration_ms", pa.int32()),
        pa.field("state_before", pa.int32()),
        pa.field("state_after", pa.int32()),
    ]
)

CONCEPT_SCHEMA = pa.schema(
    [
        pa.field("concept_id", pa.string()),
        pa.field("name", pa.string()),
        pa.field("description", pa.string()),
        pa.field("source_doc_id", pa.string()),
        pa.field("created_at", pa.string()),
    ]
)

CONCEPT_PREREQUISITE_SCHEMA = pa.schema(
    [
        pa.field("edge_id", pa.string()),
        pa.field("concept_id", pa.string()),
        pa.field("prerequisite_id", pa.string()),
    ]
)

CONCEPT_MASTERY_SCHEMA = pa.schema(
    [
        pa.field("concept_id", pa.string()),
        pa.field("p_know", pa.float64()),
        pa.field("p_slip", pa.float64()),
        pa.field("p_guess", pa.float64()),
        pa.field("p_transit", pa.float64()),
        pa.field("total_attempts", pa.int32()),
        pa.field("correct_attempts", pa.int32()),
        pa.field("last_updated", pa.string()),
    ]
)

DAILY_STATS_SCHEMA = pa.schema(
    [
        pa.field("date", pa.string()),
        pa.field("reviews_completed", pa.int32()),
        pa.field("cards_created", pa.int32()),
        pa.field("concepts_learned", pa.int32()),
        pa.field("streak_days", pa.int32()),
        pa.field("session_minutes", pa.int32()),
    ]
)


# ── Table accessors ───────────────────────────────────────────────────────────


def _get_table(name: str, schema: pa.Schema) -> Any:
    """Open or create a LanceDB table."""
    db = get_db()
    if name in db.table_names():
        return db.open_table(name)
    return db.create_table(name, schema=schema)


def get_review_cards_table() -> Any:
    """Open or create the review_cards table."""
    return _get_table(_REVIEW_CARDS_TABLE, REVIEW_CARD_SCHEMA)


def get_review_logs_table() -> Any:
    """Open or create the review_logs table."""
    return _get_table(_REVIEW_LOGS_TABLE, REVIEW_LOG_SCHEMA)


def get_concepts_table() -> Any:
    """Open or create the concepts table."""
    return _get_table(_CONCEPTS_TABLE, CONCEPT_SCHEMA)


def get_concept_prerequisites_table() -> Any:
    """Open or create the concept_prerequisites table."""
    return _get_table(_CONCEPT_PREREQS_TABLE, CONCEPT_PREREQUISITE_SCHEMA)


def get_concept_mastery_table() -> Any:
    """Open or create the concept_mastery table."""
    return _get_table(_CONCEPT_MASTERY_TABLE, CONCEPT_MASTERY_SCHEMA)


def get_daily_stats_table() -> Any:
    """Open or create the daily_stats table."""
    return _get_table(_DAILY_STATS_TABLE, DAILY_STATS_SCHEMA)


# ── Write helpers (sync) ─────────────────────────────────────────────────────


def upsert_review_card(card_dict: dict[str, Any]) -> None:
    """Insert or replace a review card row."""
    tbl = get_review_cards_table()
    try:
        tbl.delete(f'card_id = "{card_dict["card_id"]}"')
    except Exception:  # noqa: BLE001
        pass
    tbl.add([card_dict])


def batch_upsert_review_cards(cards: list[dict[str, Any]]) -> None:
    """Insert or replace multiple review card rows."""
    if not cards:
        return
    tbl = get_review_cards_table()
    for card in cards:
        try:
            tbl.delete(f'card_id = "{card["card_id"]}"')
        except Exception:  # noqa: BLE001
            pass
    tbl.add(cards)


def insert_review_log(log_dict: dict[str, Any]) -> None:
    """Append a review log entry."""
    tbl = get_review_logs_table()
    tbl.add([log_dict])


def upsert_concept(concept_dict: dict[str, Any]) -> None:
    """Insert or replace a concept row."""
    tbl = get_concepts_table()
    try:
        tbl.delete(f'concept_id = "{concept_dict["concept_id"]}"')
    except Exception:  # noqa: BLE001
        pass
    tbl.add([concept_dict])


def insert_prerequisite_edge(edge_dict: dict[str, Any]) -> None:
    """Insert a prerequisite edge."""
    tbl = get_concept_prerequisites_table()
    tbl.add([edge_dict])


def upsert_concept_mastery(mastery_dict: dict[str, Any]) -> None:
    """Insert or replace a concept mastery row."""
    tbl = get_concept_mastery_table()
    try:
        tbl.delete(f'concept_id = "{mastery_dict["concept_id"]}"')
    except Exception:  # noqa: BLE001
        pass
    tbl.add([mastery_dict])


def upsert_daily_stats(stats_dict: dict[str, Any]) -> None:
    """Insert or replace a daily stats row."""
    tbl = get_daily_stats_table()
    try:
        tbl.delete(f'date = "{stats_dict["date"]}"')
    except Exception:  # noqa: BLE001
        pass
    tbl.add([stats_dict])


def delete_review_card(card_id: str) -> None:
    """Delete a review card and its logs."""
    db = get_db()
    if _REVIEW_CARDS_TABLE in db.table_names():
        get_review_cards_table().delete(f'card_id = "{card_id}"')
    if _REVIEW_LOGS_TABLE in db.table_names():
        get_review_logs_table().delete(f'card_id = "{card_id}"')


# ── Read helpers (sync) ──────────────────────────────────────────────────────


def get_review_card(card_id: str) -> dict[str, Any] | None:
    """Fetch a single review card by ID."""
    db = get_db()
    if _REVIEW_CARDS_TABLE not in db.table_names():
        return None
    tbl = get_review_cards_table()
    arrow_tbl = tbl.to_arrow()
    mask = pc.equal(arrow_tbl["card_id"], card_id)
    rows = arrow_tbl.filter(mask).to_pylist()
    return rows[0] if rows else None


def get_all_review_cards() -> list[dict[str, Any]]:
    """Return all review cards."""
    db = get_db()
    if _REVIEW_CARDS_TABLE not in db.table_names():
        return []
    return get_review_cards_table().to_arrow().to_pylist()


def get_due_review_cards(now_iso: str) -> list[dict[str, Any]]:
    """Return review cards where due <= now_iso, sorted by due date."""
    db = get_db()
    if _REVIEW_CARDS_TABLE not in db.table_names():
        return []
    tbl = get_review_cards_table()
    arrow_tbl = tbl.to_arrow()
    mask = pc.less_equal(arrow_tbl["due"], pa.scalar(now_iso, type=pa.string()))
    rows = arrow_tbl.filter(mask).to_pylist()
    return sorted(rows, key=lambda r: r["due"])


def get_review_logs_for_card(card_id: str) -> list[dict[str, Any]]:
    """Return all review logs for a given card."""
    db = get_db()
    if _REVIEW_LOGS_TABLE not in db.table_names():
        return []
    tbl = get_review_logs_table()
    arrow_tbl = tbl.to_arrow()
    mask = pc.equal(arrow_tbl["card_id"], card_id)
    return arrow_tbl.filter(mask).to_pylist()


def get_all_concepts() -> list[dict[str, Any]]:
    """Return all concepts."""
    db = get_db()
    if _CONCEPTS_TABLE not in db.table_names():
        return []
    return get_concepts_table().to_arrow().to_pylist()


def get_concept(concept_id: str) -> dict[str, Any] | None:
    """Fetch a single concept by ID."""
    db = get_db()
    if _CONCEPTS_TABLE not in db.table_names():
        return None
    tbl = get_concepts_table()
    arrow_tbl = tbl.to_arrow()
    mask = pc.equal(arrow_tbl["concept_id"], concept_id)
    rows = arrow_tbl.filter(mask).to_pylist()
    return rows[0] if rows else None


def get_concept_by_name(name: str) -> dict[str, Any] | None:
    """Fetch a concept by its name (case-sensitive)."""
    db = get_db()
    if _CONCEPTS_TABLE not in db.table_names():
        return None
    tbl = get_concepts_table()
    arrow_tbl = tbl.to_arrow()
    mask = pc.equal(arrow_tbl["name"], name)
    rows = arrow_tbl.filter(mask).to_pylist()
    return rows[0] if rows else None


def get_all_prerequisites() -> list[dict[str, Any]]:
    """Return all concept prerequisite edges."""
    db = get_db()
    if _CONCEPT_PREREQS_TABLE not in db.table_names():
        return []
    return get_concept_prerequisites_table().to_arrow().to_pylist()


def get_all_concept_mastery() -> list[dict[str, Any]]:
    """Return all concept mastery records."""
    db = get_db()
    if _CONCEPT_MASTERY_TABLE not in db.table_names():
        return []
    return get_concept_mastery_table().to_arrow().to_pylist()


def get_concept_mastery(concept_id: str) -> dict[str, Any] | None:
    """Fetch mastery state for a single concept."""
    db = get_db()
    if _CONCEPT_MASTERY_TABLE not in db.table_names():
        return None
    tbl = get_concept_mastery_table()
    arrow_tbl = tbl.to_arrow()
    mask = pc.equal(arrow_tbl["concept_id"], concept_id)
    rows = arrow_tbl.filter(mask).to_pylist()
    return rows[0] if rows else None


def get_daily_stats(date_str: str) -> dict[str, Any] | None:
    """Fetch stats for a specific date (YYYY-MM-DD)."""
    db = get_db()
    if _DAILY_STATS_TABLE not in db.table_names():
        return None
    tbl = get_daily_stats_table()
    arrow_tbl = tbl.to_arrow()
    mask = pc.equal(arrow_tbl["date"], date_str)
    rows = arrow_tbl.filter(mask).to_pylist()
    return rows[0] if rows else None


def get_stats_range(start_date: str, end_date: str) -> list[dict[str, Any]]:
    """Return daily stats for a date range (inclusive)."""
    db = get_db()
    if _DAILY_STATS_TABLE not in db.table_names():
        return []
    tbl = get_daily_stats_table()
    arrow_tbl = tbl.to_arrow()
    after_start = pc.greater_equal(arrow_tbl["date"], pa.scalar(start_date, type=pa.string()))
    before_end = pc.less_equal(arrow_tbl["date"], pa.scalar(end_date, type=pa.string()))
    mask = pc.and_(after_start, before_end)
    rows = arrow_tbl.filter(mask).to_pylist()
    return sorted(rows, key=lambda r: r["date"])


def get_cards_for_concept(concept_id: str) -> list[dict[str, Any]]:
    """Return all review cards for a given concept."""
    db = get_db()
    if _REVIEW_CARDS_TABLE not in db.table_names():
        return []
    tbl = get_review_cards_table()
    arrow_tbl = tbl.to_arrow()
    mask = pc.equal(arrow_tbl["concept_id"], concept_id)
    return arrow_tbl.filter(mask).to_pylist()


# ── Async wrappers ────────────────────────────────────────────────────────────


async def async_upsert_review_card(card_dict: dict[str, Any]) -> None:
    """Async wrapper for upsert_review_card."""
    await asyncio.to_thread(upsert_review_card, card_dict)


async def async_get_review_card(card_id: str) -> dict[str, Any] | None:
    """Async wrapper for get_review_card."""
    return await asyncio.to_thread(get_review_card, card_id)


async def async_get_due_review_cards(now_iso: str) -> list[dict[str, Any]]:
    """Async wrapper for get_due_review_cards."""
    return await asyncio.to_thread(get_due_review_cards, now_iso)


async def async_get_all_review_cards() -> list[dict[str, Any]]:
    """Async wrapper for get_all_review_cards."""
    return await asyncio.to_thread(get_all_review_cards)


async def async_get_all_concepts() -> list[dict[str, Any]]:
    """Async wrapper for get_all_concepts."""
    return await asyncio.to_thread(get_all_concepts)


async def async_get_all_prerequisites() -> list[dict[str, Any]]:
    """Async wrapper for get_all_prerequisites."""
    return await asyncio.to_thread(get_all_prerequisites)


async def async_get_all_concept_mastery() -> list[dict[str, Any]]:
    """Async wrapper for get_all_concept_mastery."""
    return await asyncio.to_thread(get_all_concept_mastery)


async def async_get_concept_mastery(concept_id: str) -> dict[str, Any] | None:
    """Async wrapper for get_concept_mastery."""
    return await asyncio.to_thread(get_concept_mastery, concept_id)


async def async_upsert_concept_mastery(mastery_dict: dict[str, Any]) -> None:
    """Async wrapper for upsert_concept_mastery."""
    await asyncio.to_thread(upsert_concept_mastery, mastery_dict)


async def async_get_daily_stats(date_str: str) -> dict[str, Any] | None:
    """Async wrapper for get_daily_stats."""
    return await asyncio.to_thread(get_daily_stats, date_str)


async def async_get_stats_range(start: str, end: str) -> list[dict[str, Any]]:
    """Async wrapper for get_stats_range."""
    return await asyncio.to_thread(get_stats_range, start, end)


async def async_upsert_daily_stats(stats_dict: dict[str, Any]) -> None:
    """Async wrapper for upsert_daily_stats."""
    await asyncio.to_thread(upsert_daily_stats, stats_dict)
