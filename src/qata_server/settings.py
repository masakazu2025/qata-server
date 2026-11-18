"""server の設定。環境変数から読むのはここだけで、ほかはこの型を受け取る。

- `QATA_DATA_DIR`：保存先のフォルダ（既定は `./data`）
- `QATA_RUNNER_URL`：runner の場所（既定は `http://127.0.0.1:8001`）
- `QATA_HOST`・`QATA_PORT`：server が待ち受ける場所（既定は `127.0.0.1:8000`）

空の環境変数は、置いていないものとして扱う。契約の場所は設定にしない。
読む版の契約は、リポジトリの直下の qata-contracts/ にある（S14）。
"""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="QATA_", env_ignore_empty=True)

    data_dir: Path = Path("data")
    runner_url: str = "http://127.0.0.1:8001"
    host: str = "127.0.0.1"
    port: int = 8000
