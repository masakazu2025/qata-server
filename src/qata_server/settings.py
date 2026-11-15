"""server の設定。環境変数から読むのはここだけで、ほかはこの型を受け取る。

Settings（立ち上げの設定）：
- `QATA_DATA_DIR`：保存先のフォルダ（既定は `./data`）
- `QATA_RUNNER_URL`：runner の場所（既定は `http://127.0.0.1:8001`）
- `QATA_HOST`・`QATA_PORT`：server が待ち受ける場所（既定は `127.0.0.1:8000`）

ParentSettings（親の契約の場所）：
- `QATA_PARENT_DIR`：親のリポジトリ。既定は、作業フォルダで隣に並べた `../qata/`

二つに分けるのは、契約を読むところ（判定・型の生成）が、立ち上げの設定の誤りで
巻き添えに落ちないようにするため（S10）。空の環境変数は、置いていないものとして扱う。
"""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_CONFIG = SettingsConfigDict(env_prefix="QATA_", env_ignore_empty=True)

# src/qata_server/settings.py から見て、qata-server の隣の qata
_SIBLING_PARENT = Path(__file__).resolve().parents[3] / "qata"


class Settings(BaseSettings):
    model_config = _CONFIG

    data_dir: Path = Path("data")
    runner_url: str = "http://127.0.0.1:8001"
    host: str = "127.0.0.1"
    port: int = 8000


class ParentSettings(BaseSettings):
    model_config = _CONFIG

    parent_dir: Path = _SIBLING_PARENT
