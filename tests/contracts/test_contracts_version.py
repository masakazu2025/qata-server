"""contracts_version.feature の手順。"""

import io
import json
import shutil
import subprocess
import tarfile
from pathlib import Path

import pytest
import sync_contracts
from pytest_bdd import given, parsers, scenarios, then, when
from sync_contracts import (
    COPY_DIR,
    contracts_in,
    differences,
    newer_version,
    old_version_notice,
    write,
)

from qata_server import main
from qata_server.application import contract_check
from qata_server.settings import Settings

scenarios("contracts_version.feature")


@given(parsers.parse('読む版 "{version}"'), target_fixture="current")
def given_current(version: str) -> str:
    return version


@given(parsers.re('親のタグ "(?P<tags>.*)"'), target_fixture="ls_remote")
def given_tags(tags: str) -> str:
    # git ls-remote --tags の出力の形（ハッシュ、タブ、refs/tags/<タグ>）
    return "".join(
        f"0123abcd\trefs/tags/{tag}\n" for tag in tags.split(",") if tag.strip()
    )


@then(parsers.parse('知らせる新しい版は "{expected}"'))
def then_newer(current: str, ls_remote: str, expected: str) -> None:
    assert newer_version(current, ls_remote) == (
        None if expected == "なし" else expected
    )


@then(parsers.re("CI に出す一行は(?P<shape>警告|警告ではない)$"))
def then_notice(current: str, ls_remote: str, shape: str) -> None:
    line = old_version_notice(current, ls_remote)
    assert line.startswith("::warning::") == (shape == "警告"), line


ERRORS = {
    "OSError": OSError("git がない"),
    "CalledProcessError": subprocess.CalledProcessError(128, ["git"]),
    "TimeoutExpired": subprocess.TimeoutExpired(["git"], 60),
}


@given(parsers.parse('タグを取ると "{error}" になる'))
def given_list_tags_fails(monkeypatch: pytest.MonkeyPatch, error: str) -> None:
    def fail() -> str:
        raise ERRORS[error]

    monkeypatch.setattr(sync_contracts, "list_tags", fail)


@when("古い版の警告を出す")
def when_warn(capsys: pytest.CaptureFixture[str]) -> None:
    # capsys は、出す前に受け取っておく（受け取ったときから捕まえるため）
    # 例外が漏れれば、ここでテストが落ちる
    sync_contracts.warn_if_old("1.0.0")


@then("出した一行は警告")
def then_warned(capsys: pytest.CaptureFixture[str]) -> None:
    assert capsys.readouterr().out.startswith("::warning::")


@given("写しと同じ中身の、親のタグの tarball", target_fixture="tarball")
def given_tarball() -> bytes:
    # GitHub のタグの tarball と同じく、一段目のフォルダの下に contracts/ がある
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as tar:
        tar.add(COPY_DIR, arcname="qata-contracts-v0.0.0/contracts")
    return buffer.getvalue()


@pytest.fixture
def copy_dir(tmp_path: Path) -> Path:
    """写しを手で直す手順のために、一時の場所に複製した写し。"""
    copy = tmp_path / "qata-contracts"
    shutil.copytree(COPY_DIR, copy)
    return copy


@when(parsers.parse('写しの "{name}" を書き換える'))
def when_edit(copy_dir: Path, name: str) -> None:
    path = copy_dir / name
    path.write_bytes(path.read_bytes() + b"x")


@then("写しとの違いはない")
def then_no_difference(tarball: bytes, copy_dir: Path) -> None:
    assert differences(tarball, copy_dir) == []


@then(parsers.parse('写しとの違いに "{name}" がある'))
def then_difference(tarball: bytes, copy_dir: Path, name: str) -> None:
    assert name in differences(tarball, copy_dir)


@when(parsers.parse('写しの "{name}" を足す'))
def when_add(copy_dir: Path, name: str) -> None:
    (copy_dir / name).write_text("{}", encoding="utf-8")


@when(parsers.parse('写しの "{name}" を消す'))
def when_remove(copy_dir: Path, name: str) -> None:
    (copy_dir / name).unlink()


def _tarball(names: list[str]) -> bytes:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as tar:
        for name in names:
            data = b"x"
            info = tarfile.TarInfo(f"qata-contracts-v0.0.0/{name}")
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
    return buffer.getvalue()


@given(
    parsers.re("一段目のフォルダに (?P<names>.+) がある tarball"),
    target_fixture="tarball",
)
def given_tarball_with(names: str) -> bytes:
    return _tarball([n.strip().strip('"') for n in names.split("と")])


@then(parsers.parse('写すファイルは "{name}" だけ'))
def then_only(tarball: bytes, name: str) -> None:
    assert list(contracts_in(tarball)) == [name]


@then("写すと、写しを残したまま失敗する")
def then_write_fails(tarball: bytes, copy_dir: Path) -> None:
    before = sorted(p.name for p in copy_dir.rglob("*"))
    with pytest.raises(ValueError):
        write(tarball, copy_dir)
    assert sorted(p.name for p in copy_dir.rglob("*")) == before


@pytest.fixture
def contracts_dir(copy_dir: Path, monkeypatch: pytest.MonkeyPatch):
    """契約の判定が、一時の場所に複製した写しを読むようにする。"""
    monkeypatch.setattr(contract_check, "SCHEMAS_DIR", copy_dir / "schemas")
    monkeypatch.setattr(
        contract_check,
        "USED_CONTRACTS",
        [copy_dir / p.relative_to(COPY_DIR) for p in contract_check.USED_CONTRACTS],
    )
    contract_check.clear_cache()
    yield copy_dir
    contract_check.clear_cache()


@given(parsers.parse('写しから "{name}" を除く'))
def given_removed(contracts_dir: Path, name: str) -> None:
    (contracts_dir / name).unlink()


@given(parsers.parse('写しの "{name}" から定義 "{definition}" を除く'))
def given_definition_removed(contracts_dir: Path, name: str, definition: str) -> None:
    path = contracts_dir / name
    schema = json.loads(path.read_text(encoding="utf-8"))
    del schema["$defs"][definition]
    path.write_text(json.dumps(schema), encoding="utf-8")


def _build(tmp_path: Path) -> None:
    main.build(Settings(data_dir=tmp_path / "data"))


@then("server の組み立てが失敗する")
def then_build_fails(contracts_dir: Path, tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        _build(tmp_path)


@then("server を組み立てられる")
def then_builds(tmp_path: Path) -> None:
    # 複製ではなく、リポジトリの写しそのもので組み立てる
    _build(tmp_path)
