"""feature の手順から使う、偽の runner と契約の例。"""

import base64
import copy
import dataclasses
import json
from typing import Any

from generate_contracts import CONTRACTS_DIR

from qata_server.application import App, RunnerBusy, RunnerUnavailable

EXAMPLES_DIR = CONTRACTS_DIR / "examples"
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def load_example(file_name: str) -> Any:
    return json.loads((EXAMPLES_DIR / file_name).read_text(encoding="utf-8"))


def png_for(index: int) -> bytes:
    return PNG_SIGNATURE + f"step {index}".encode()


def remove_part_from(apps: dict[str, App], app_id: str, part: str) -> None:
    """登録のあとで、部品の辞書から部品が消えた場面を作る。"""
    app = apps[app_id]
    conversions = {k: v for k, v in app.conversions.items() if k[0] != part}
    assert len(conversions) < len(app.conversions), f"部品 {part!r} がない"
    apps[app_id] = dataclasses.replace(app, conversions=conversions)


def _set_step(result: dict[str, Any], index: int, **changes: Any) -> None:
    result["steps"][index].update(changes)


def _error_at(result: dict[str, Any], index: int) -> None:
    """そのステップを error にする（スクショと読んだ文字は消す）。"""
    step = result["steps"][index]
    step.pop("screenshot", None)
    step.pop("text", None)
    step.update(
        status="error", error={"code": "step_failed", "message": "ボタンが見つからない"}
    )


# 壊れた結果の作り方。名前は feature の表に書く。どれも、runner の決まりに合う
# 結果（前準備 2 つ・テストケース 5 つ、すべて ok の completed）を壊す。
BREAKAGES: dict[str, Any] = {
    "決めた形と違う": lambda r: r.update(status="done"),
    "スクショが Base64 でない": lambda r: _set_step(
        r, 0, screenshot={"media_type": "image/png", "data_base64": "!!!"}
    ),
    "スクショに ASCII でない文字がある": lambda r: _set_step(
        r, 0, screenshot={"media_type": "image/png", "data_base64": "スクショ"}
    ),
    "実行の番号が命令と違う": lambda r: r.update(run_id="run_other"),
    "ステップの番号が飛ぶ": lambda r: r["steps"].pop(3),
    "ステップが命令より多い": lambda r: r["steps"].append(
        {**r["steps"][-1], "index": len(r["steps"])}
    ),
    "completed なのにステップが足りない": lambda r: r["steps"].pop(),
    "completed なのに最後のステップが error": lambda r: _error_at(r, -1),
    "前準備が error なのに completed": lambda r: _error_at(r, 1),
    "error のあとにもステップがある": lambda r: (
        _error_at(r, 3),
        r.update(status="aborted", error=r["steps"][3]["error"]),
    ),
}


class FakeRunner:
    """決まった結果を返す runner。受けた命令を覚えておく。"""

    def __init__(self) -> None:
        self.text = "表示は 3 です"
        self.mode = "ok"
        self.abort_at: int | None = None
        # 返す前に結果を壊すときの名前（BREAKAGES）
        self.breakage: str | None = None
        self.commands: list[dict[str, Any]] = []

    def run(self, command: dict[str, Any]) -> Any:
        if self.mode == "unreachable":
            raise RunnerUnavailable("runner に届かない（偽物）")
        if self.mode == "busy":
            raise RunnerBusy("runner はほかの実行の最中（偽物）")
        if self.mode == "crash":
            # server の中の想定していない誤りの代わり
            raise RuntimeError("想定していない誤り（偽物）")
        self.commands.append(copy.deepcopy(command))
        base = {
            "run_id": command["run_id"],
            "started_at": "2026-11-08T10:06:00+09:00",
            "finished_at": "2026-11-08T10:06:03+09:00",
        }
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
        result = {**base, "status": "completed", "steps": steps}
        if self.breakage is not None:
            BREAKAGES[self.breakage](result)
        return result
