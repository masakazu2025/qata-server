"""server の設定。環境変数から読むのはここだけで、ほかは Settings を受け取る。

- `QATA_DATA_DIR`：保存先のフォルダ（既定は `./data`）
- `QATA_RUNNER_URL`：runner の場所（既定は `http://127.0.0.1:8001`）
- `QATA_HOST`・`QATA_PORT`：server が待ち受ける場所（既定は `127.0.0.1:8000`）
- `QATA_PARENT_DIR`：親のリポジトリ（契約を読む）。
  既定は、作業フォルダで隣に並べた `../qata/`

空の環境変数は、置いていないものとして扱う。
"""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# src/qata_server/settings.py から見て、qata-server の隣の qata
_SIBLING_PARENT = Path(__file__).resolve().parents[3] / "qata"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="QATA_", env_ignore_empty=True)

    data_dir: Path = Path("data")
    runner_url: str = "http://127.0.0.1:8001"
    host: str = "127.0.0.1"
    port: int = 8000
    parent_dir: Path = _SIBLING_PARENT
