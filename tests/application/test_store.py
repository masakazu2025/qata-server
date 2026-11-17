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
from sqlalchemy import create_engine, select
from support import load_example

from qata_server.application import Store
from qata_server.application.store import (
    METADATA,
    MIGRATIONS,
    database_url,
    testcase_tags,
)

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


def _untagged(n: int) -> Record:
    """タグを足す前の形の記録（tags がない）。"""
    data = _testcase(n).model_dump(mode="json", exclude_none=True)
    del data["testcase"]["tags"]
    return Record.model_validate(data)


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


def test_タグを足す前の記録もそのまま読めてタグで絞ると出ない(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    untagged = _untagged(1)
    _write_old_store(data_dir, [untagged], [])

    store = Store(data_dir)

    read = store.get_testcase(untagged.id.root)
    assert read == untagged
    assert read is not None and read.testcase.tags is None
    assert store.list_testcases() == [untagged]
    assert store.list_testcases(tags=[]) == [untagged]
    assert store.list_testcases(tags=["機能:加算"]) == []


def test_タグの表を作るときにもうある記録のタグを写す(tmp_path: Path) -> None:
    # 記録の JSON がタグを持っていれば、タグの表がなくても、当てたあとに絞れる
    data_dir = tmp_path / "data"
    tagged, untagged = _testcase(1), _untagged(2)
    _write_old_store(data_dir, [tagged, untagged], [])

    store = Store(data_dir)

    assert store.list_testcases(tags=["機能:加算"]) == [tagged]
    assert store.list_testcases(tags=["機能:加算", "設計書:電卓の基本操作"]) == [tagged]


def test_上書きするとタグも記録に合わせる(tmp_path: Path) -> None:
    store = Store(tmp_path / "data")
    tagged = _testcase(1)
    store.save_testcase(tagged)

    data = tagged.model_dump(mode="json", exclude_none=True)
    data["testcase"]["tags"] = ["機能:減算"]
    store.save_testcase(Record.model_validate(data))

    assert store.list_testcases(tags=["機能:加算"]) == []
    assert len(store.list_testcases(tags=["機能:減算"])) == 1


def test_消すとタグの組も消える(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    store = Store(data_dir)
    tagged = _testcase(1)
    store.save_testcase(tagged)

    assert store.delete_testcase(tagged.id.root)

    with create_engine(database_url(data_dir)).connect() as connection:
        left = connection.scalars(
            select(testcase_tags.c.tag).where(
                testcase_tags.c.testcase_id == tagged.id.root
            )
        ).all()
    assert left == []


def test_タグをとても多く並べても絞り込める(tmp_path: Path) -> None:
    # 並びの数に上限はない（親の D50）。1000 個でも誤りにならない
    store = Store(tmp_path / "data")
    store.save_testcase(_testcase(1))
    many = ["機能:加算", *(f"タグ{i}" for i in range(999))]

    assert store.list_testcases(tags=many) == []
    assert len(store.list_testcases(tags=many[:1])) == 1


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
