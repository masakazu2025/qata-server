# qata-server

[qata](https://github.com/masakazu2025/qata) の server です。部品の辞書の提供、テストケースの検証・登録、実行の指揮、結果の保存を受け持ちます。LLM は呼びません。テストケースを考えるのは MCP の向こうの AI で、server は道具と関門だけを持ちます。

契約と全体の要件は、親のリポジトリ `qata` が正です。契約は、その版を `qata-contracts/` に写して持つので（下の「読む契約の版」）、このリポジトリだけで動きます。

やることは、このリポジトリの GitHub の issue で管理しています。部品をまたぐものと全体の判断は、親の [qata の issue](https://github.com/masakazu2025/qata/issues) に置きます。

## 関門

pull request と main への push のたびに、GitHub Actions（`.github/workflows/ci.yml`）が下を回します。通らないと main にマージできません。

```
uv sync
uv run python scripts/sync_contracts.py --check  # 契約の写しを手で直していないか
uv run pytest          # 契約・application・REST・MCP・設定・依存の向き（import-linter）
uv run ruff check
uv run ruff format --check
uv run pyright         # 型（契約から生成した型は報告から外す）
```

CI は、読む契約の版が親の最新より古いと警告を出します（関門は落としません。`sync_contracts.py --warn-if-old`）。

## 読む契約の版

server は、親の契約の版を一つ選んで写して持ち、その版だけを読みます。親の `main` が進んでも、ここで版を上げるまで前の版を読み続けます。隣に並べた親（`../qata/`）の中身は読みません。

- 写し：`qata-contracts/`。親のタグ `contracts-v<版>` の `contracts/` を丸ごと写したもの。手で直しません。
- 読む版：`qata-contracts/VERSION`。変更の記録は `qata-contracts/CHANGELOG.md`。
- 型の生成・テスト・実行（判定と MCP の道具の形）は、どれも `qata-contracts/` を読みます。立ち上げるときに、使う契約がそろっているかを確かめ、欠けていれば落ちます。

版を上げるときは、写し直してから型を生成し直します。

```
uv run python scripts/sync_contracts.py 1.1.0
uv run python scripts/generate_contracts.py
```

## 契約から型を生成する

読む版の契約（JSON Schema）から pydantic の型を生成し、`src/qata_server/contracts/` に置いてコミットします。手で直しません。契約が変わったら生成し直します。生成物が契約と合っているかは `pytest` で確かめます。

```
uv run python scripts/generate_contracts.py
```

## アプリの設定

対象のアプリごとに、部品の辞書と変換の規則（部品の名前 → キー・座標・読み取りの場所）を `src/qata_server/apps/<アプリ>.json` に書きます（[docs/decisions.md](docs/decisions.md) の S3）。AI と web に見せる部品の辞書は、ここから作ります。

## 立ち上げる

```
uv run qata-server
```

`http://127.0.0.1:8000` で待ち受けます（API の一覧は `/docs`）。同じプロセスが、web 用の REST と、AI 用の MCP（`/mcp`、下の「MCP で使う」）の両方に答えます。runner は `http://127.0.0.1:8001` にあるものとします。変えるときは、下の「設定」の環境変数を使います。

## 設定

設定は環境変数で渡します。設定ファイル（`.env` など）は読みません。何も渡さなければ、下の既定値で動きます。変えたい項目だけを、立ち上げるときに渡します。

| 環境変数 | 中身 | 既定値 |
| --- | --- | --- |
| `QATA_HOST` | server が待ち受けるアドレス | `127.0.0.1` |
| `QATA_PORT` | server が待ち受けるポート | `8000` |
| `QATA_RUNNER_URL` | runner の場所 | `http://127.0.0.1:8001` |
| `QATA_DATA_DIR` | 保存先のフォルダ（テストケース・実行の結果・スクショ） | `./data`（立ち上げたフォルダから見て） |

- 空の環境変数は、置いていないものとして扱います（既定値になります）。
- `QATA_PORT` が数でないときは、立ち上げる前に誤りで止まります。

渡し方の例（PowerShell）：

```
$env:QATA_PORT = '9000'; $env:QATA_DATA_DIR = 'C:\qata-data'; uv run qata-server
```

ほかに渡しているところ：web の端から端までのテスト（qata-web の `playwright.config.ts`）、CI（`.github/workflows/ci.yml`）。

環境変数を読むのは `src/qata_server/settings.py`（pydantic-settings）だけです。項目を足すときは、ここに足します。

## 表の形を変える

保存は SQLite で、表は `src/qata_server/application/store.py` に SQLAlchemy で定義しています。表の形の変更は、Alembic のマイグレーション（`src/qata_server/migrations/versions/`）で記録します。server は立ち上げるときに、マイグレーションを最新まで当てます。手元の保存先のデータは、そのまま残ります。

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

AI（MCP のクライアント）からは、立ち上げた server の `/mcp` に Streamable HTTP でつなぎます（既定では `http://127.0.0.1:8000/mcp`）。道具は読む版の `mcp-tools.json` のとおりです。MCP のためだけに別のプロセスは立ち上げません。先に `uv run qata-server` で server を立ち上げておきます。

たとえば Claude Code では次のように足します。

```
claude mcp add --transport http qata http://127.0.0.1:8000/mcp
```

プロジェクトの `.mcp.json` に書くときは次の形です。

```json
{
  "mcpServers": {
    "qata": { "type": "http", "url": "http://127.0.0.1:8000/mcp" }
  }
}
```

server を手元（`127.0.0.1`・`localhost`）で待ち受けるときは、MCP の道に DNS rebinding の守りが入り、ほかの名前やブラウザーの別のサイトからの呼び出しは断ります。
