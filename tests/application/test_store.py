"""保存の表の形とマイグレーション。

Alembic を入れる前の保存先（表はあるが、マイグレーションの記録がない）を
そのまま読めることと、表の定義（store.METADATA）とマイグレーションがずれていないことを確かめる。
"""

import sqlite3
from contextlib import closing
from pathlib import Path

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine
from support import load_example

from qata_server.application import Store
from qata_server.application.store import METADATA, MIGRATIONS, database_url

# Test で始まる名前は pytest がテストの class として集めるので、別の名前で読む
from qata_server.contracts.server_schema import Run
from qata_server.contracts.server_schema import TestcaseRecord as Record

_REPO = Path(__file__).resolve().parents[2]

# Alembic を入れる前の store.py が作っていた表（そのまま写したもの）
_OLD_TABLES = """
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


def _testcase(n: int) -> Record:
    record = Record.model_validate(load_example("testcase-record.json"))
    return record.model_copy(update={"id": type(record.id)(f"tc_{n:032x}")})


def _run(n: int, testcase: Record) -> Run:
    run = Run.model_validate(load_example("run.json"))
    return run.model_copy(
        update={"id": type(run.id)(f"run_{n:032x}"), "testcase_id": testcase.id}
    )


def _write_old_store(data_dir: Path, records: list[Record], runs: list[Run]):
    """古い store.py と同じやり方で、表を作って記録を入れる。"""
    data_dir.mkdir(parents=True)
    with closing(sqlite3.connect(data_dir / "qata.sqlite3")) as db, db:
        db.executescript(_OLD_TABLES)
        for r in records:
            db.execute(
                "INSERT INTO testcases (id, app_id, record) VALUES (?, ?, ?)",
                (
                    r.id.root,
                    r.testcase.app_id.root,
                    r.model_dump_json(exclude_none=True),
                ),
            )
        for run in runs:
            db.execute(
                "INSERT INTO runs (id, testcase_id, record) VALUES (?, ?, ?)",
                (
                    run.id.root,
                    run.testcase_id.root,
                    run.model_dump_json(exclude_none=True),
                ),
            )


def _revision(data_dir: Path) -> str | None:
    with create_engine(database_url(data_dir)).connect() as connection:
        return MigrationContext.configure(connection).get_current_revision()


def _head() -> str | None:
    return ScriptDirectory(str(MIGRATIONS)).get_current_head()


def test_古い保存先の記録を読めて新しい順も変わらない(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    first, second = _testcase(1), _testcase(2)
    old_run = _run(1, first)
    _write_old_store(data_dir, [first, second], [old_run])

    store = Store(data_dir)

    assert _revision(data_dir) == _head()
    assert store.get_testcase(first.id.root) == first
    assert store.list_testcases() == [second, first]
    assert store.list_runs(first.id.root) == [old_run]

    # 移したあとに足したものは、前からあるものより新しい
    third = _testcase(3)
    store.save_testcase(third)
    assert store.list_testcases() == [third, second, first]
    new_run = _run(2, first)
    store.save_run(new_run)
    assert store.list_runs() == [new_run, old_run]


def test_上書きしても並びは変わらない(tmp_path: Path) -> None:
    store = Store(tmp_path / "data")
    first, second = _testcase(1), _testcase(2)
    store.save_testcase(first)
    store.save_testcase(second)

    approved = first.model_copy(update={"updated_at": second.created_at})
    store.save_testcase(approved)

    assert store.list_testcases() == [second, approved]


def test_もう一度立ち上げても当て直さない(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    Store(data_dir).save_testcase(_testcase(1))

    store = Store(data_dir)

    assert _revision(data_dir) == _head()
    assert store.list_testcases() == [_testcase(1)]


def test_表の定義とマイグレーションがずれていない(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    Store(data_dir)
    with create_engine(database_url(data_dir)).connect() as connection:
        diff = compare_metadata(MigrationContext.configure(connection), METADATA)
    assert diff == []


def test_CLIから当てると設定の保存先が最新になる(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # README の「表の形を変える」で使う道（uv run alembic ...）
    data_dir = tmp_path / "data"
    monkeypatch.setenv("QATA_DATA_DIR", str(data_dir))

    command.upgrade(Config(str(_REPO / "alembic.ini")), "head")

    assert _revision(data_dir) == _head()
