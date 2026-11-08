"""feature の手順から使う、偽の runner と契約の例。"""

import base64
import copy
import json
from typing import Any

from generate_contracts import CONTRACTS_DIR

from qata_server.application import RunnerUnavailable

EXAMPLES_DIR = CONTRACTS_DIR / "examples"
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def load_example(file_name: str) -> Any:
    return json.loads((EXAMPLES_DIR / file_name).read_text(encoding="utf-8"))


def png_for(index: int) -> bytes:
    return PNG_SIGNATURE + f"step {index}".encode()


class FakeRunner:
    """決まった結果を返す runner。受けた命令を覚えておく。"""

    def __init__(self) -> None:
        self.text = "表示は 3 です"
        self.mode = "ok"
        self.abort_at: int | None = None
        self.commands: list[dict[str, Any]] = []

    def run(self, command: dict[str, Any]) -> Any:
        if self.mode == "unreachable":
            raise RunnerUnavailable("runner に届かない（偽物）")
        self.commands.append(copy.deepcopy(command))
        base = {
            "run_id": command["run_id"],
            "started_at": "2026-11-08T10:06:00+09:00",
            "finished_at": "2026-11-08T10:06:03+09:00",
        }
        if self.mode == "broken":
            return {**base, "status": "done", "steps": []}
        if self.mode == "launch_failed":
            error = {"code": "launch_failed", "message": "アプリを起動できない"}
            return {**base, "status": "aborted", "error": error, "steps": []}
        steps = []
        for i, step in enumerate(command["steps"]):
            if i == self.abort_at:
                error = {"code": "step_failed", "message": "ボタンが見つからない"}
                steps.append({"index": i, "status": "error", "error": error})
                return {**base, "status": "aborted", "error": error, "steps": steps}
            result = {
                "index": i,
                "status": "ok",
                "screenshot": {
                    "media_type": "image/png",
                    "data_base64": base64.b64encode(png_for(i)).decode(),
                },
            }
            if step["type"] == "read_text":
                result["text"] = self.text
            steps.append(result)
        return {**base, "status": "completed", "steps": steps}
