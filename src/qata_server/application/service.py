"""server の機能。REST（web 用）と MCP（AI 用）の入口は、これを薄く包む。"""

import base64
import binascii
from collections.abc import Callable
from datetime import datetime
from typing import Any, Protocol

from qata_server.application import contract_check
from qata_server.application.apps import App
from qata_server.application.store import Store, new_id
from qata_server.contracts.part_dictionary_schema import PartDictionary
from qata_server.contracts.server_schema import (
    AppSummary,
    RegisterResult,
    Run,
    TestcaseRecord,
    ValidationResult,
)
from qata_server.contracts.testcase_schema import Testcase


class Runner(Protocol):
    def run(self, command: dict[str, Any]) -> Any:
        """runner-command を送り、返ってきた本文（JSON）をそのまま返す。

        届かなければ RunnerUnavailable。返ってきたものの判定は server が行う。
        """
        ...


class ServiceError(Exception):
    """入口がエラーの応答（error_response）に変えるもの。"""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class NotFound(ServiceError):
    pass


class Conflict(ServiceError):
    """いまの状態ではできない。"""


class RunnerUnavailable(ServiceError):
    def __init__(self, message: str) -> None:
        super().__init__("runner_unavailable", message)


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="milliseconds")


class Service:
    def __init__(
        self,
        apps: dict[str, App],
        store: Store,
        runner: Runner,
        now: Callable[[], str] = _now,
    ) -> None:
        self._apps = apps
        self._store = store
        self._runner = runner
        self._now = now

    # 部品の辞書

    def list_apps(self) -> list[AppSummary]:
        return [
            AppSummary.model_validate({"app_id": a.app_id, "name": a.name})
            for a in self._apps.values()
        ]

    def get_part_dictionary(self, app_id: str) -> PartDictionary:
        app = self._apps.get(app_id)
        if app is None:
            raise NotFound("not_found", f"アプリ {app_id!r} の部品の辞書はない")
        return app.dictionary

    # テストケース

    def validate_testcase(self, data: Any) -> ValidationResult:
        errors = self._validate(data)
        return ValidationResult.model_validate({"valid": not errors, "errors": errors})

    def register_testcase(self, data: Any) -> RegisterResult:
        errors = self._validate(data)
        if errors:
            return RegisterResult.model_validate(
                {"registered": False, "errors": errors}
            )
        now = self._now()
        record = TestcaseRecord.model_validate(
            {
                "id": new_id("tc"),
                "testcase": data,
                "review_status": "pending" if data["needs_review"] else "not_required",
                "created_at": now,
                "updated_at": now,
            }
        )
        self._store.save_testcase(record)
        return RegisterResult.model_validate(
            {"registered": True, "testcase_record": record, "errors": []}
        )

    def list_testcases(self, app_id: str | None = None) -> list[TestcaseRecord]:
        return self._store.list_testcases(app_id)

    def get_testcase(self, testcase_id: str) -> TestcaseRecord:
        record = self._store.get_testcase(testcase_id)
        if record is None:
            raise NotFound("not_found", f"テストケース {testcase_id!r} はない")
        return record

    def delete_testcase(self, testcase_id: str) -> None:
        if not self._store.delete_testcase(testcase_id):
            raise NotFound("not_found", f"テストケース {testcase_id!r} はない")

    def approve_testcase(self, testcase_id: str) -> TestcaseRecord:
        record = self.get_testcase(testcase_id)
        if record.review_status.value == "not_required":
            raise Conflict(
                "review_not_required", "このテストケースは人の確認が要らない"
            )
        data = record.model_dump(mode="json", exclude_none=True)
        approved = TestcaseRecord.model_validate(
            {**data, "review_status": "approved", "updated_at": self._now()}
        )
        self._store.save_testcase(approved)
        return approved

    def _validate(self, data: Any) -> list[dict[str, str]]:
        """二段で検証する：形式（JSON Schema）と、部品の辞書との照合。"""
        schema_errors = [
            {
                "code": "schema",
                "path": path,
                "message": f"形式が契約に合わない：{message}",
            }
            for path, message in contract_check.problems("testcase.schema.json", data)
        ]
        if schema_errors:
            return schema_errors
        return self._check_parts(Testcase.model_validate(data))

    def _check_parts(self, testcase: Testcase) -> list[dict[str, str]]:
        app = self._apps.get(testcase.app_id.root)
        if app is None:
            return [
                {
                    "code": "unknown_app",
                    "path": "/app_id",
                    "message": f"アプリ {testcase.app_id.root!r} の部品の辞書はない",
                }
            ]
        errors = []
        for i, wrapped in enumerate(testcase.steps):
            step = wrapped.root
            part = step.part.root
            actions = app.actions(part)
            if not actions:
                errors.append(
                    {
                        "code": "unknown_part",
                        "path": f"/steps/{i}/part",
                        "message": f"部品 {part!r} は {app.name} の部品の辞書にない",
                    }
                )
            elif step.type not in actions:
                errors.append(
                    {
                        "code": "action_not_supported",
                        "path": f"/steps/{i}/type",
                        "message": f"部品 {part!r} は {step.type} に対応していない"
                        f"（使えるのは {actions}）",
                    }
                )
        return errors

    # 実行

    def run_testcase(self, testcase_id: str) -> Run:
        """runner で実行し、結果を判定して保存する。終わるまで待つ。"""
        record = self.get_testcase(testcase_id)
        if record.review_status.value == "pending":
            raise Conflict(
                "review_pending", "人の確認待ちのため実行できない。承認してから実行する"
            )
        testcase = record.testcase
        # 登録のあとで部品の辞書が変わっていることがあるので、照らし直す
        out_of_date = self._check_parts(testcase)
        if out_of_date:
            details = "、".join(e["message"] for e in out_of_date)
            raise Conflict(
                "testcase_out_of_date", f"いまの部品の辞書に合わない：{details}"
            )

        app = self._apps[testcase.app_id.root]
        steps = [s.root for s in testcase.steps]
        conversions = [app.conversions[(s.part.root, s.type)] for s in steps]
        run_id = new_id("run")
        command = {
            "run_id": run_id,
            "app": app.runner_app,
            "screenshot": app.screenshot,
            "steps": [c.runner_step for c in conversions],
        }
        started_at = self._now()
        raw = self._runner.run(command)
        finished_at = self._now()

        broken = self._why_broken(raw, run_id, len(steps))
        if broken:
            error = {
                "code": "invalid_runner_result",
                "message": f"runner の結果が契約に合わない：{broken}",
            }
            run = self._error_run(
                run_id, testcase_id, steps, started_at, finished_at, error
            )
        else:
            run = self._judge(run_id, testcase_id, steps, conversions, raw)
        self._store.save_run(run)
        return run

    def _why_broken(self, raw: Any, run_id: str, step_count: int) -> str | None:
        """runner の結果が使えないなら、その理由。"""
        found = contract_check.problems("runner-result.schema.json", raw)
        if found:
            return "、".join(f"{p or '/'}：{m}" for p, m in found)
        if raw["run_id"] != run_id:
            return f"run_id が命令と違う（{raw['run_id']!r}）"
        indexes = [s["index"] for s in raw["steps"]]
        if indexes != list(range(len(indexes))) or len(indexes) > step_count:
            return f"steps の index が命令の順になっていない（{indexes}）"
        if raw["status"] == "completed" and len(indexes) != step_count:
            return (
                f"completed なのに、ステップが {len(indexes)} 個しかない"
                f"（命令は {step_count} 個）"
            )
        for s in raw["steps"]:
            if "screenshot" in s:
                try:
                    base64.b64decode(s["screenshot"]["data_base64"], validate=True)
                except binascii.Error:
                    return f"/steps/{s['index']}/screenshot：Base64 として読めない"
        return None

    def _judge(self, run_id, testcase_id, steps, conversions, raw) -> Run:
        """runner の結果から、ステップごとの合否と、実行の合否を決める。"""
        results = raw["steps"]
        run_steps = []
        first_error = raw.get("error")
        for i, step in enumerate(steps):
            entry: dict[str, Any] = {
                "index": i,
                "step": step.model_dump(exclude_none=True),
            }
            if i >= len(results):
                entry["status"] = "skipped"
                run_steps.append(entry)
                continue
            result = results[i]
            if "screenshot" in result:
                png = base64.b64decode(result["screenshot"]["data_base64"])
                entry["screenshot_id"] = self._store.save_screenshot(png)
            if result["status"] == "error":
                entry["status"] = "error"
                entry["message"] = result["error"]["message"]
                first_error = first_error or result["error"]
            elif step.type == "expect_text":
                entry.update(
                    self._check_text(step.expected, conversions[i], result.get("text"))
                )
            else:
                entry["status"] = "passed"
            run_steps.append(entry)

        statuses = {s["status"] for s in run_steps}
        run: dict[str, Any] = {
            "id": run_id,
            "testcase_id": testcase_id,
            "started_at": raw["started_at"],
            "finished_at": raw["finished_at"],
            "steps": run_steps,
        }
        if raw["status"] == "aborted" or "error" in statuses:
            run["status"] = "error"
            run["error"] = first_error or {
                "code": "step_error",
                "message": "ステップでエラーが起きた",
            }
        elif "failed" in statuses:
            run["status"] = "failed"
        else:
            run["status"] = "passed"
        return Run.model_validate(run)

    @staticmethod
    def _check_text(expected: str, conversion, text: str | None) -> dict[str, str]:
        if text is None:
            return {"status": "error", "message": "runner が読んだ文字を返さなかった"}
        actual = conversion.extract(text) if conversion.extract else text
        if actual is None:
            return {
                "status": "failed",
                "message": f"読んだ文字「{text}」から値を取り出せない",
            }
        if actual != expected:
            return {
                "status": "failed",
                "actual": actual,
                "message": f"期待する値は「{expected}」だが、読んだ値は「{actual}」",
            }
        return {"status": "passed", "actual": actual}

    @staticmethod
    def _error_run(run_id, testcase_id, steps, started_at, finished_at, error) -> Run:
        return Run.model_validate(
            {
                "id": run_id,
                "testcase_id": testcase_id,
                "status": "error",
                "started_at": started_at,
                "finished_at": finished_at,
                "error": error,
                "steps": [
                    {
                        "index": i,
                        "step": s.model_dump(exclude_none=True),
                        "status": "skipped",
                    }
                    for i, s in enumerate(steps)
                ],
            }
        )

    # 実行の結果

    def list_runs(self, testcase_id: str | None = None) -> list[Run]:
        return self._store.list_runs(testcase_id)

    def get_run(self, run_id: str) -> Run:
        run = self._store.get_run(run_id)
        if run is None:
            raise NotFound("not_found", f"実行の結果 {run_id!r} はない")
        return run

    def get_screenshot(self, screenshot_id: str) -> bytes:
        png = self._store.get_screenshot(screenshot_id)
        if png is None:
            raise NotFound("not_found", f"スクショ {screenshot_id!r} はない")
        return png
