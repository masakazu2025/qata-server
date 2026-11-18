"""親のタグ contracts-v<版> の contracts/ を、qata-contracts/ に丸ごと写す。

使い方：
  uv run python scripts/sync_contracts.py 1.0.0     # その版を写す（版を上げるとき）
  uv run python scripts/sync_contracts.py --check   # 写しを手で直していないか確かめる
  uv run python scripts/sync_contracts.py --warn-if-old  # 親に新しい版があれば警告

読む版は qata-contracts/VERSION。写しは手で直さない（親の repos-and-contracts.md の
「子の持ち方」、D54）。版を上げたら scripts/generate_contracts.py で型を作り直す。
"""

import argparse
import io
import shutil
import subprocess
import sys
import tarfile
import urllib.request
from pathlib import Path, PurePosixPath

REPO_ROOT = Path(__file__).resolve().parent.parent
COPY_DIR = REPO_ROOT / "qata-contracts"
PARENT_REPO = "https://github.com/masakazu2025/qata"
TAG_PREFIX = "contracts-v"


def read_version(copy_dir: Path = COPY_DIR) -> str:
    return (copy_dir / "VERSION").read_text(encoding="utf-8").strip()


def download(version: str) -> bytes:
    """親のタグの tarball を取る。"""
    url = f"{PARENT_REPO}/archive/refs/tags/{TAG_PREFIX}{version}.tar.gz"
    with urllib.request.urlopen(url, timeout=60) as response:
        return response.read()


def contracts_in(tarball: bytes) -> dict[str, bytes]:
    """tarball の中の contracts/ のファイル（contracts/ からの相対の道 → 中身）。

    GitHub の tarball は、一段目に「リポジトリ名-タグ」のフォルダがある。
    """
    found: dict[str, bytes] = {}
    with tarfile.open(fileobj=io.BytesIO(tarball), mode="r:gz") as tar:
        for member in tar.getmembers():
            parts = PurePosixPath(member.name).parts
            if not member.isfile() or len(parts) < 3 or parts[1] != "contracts":
                continue
            data = tar.extractfile(member)
            assert data is not None
            found["/".join(parts[2:])] = data.read()
    if not found:
        raise ValueError("tarball に contracts/ がない")
    return found


def files_in(root: Path) -> dict[str, bytes]:
    return {
        p.relative_to(root).as_posix(): p.read_bytes()
        for p in sorted(root.rglob("*"))
        if p.is_file()
    }


def write(tarball: bytes, copy_dir: Path = COPY_DIR) -> None:
    """写しを tarball の contracts/ の中身に置き換える。

    tarball を読めてから写しを消す。読めないときに写しが消えたままにならないように。
    """
    files = contracts_in(tarball)
    if copy_dir.exists():
        shutil.rmtree(copy_dir)
    for name, data in files.items():
        path = copy_dir / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)


def differences(tarball: bytes, copy_dir: Path = COPY_DIR) -> list[str]:
    """tarball の contracts/ と写しで、中身が違うか片方にしかないファイルの一覧。"""
    expected = contracts_in(tarball)
    actual = files_in(copy_dir)
    return sorted(
        name
        for name in expected.keys() | actual.keys()
        if expected.get(name) != actual.get(name)
    )


def parse_version(text: str) -> tuple[int, int, int] | None:
    parts = text.split(".")
    if len(parts) != 3 or not all(p.isdigit() for p in parts):
        return None
    major, minor, patch = (int(p) for p in parts)
    return major, minor, patch


def newer_version(current: str, ls_remote: str) -> str | None:
    """git ls-remote --tags の出力から、読む版より新しい一番大きい版。なければ None。

    版は数として比べる（1.10.0 は 1.9.0 より大きい）。
    """
    current_key = parse_version(current)
    if current_key is None:
        raise ValueError(f"読む版の形が違う：{current!r}")
    versions = []
    for line in ls_remote.splitlines():
        ref = line.split("\t")[-1].removesuffix("^{}")
        tag = ref.removeprefix("refs/tags/")
        if not tag.startswith(TAG_PREFIX):
            continue
        key = parse_version(tag.removeprefix(TAG_PREFIX))
        if key is not None:
            versions.append(key)
    latest = max(versions, default=None)
    if latest is None or latest <= current_key:
        return None
    return ".".join(str(n) for n in latest)


def list_tags() -> str:
    """親の contracts-v* のタグを git ls-remote --tags の形で取る。"""
    return subprocess.run(
        ["git", "ls-remote", "--tags", PARENT_REPO, f"{TAG_PREFIX}*"],
        check=True,
        capture_output=True,
        text=True,
        timeout=60,
    ).stdout


def old_version_notice(current: str, ls_remote: str) -> str:
    """読む版と親のタグから、CI に出す一行。古ければ GitHub Actions の警告の形。"""
    newer = newer_version(current, ls_remote)
    if newer:
        return (
            f"::warning::読む契約の版 {current} は、親の最新 {newer} より古い。"
            f"scripts/sync_contracts.py {newer} で上げる"
        )
    return f"読む契約の版 {current} は、親の最新"


def warn_if_old(current: str | None = None) -> None:
    """親に新しい版があれば GitHub Actions の警告を出す。関門は落とさない。

    タグが取れないとき（つながらないなど）も、警告だけにする。
    """
    current = current or read_version()
    try:
        ls_remote = list_tags()
    except (OSError, subprocess.SubprocessError) as e:
        print(f"::warning::親の契約の版のタグが取れなかった：{e}")
        return
    print(old_version_notice(current, ls_remote))


def main() -> int:
    if isinstance(sys.stdout, io.TextIOWrapper):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="親のタグから契約を写す")
    parser.add_argument("version", nargs="?", help="写す版（例：1.0.0）")
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--check",
        action="store_true",
        help="写し直して、qata-contracts/ と同じかを確かめる（版は省くと VERSION）",
    )
    group.add_argument(
        "--warn-if-old", action="store_true", help="親に新しい版があれば警告する"
    )
    args = parser.parse_args()

    if args.warn_if_old:
        warn_if_old()
        return 0
    if args.check:
        version = args.version or read_version()
        # その版のタグの中身を取り直し、写しと比べる
        found = differences(download(version))
        if found:
            print(f"qata-contracts/ が、親のタグ {TAG_PREFIX}{version} と違う：")
            for name in found:
                print(f"  {name}")
            print(f"手で直さず、scripts/sync_contracts.py {version} で写し直す")
            return 1
        print(f"qata-contracts/ は、親のタグ {TAG_PREFIX}{version} と同じ")
        return 0
    if not args.version:
        parser.error("写す版を指定する（例：1.0.0）")
    if parse_version(args.version) is None:
        parser.error(f"版は三つの数（例：1.0.0）：{args.version!r}")
    write(download(args.version))
    print(f"写した：{TAG_PREFIX}{args.version} → {COPY_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
