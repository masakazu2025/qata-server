"""変換の枠：部品の名前で書いたステップを、runner への命令の基本の操作に変える。

親の D14・D17。

規則は、アプリの設定の部品ごと・アクションごとに `{"kind": ..., ...}` の形で書く。
kind ごとの変換を CONVERTERS に足せば、規則の種類を増やせる（runner は変わらない）。
"""

import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Conversion:
    """一つのステップの変換の結果。"""

    runner_step: dict[str, Any]
    """runner への命令の steps の一つ（key・tap・read_text）。"""

    extract: Callable[[str], str | None] | None = None
    """expect_text のとき、runner が読んだ文字から値を取り出す。

    取り出せなければ None。
    """


@dataclass(frozen=True)
class Converter:
    action: str
    """この規則を使えるテストケースのアクション。"""

    convert: Callable[[dict[str, Any]], Conversion]


class RuleError(ValueError):
    """変換の規則の書き方が違う。"""


def _key(rule: dict[str, Any]) -> Conversion:
    """キーを押す。{"kind": "key", "key": "1"}"""
    return Conversion({"type": "key", "key": rule["key"]})


def _tap(rule: dict[str, Any]) -> Conversion:
    """座標をタップする。{"kind": "tap", "point": {"x": 0, "y": 0}}"""
    return Conversion({"type": "tap", "point": rule["point"]})


def _uia(rule: dict[str, Any]) -> Conversion:
    """UI Automation で要素の Name を読む。

    {"kind": "uia", "automation_id": "...", "extract": "^表示は (.+) です$"}
    extract は正規表現。一つ目のグループ（なければ合った全体）を値にする。
    省略したら、読んだ文字のまま。
    """
    pattern = re.compile(rule.get("extract", "^(.*)$"), re.DOTALL)

    def extract(text: str) -> str | None:
        match = pattern.search(text)
        if match is None:
            return None
        return match.group(1) if pattern.groups else match.group(0)

    return Conversion(
        {
            "type": "read_text",
            "source": {"method": "uia", "automation_id": rule["automation_id"]},
        },
        extract,
    )


CONVERTERS: dict[str, Converter] = {
    "key": Converter("press_key", _key),
    "tap": Converter("tap", _tap),
    "uia": Converter("expect_text", _uia),
}


def convert(action: str, rule: dict[str, Any]) -> Conversion:
    """規則を変換にする。規則が違えば RuleError。"""
    kind = rule.get("kind")
    converter = CONVERTERS.get(kind)
    if converter is None:
        raise RuleError(
            f"知らない規則の種類：{kind!r}（使えるのは {sorted(CONVERTERS)}）"
        )
    if converter.action != action:
        raise RuleError(
            f"規則の種類 {kind!r} は {converter.action} のためのもので、"
            f"{action} には使えない"
        )
    try:
        return converter.convert(rule)
    except (KeyError, re.error) as e:
        raise RuleError(f"規則 {kind!r} の書き方が違う：{e}") from e
