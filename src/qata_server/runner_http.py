"""本物の runner に、HTTP で命令を送る（runner の `POST /runs`）。"""

from typing import Any

import httpx

from qata_server.application import RunnerBusy, RunnerUnavailable


class HttpRunner:
    def __init__(
        self,
        base_url: str,
        timeout: float = 300.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        # 実行が終わるまで待って返すので、待つ時間は長めにする
        self._client = httpx.Client(
            base_url=base_url, timeout=timeout, transport=transport
        )

    def run(self, command: dict[str, Any]) -> Any:
        try:
            response = self._client.post("/runs", json=command)
        except httpx.HTTPError as exc:
            raise RunnerUnavailable(f"runner に届かない：{exc!r}") from exc
        if response.status_code == 409 and _code(response) == "runner_busy":
            raise RunnerBusy(
                "runner がほかの実行の最中なので、実行しなかった。"
                "終わってからもう一度実行する"
            )
        if response.is_error:
            raise RunnerUnavailable(
                f"runner が命令を受けなかった（HTTP {response.status_code}）："
                f"{response.text[:200]}"
            )
        try:
            return response.json()
        except ValueError:
            # JSON でなければ、そのまま返す。契約に合わないものとして server が判定する
            return response.text


def _code(response: httpx.Response) -> str | None:
    """runner のエラーの本文（契約の共通の部品 error）の code。読めなければ None。"""
    try:
        body = response.json()
    except ValueError:
        return None
    return body.get("code") if isinstance(body, dict) else None
