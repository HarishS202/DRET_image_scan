from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from app.models import ProcessingResult


class DRETRepository:
    def __init__(self, db_path: str = "app/data/dret.db") -> None:
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS dret_orders (
                    order_number TEXT PRIMARY KEY,
                    dealer_name TEXT NOT NULL,
                    rga_number TEXT,
                    rga_document_type TEXT,
                    rejected_document_type TEXT,
                    total_lines INTEGER,
                    auto_applied_lines INTEGER,
                    review_lines INTEGER,
                    estimated_minutes_saved INTEGER,
                    warnings_json TEXT,
                    created_at_utc TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS dret_order_lines (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    order_number TEXT NOT NULL,
                    line_number INTEGER,
                    part_number TEXT,
                    description TEXT,
                    qty_shipped INTEGER,
                    qty_approved INTEGER,
                    qty_rejected INTEGER,
                    confidence REAL,
                    auto_apply INTEGER,
                    rejection_code TEXT,
                    mapped_bms_code TEXT,
                    rejection_comment TEXT,
                    rejection_reason_text TEXT,
                    FOREIGN KEY(order_number) REFERENCES dret_orders(order_number)
                )
                """
            )

    def create_order(self, payload: ProcessingResult) -> str:
        timestamp = datetime.now(timezone.utc)
        order_number = f"DRET-{timestamp.strftime('%Y%m%d%H%M%S')}"
        warnings_json = " | ".join(payload.warnings or [])

        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO dret_orders (
                    order_number,
                    dealer_name,
                    rga_number,
                    rga_document_type,
                    rejected_document_type,
                    total_lines,
                    auto_applied_lines,
                    review_lines,
                    estimated_minutes_saved,
                    warnings_json,
                    created_at_utc
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    order_number,
                    payload.dealer_name,
                    payload.rga_number,
                    payload.rga_document_type,
                    payload.rejected_document_type,
                    payload.total_lines,
                    payload.auto_applied_lines,
                    payload.review_lines,
                    payload.estimated_minutes_saved,
                    warnings_json,
                    timestamp.isoformat(),
                ),
            )

            for line in payload.lines:
                conn.execute(
                    """
                    INSERT INTO dret_order_lines (
                        order_number,
                        line_number,
                        part_number,
                        description,
                        qty_shipped,
                        qty_approved,
                        qty_rejected,
                        confidence,
                        auto_apply,
                        rejection_code,
                        mapped_bms_code,
                        rejection_comment,
                        rejection_reason_text
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        order_number,
                        line.line_number,
                        line.part_number,
                        line.description,
                        line.qty_shipped,
                        line.qty_approved,
                        line.qty_rejected,
                        line.confidence,
                        1 if line.auto_apply else 0,
                        line.rejection.code,
                        line.rejection.mapped_bms_code,
                        line.rejection.comment,
                        line.rejection.reason_text,
                    ),
                )

        return order_number
