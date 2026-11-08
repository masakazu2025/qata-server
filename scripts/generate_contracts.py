"""親の契約（JSON Schema）から pydantic の型を生成する。

使い方：uv run python scripts/generate_contracts.py

生成物は src/qata_server/contracts/ に置き、コミットする。手で直さない。
"""

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CONTRACTS_DIR = REPO_ROOT.parent / "qata" / "contracts"
SCHEMAS_DIR = CONTRACTS_DIR / "schemas"
GENERATED_DIR = REPO_ROOT / "src" / "qata_server" / "contracts"

OPTIONS = [
    "--input-file-type", "jsonschema",
    "--output-model-type", "pydantic_v2.BaseModel",
    "--target-python-version", "3.12",
    "--disable-timestamp",
    "--use-standard-collections",
    "--use-union-operator",
    "--use-annotated",
    "--field-constraints",
    "--use-title-as-name",
    "--use-double-quotes",
    "--formatters", "ruff-format", "ruff-check",
]  # fmt: skip


def generate(out_dir: Path) -> None:
    """契約から型を生成し、out_dir に置く（中身を入れ替える）。

    生成は、いつも同じ条件（このリポジトリの外の一時フォルダ）で行う。
    生成先の ruff の設定で、整形の結果が変わらないようにするため。
    """
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp) / "contracts"
        env = {**os.environ, "RUFF_NO_CACHE": "true"}
        subprocess.run(
            [
                sys.executable, "-m", "datamodel_code_generator",
                "--input", str(SCHEMAS_DIR),
                "--output", str(work),
                *OPTIONS,
            ],
            check=True,
            env=env,
            cwd=tmp,
        )  # fmt: skip
        if out_dir.exists():
            shutil.rmtree(out_dir)
        shutil.copytree(work, out_dir)
    # Windows でも改行を LF にそろえる（.gitattributes に合わせる）
    for path in out_dir.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        path.write_text(text, encoding="utf-8", newline="\n")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    generate(GENERATED_DIR)
    print(f"生成した：{GENERATED_DIR}")
