"""依存の向きの feature の手順。"""

import os
import subprocess
import sys
from pathlib import Path

from pytest_bdd import scenarios, then

scenarios("architecture.feature")

ROOT = Path(__file__).resolve().parent.parent


@then("import-linter の決まりがすべて守られている")
def import_contracts_kept() -> None:
    lint_imports = Path(sys.executable).parent / "lint-imports"
    result = subprocess.run(
        [str(lint_imports), "--no-cache"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env={"PYTHONIOENCODING": "utf-8", **os.environ},
    )
    assert result.returncode == 0, result.stdout + result.stderr
