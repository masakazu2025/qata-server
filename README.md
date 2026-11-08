# qata-server

[qata](https://github.com/masakazu2025/qata) の server です。部品の辞書の提供、テストケースの検証・登録、実行の指揮、結果の保存を受け持ちます。LLM は呼びません。テストケースを考えるのは MCP の向こうの AI で、server は道具と関門だけを持ちます。

契約と全体の要件は、親のリポジトリ `qata` が正です。このリポジトリは、親と同じ作業フォルダに並べて置きます（`../qata/contracts/` を読むため）。親を別の場所に置くときは、環境変数 `QATA_PARENT_DIR` で親のリポジトリを指します。

```
作業フォルダ/
├── qata/          ← 親
└── qata-server/   ← ここ
```

## 関門

pull request と main への push のたびに、GitHub Actions（`.github/workflows/ci.yml`）が下を回します。通らないと main にマージできません。

```
uv sync
uv run pytest          # 契約・application・REST・MCP・依存の向き（import-linter）
uv run ruff check
uv run ruff format --check
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

`http://127.0.0.1:8000` で待ち受けます（API の一覧は `/docs`）。runner は `http://127.0.0.1:8001` にあるものとします。変えるときは環境変数 `QATA_HOST`・`QATA_PORT`・`QATA_RUNNER_URL`・`QATA_DATA_DIR`（保存先、既定は `./data`）を使います。

## MCP で使う

AI（MCP のクライアント）からは、stdio で立ち上げます。道具は親の `mcp-tools.json` のとおりです。

```
uv run --directory <qata-server の場所> qata-server-mcp
```

REST の server と同じテストケースや実行の結果を見るには、`QATA_DATA_DIR` を同じ場所（絶対パス）にします。たとえば Claude Code では次のように足します。

```
claude mcp add qata -e QATA_DATA_DIR=<保存先> -- uv run --directory <qata-server の場所> qata-server-mcp
```
