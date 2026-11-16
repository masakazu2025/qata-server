# qata-server

[qata](https://github.com/masakazu2025/qata) の server です。部品の辞書の提供、テストケースの検証・登録、実行の指揮、結果の保存を受け持ちます。LLM は呼びません。テストケースを考えるのは MCP の向こうの AI で、server は道具と関門だけを持ちます。

契約と全体の要件は、親のリポジトリ `qata` が正です。このリポジトリは、親と同じ作業フォルダに並べて置きます（`../qata/contracts/` を読むため）。親を別の場所に置くときは、環境変数 `QATA_PARENT_DIR` で親のリポジトリを指します。

```
作業フォルダ/
├── qata/          ← 親
└── qata-server/   ← ここ
```

やることは、このリポジトリの GitHub の issue で管理しています。部品をまたぐものと全体の判断は、親の [qata の issue](https://github.com/masakazu2025/qata/issues) に置きます。

## 関門

pull request と main への push のたびに、GitHub Actions（`.github/workflows/ci.yml`）が下を回します。通らないと main にマージできません。

```
uv sync
uv run pytest          # 契約・application・REST・MCP・設定・依存の向き（import-linter）
uv run ruff check
uv run ruff format --check
uv run pyright         # 型（契約から生成した型は報告から外す）
```

## 契約から型を生成する

親の契約（JSON Schema）から pydantic の型を生成し、`src/qata_server/contracts/` に置いてコミットします。手で直しません。契約が変わったら生成し直します。生成物が契約と合っているかは `pytest` で確かめます。

```
uv run python scripts/generate_contracts.py
```

## アプリの設定

対象のアプリごとに、部品の辞書と変換の規則（部品の名前 → キー・座標・読み取りの場所）を `src/qata_server/apps/<アプリ>.json` に書きます（[docs/decisions.md](docs/decisions.md) の S3）。AI と web に見せる部品の辞書は、ここから作ります。

## 立ち上げる

```
uv run qata-server
```

`http://127.0.0.1:8000` で待ち受けます（API の一覧は `/docs`）。runner は `http://127.0.0.1:8001` にあるものとします。変えるときは、下の「設定」の環境変数を使います。

## 設定

設定は環境変数で渡します。設定ファイル（`.env` など）は読みません。何も渡さなければ、下の既定値で動きます。変えたい項目だけを、立ち上げるときに渡します。

| 環境変数 | 中身 | 既定値 |
| --- | --- | --- |
| `QATA_HOST` | server が待ち受けるアドレス | `127.0.0.1` |
| `QATA_PORT` | server が待ち受けるポート | `8000` |
| `QATA_RUNNER_URL` | runner の場所 | `http://127.0.0.1:8001` |
| `QATA_DATA_DIR` | 保存先のフォルダ（テストケース・実行の結果・スクショ） | `./data`（立ち上げたフォルダから見て） |
| `QATA_PARENT_DIR` | 親のリポジトリ（契約を読む） | 隣に並べた `../qata` |

- 空の環境変数は、置いていないものとして扱います（既定値になります）。
- `QATA_PORT` が数でないときは、立ち上げる前に誤りで止まります。

渡し方の例（PowerShell）：

```
$env:QATA_PORT = '9000'; $env:QATA_DATA_DIR = 'C:\qata-data'; uv run qata-server
```

ほかに渡しているところ：web の端から端までのテスト（qata-web の `playwright.config.ts`）、CI（`.github/workflows/ci.yml`）、MCP の登録（下の `claude mcp add -e`）。

環境変数を読むのは `src/qata_server/settings.py`（pydantic-settings）だけです。項目を足すときは、ここに足します。

## 表の形を変える

保存は SQLite で、表は `src/qata_server/application/store.py` に SQLAlchemy で定義しています。表の形の変更は、Alembic のマイグレーション（`src/qata_server/migrations/versions/`）で記録します。server は立ち上げるとき（REST も MCP も）に、マイグレーションを最新まで当てます。手元の保存先のデータは、そのまま残ります。

表の形を変えるときは、次の順に進めます。

1. `store.py` の表の定義を変える。
2. マイグレーションを一つ足す。いまの保存先（`QATA_DATA_DIR`、既定は `./data`）と見比べて、差を書き出します。

   ```
   uv run alembic upgrade head
   uv run alembic revision --autogenerate -m "<何を変えるか>"
   ```

3. できたファイル（`versions/<番号>_<何を変えるか>.py`）を読み、`upgrade` と `downgrade` を確かめて直す。書き出しは表と列の増減までで、もうある記録の JSON の中身を新しい形に直すことは、手で書きます。番号は、前の番号の次にします（`--rev-id 0002` で決められます）。
4. `uv run pytest` を回す。表の定義とマイグレーションがずれていないこと、古い保存先を読めることを確かめます（`tests/application/test_store.py`）。
5. server を立ち上げ直すと、新しいマイグレーションが当たる。

書き出したファイルには、`ruff check --fix` と `ruff format` が自動でかかります（`alembic.ini` の `post_write_hooks`）。Alembic の CLI の設定は `alembic.ini` です。Windows では日本語を読めないので、この設定ファイルには英数字だけを書きます。

## MCP で使う

AI（MCP のクライアント）からは、stdio で立ち上げます。道具は親の `mcp-tools.json` のとおりです。

```
uv run --directory <qata-server の場所> qata-server-mcp
```

REST の server と同じテストケースや実行の結果を見るには、`QATA_DATA_DIR` を同じ場所（絶対パス）にします。たとえば Claude Code では次のように足します。

```
claude mcp add qata -e QATA_DATA_DIR=<保存先> -- uv run --directory <qata-server の場所> qata-server-mcp
```
