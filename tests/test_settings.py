"""設定の feature の手順。"""

import os
import re
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError
from pytest_bdd import given, parsers, scenarios, then, when

from qata_server import main
from qata_server.settings import Settings

scenarios("settings.feature")

ROOT = Path(__file__).resolve().parent.parent
# 環境変数から値を読む書き方。子のプロセスに環境を渡す {**os.environ} は入れない
ENVIRON = re.compile(r"\benviron\s*(\.get\b|\[)|\bgetenv\b")


@pytest.fixture
def ctx() -> dict[str, Any]:
    return {}


@given("qata の環境変数を置いていない")
def no_qata_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in list(os.environ):
        if name.upper().startswith("QATA_"):
            monkeypatch.delenv(name)


@given(parsers.re(r'環境変数 "(?P<name>[^"]+)" を "(?P<value>[^"]*)" にする'))
def set_env(monkeypatch: pytest.MonkeyPatch, name: str, value: str) -> None:
    monkeypatch.setenv(name, value)


@then(parsers.parse('設定の "{field}" は "{expected}"'))
def setting_is(field: str, expected: str) -> None:
    value = getattr(Settings(), field)
    if isinstance(value, Path):
        assert value == Path(expected)
    else:
        assert str(value) == expected


@then("親のリポジトリは、隣に並べた qata を指す")
def parent_is_sibling() -> None:
    assert Settings().parent_dir == ROOT.parent / "qata"


@then(parsers.parse('設定を読むと、"{field}" の誤りになる'))
def setting_rejected(field: str) -> None:
    with pytest.raises(ValidationError) as info:
        Settings()
    assert [error["loc"] for error in info.value.errors()] == [(field,)]


@given(
    parsers.parse('保存先を一時フォルダに、runner の場所を "{url}" にした設定'),
    target_fixture="settings",
)
def settings_for(tmp_path: Path, url: str) -> Settings:
    return Settings(data_dir=tmp_path / "data", runner_url=url)


@when("その設定で server を組み立てる")
def build_with(
    settings: Settings, monkeypatch: pytest.MonkeyPatch, ctx: dict[str, Any]
) -> None:
    urls: list[str] = []

    class RecordingRunner:
        def __init__(self, base_url: str) -> None:
            urls.append(base_url)

    monkeypatch.setattr(main, "HttpRunner", RecordingRunner)
    main.build(settings)
    ctx["runner_urls"] = urls


@then("保存先の一時フォルダに、保存のファイルができる")
def store_in_data_dir(settings: Settings) -> None:
    assert (settings.data_dir / "qata.sqlite3").is_file()


@then(parsers.parse('runner への道具は "{url}" を指す'))
def runner_points_to(ctx: dict[str, Any], url: str) -> None:
    assert ctx["runner_urls"] == [url]


@then("src と scripts に、Settings を通さずに環境変数の値を読むところがない")
def no_environ_reads() -> None:
    files = sorted((ROOT / "src").rglob("*.py")) + sorted(
        (ROOT / "scripts").rglob("*.py")
    )
    readers = [
        path.relative_to(ROOT).as_posix()
        for path in files
        if ENVIRON.search(path.read_text(encoding="utf-8"))
    ]
    assert readers == []
