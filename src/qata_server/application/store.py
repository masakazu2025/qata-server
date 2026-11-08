"""登録したテストケースと実行の結果を SQLite に、スクショを PNG のファイルに保存する。

記録は契約の形（testcase_record・run）の JSON のまま持つ。中を探す要がないため（S4）。
"""

import re
import sqlite3
import uuid
from collections.abc import Iterator
from contextlib import closing, contextmanager
from pathlib import Path

from qata_server.contracts.server_schema import Run, TestcaseRecord

_ID = re.compile(r"^[a-z]+_[0-9a-f]{32}$")

_TABLES = """
CREATE TABLE IF NOT EXISTS testcases (
    id TEXT PRIMARY KEY,
    app_id TEXT NOT NULL,
    record TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS runs (
    id TEXT PRIMARY KEY,
    testcase_id TEXT NOT NULL,
    record TEXT NOT NULL
);
"""


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


class Store:
    def __init__(self, data_dir: Path) -> None:
        self._db = data_dir / "qata.sqlite3"
        self._screenshots = data_dir / "screenshots"
        self._screenshots.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.executescript(_TABLES)

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        # 呼ぶたびにつなぐ。REST から別のスレッドで呼ばれても困らないように
        with closing(sqlite3.connect(self._db)) as db, db:
            yield db

    # テストケース

    def save_testcase(self, record: TestcaseRecord) -> None:
        with self._connect() as db:
            db.execute(
                "INSERT INTO testcases (id, app_id, record) VALUES (?, ?, ?)"
                " ON CONFLICT (id) DO UPDATE SET record = excluded.record",
                (
                    record.id.root,
                    record.testcase.app_id.root,
                    record.model_dump_json(exclude_none=True),
                ),
            )

    def get_testcase(self, testcase_id: str) -> TestcaseRecord | None:
        with self._connect() as db:
            row = db.execute(
                "SELECT record FROM testcases WHERE id = ?", (testcase_id,)
            ).fetchone()
        return TestcaseRecord.model_validate_json(row[0]) if row else None

    def list_testcases(self, app_id: str | None = None) -> list[TestcaseRecord]:
        """新しい順。"""
        with self._connect() as db:
            rows = db.execute(
                "SELECT record FROM testcases WHERE ? IS NULL OR app_id = ?"
                " ORDER BY rowid DESC",
                (app_id, app_id),
            ).fetchall()
        return [TestcaseRecord.model_validate_json(r[0]) for r in rows]

    def delete_testcase(self, testcase_id: str) -> bool:
        """消したら True。実行の結果は残す。"""
        with self._connect() as db:
            cursor = db.execute("DELETE FROM testcases WHERE id = ?", (testcase_id,))
        return cursor.rowcount > 0

    # 実行の結果

    def save_run(self, run: Run) -> None:
        with self._connect() as db:
            db.execute(
                "INSERT INTO runs (id, testcase_id, record) VALUES (?, ?, ?)",
                (
                    run.id.root,
                    run.testcase_id.root,
                    run.model_dump_json(exclude_none=True),
                ),
            )

    def get_run(self, run_id: str) -> Run | None:
        with self._connect() as db:
            row = db.execute(
                "SELECT record FROM runs WHERE id = ?", (run_id,)
            ).fetchone()
        return Run.model_validate_json(row[0]) if row else None

    def list_runs(self, testcase_id: str | None = None) -> list[Run]:
        """新しい順。"""
        with self._connect() as db:
            rows = db.execute(
                "SELECT record FROM runs WHERE ? IS NULL OR testcase_id = ?"
                " ORDER BY rowid DESC",
                (testcase_id, testcase_id),
            ).fetchall()
        return [Run.model_validate_json(r[0]) for r in rows]

    # スクショ

    def save_screenshot(self, png: bytes) -> str:
        screenshot_id = new_id("ss")
        (self._screenshots / f"{screenshot_id}.png").write_bytes(png)
        return screenshot_id

    def get_screenshot(self, screenshot_id: str) -> bytes | None:
        # ID はファイルの名前に使うので、振った形のものだけを受ける
        if not _ID.match(screenshot_id):
            return None
        path = self._screenshots / f"{screenshot_id}.png"
        return path.read_bytes() if path.is_file() else None
