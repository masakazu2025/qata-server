"""アプリの設定（部品の辞書と変換の規則）を読み込む。

設定は server の中の形で、アプリごとに一つの JSON ファイルにする（S3）。
AI と web に見せる部品の辞書（親の part-dictionary.schema.json）は、ここから作る。
"""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from qata_server.application import contract_check
from qata_server.application.conversion import Conversion, RuleError, convert
from qata_server.contracts.part_dictionary_schema import PartDictionary

APPS_DIR = Path(__file__).resolve().parent.parent / "apps"


class AppConfigError(ValueError):
    """アプリの設定の書き方が違う。"""


@dataclass(frozen=True)
class App:
    app_id: str
    name: str
    dictionary: PartDictionary
    runner_app: dict[str, Any]
    """runner への命令の app（起動のしかたとウィンドウ）。"""
    screenshot: dict[str, Any]
    """runner への命令の screenshot（撮る範囲）。"""
    prepare: list[dict[str, Any]]
    """前準備。テストケースのステップの前に runner に送る基本の操作（S8）。"""
    conversions: dict[tuple[str, str], Conversion]
    """(部品の名前, アクション) → 変換。"""

    def actions(self, part: str) -> list[str]:
        """部品に使えるアクション。辞書にない部品なら空。"""
        return [action for name, action in self.conversions if name == part]


def load_apps(directory: Path = APPS_DIR) -> dict[str, App]:
    apps: dict[str, App] = {}
    for path in sorted(directory.glob("*.json")):
        try:
            app = _load(json.loads(path.read_text(encoding="utf-8")))
        except (AppConfigError, KeyError, TypeError, AttributeError) as e:
            raise AppConfigError(f"{path.name}：{e}") from e
        if app.app_id in apps:
            raise AppConfigError(f"{path.name}：app_id {app.app_id!r} が重なっている")
        apps[app.app_id] = app
    return apps


def _load(config: dict[str, Any]) -> App:
    unknown = set(config) - {
        "app_id",
        "name",
        "launch",
        "window",
        "screenshot",
        "prepare",
        "parts",
    }
    if unknown:
        raise AppConfigError(f"知らない項目：{sorted(unknown)}")

    runner_app = {"launch": config["launch"], "window": config["window"]}
    screenshot = config["screenshot"]
    _check("runner-command.schema.json#/properties/app", runner_app, "launch・window")
    _check(
        "runner-command.schema.json#/$defs/screenshot_settings",
        screenshot,
        "screenshot",
    )

    prepare = config.get("prepare", [])
    if not isinstance(prepare, list):
        raise AppConfigError("prepare は配列にする")
    for i, step in enumerate(prepare):
        _check("runner-command.schema.json#/$defs/step", step, f"前準備の {i} 番目")

    parts: dict[str, Any] = {}
    conversions: dict[tuple[str, str], Conversion] = {}
    for name, part in config["parts"].items():
        rules = part["rules"]
        for action, rule in rules.items():
            try:
                conversion = convert(action, rule)
            except RuleError as e:
                raise AppConfigError(f"部品 {name!r} の {action}：{e}") from e
            _check(
                "runner-command.schema.json#/$defs/step",
                conversion.runner_step,
                f"部品 {name!r} の {action} の変換の結果",
            )
            conversions[(name, action)] = conversion
        entry: dict[str, Any] = {"actions": list(rules)}
        if "description" in part:
            entry["description"] = part["description"]
        parts[name] = entry

    dictionary = {"app_id": config["app_id"], "name": config["name"], "parts": parts}
    _check("part-dictionary.schema.json", dictionary, "部品の辞書")
    return App(
        app_id=config["app_id"],
        name=config["name"],
        dictionary=PartDictionary.model_validate(dictionary),
        runner_app=runner_app,
        screenshot=screenshot,
        prepare=prepare,
        conversions=conversions,
    )


def _check(contract: str, data: Any, what: str) -> None:
    found = contract_check.problems(contract, data)
    if found:
        details = "、".join(f"{p or '/'}：{m}" for p, m in found)
        raise AppConfigError(f"{what}が契約に合わない（{details}）")
