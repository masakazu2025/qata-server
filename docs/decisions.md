# 決めたこと

この部品の中だけで閉じることを残します。全体に関わることは親の `../qata/docs/decisions.md` に置きます。新しいものを上に足します。

---

## S7. MCP の入口

- 決めた人：AI　レビュー：未（人のレビューは要らない。PoC が終わったときにまとめて振り返る、親の D25）
- 入口は `mcp_server.py` の `create_server(service)`。MCP の Python SDK（2.x）の低い層の `Server` を使う。道具の形を、関数の型から作らせず、契約のままに出すため。
- 道具の名前・説明・inputSchema・outputSchema は、実行のときに親の `mcp-tools.json` を読んで、そのまま出す。`$ref` は referencing でたどって中身に置き換え、それだけで読める形にする（クライアントは外の `$ref` をたどらない）。契約の `$ref` は循環しないので、展開で足りる。
- 道具と、それを受ける Service の呼び出しが一対一でなければ、server を立ち上げない。
- 引数は inputSchema で検査し、合わなければ `invalid_arguments` のエラーにする。ただしテストケースの中身は見ず、Service が validation_result・register_result で返す（S6 と同じ）。ない道具は `unknown_tool`。
- 道具のエラー（Service のエラーを含む）は、`isError` にして、契約の `error_response` の形を文字で返す。`code` は REST と同じ（S5）。
- 結果は structuredContent に入れ、同じものを JSON の文字でも返す（structuredContent を読まないクライアントのため）。
- 道具の呼び出しはスレッドで動かす。`run_testcase` は実行が終わるまで待つため。
- 立ち上げは stdio（`uv run qata-server-mcp`）。デモのクライアント（Claude Desktop か Claude Code か）は決まっていないが、stdio はどちらでも使える。Streamable HTTP で REST と同じプロセスに載せる形は、要るときに足す。
- REST と MCP は別のプロセスになるので、同じ `QATA_DATA_DIR` を指して、同じ SQLite とスクショを見る。Store は呼ぶたびにつなぐ（S4）ので、二つのプロセスから使ってよい。
- 「MCP の道具が mcp-tools.json と合う」は、同じプロセスの中でつないだ MCP のクライアントから確かめる。
  - 名前と説明が同じ。どの形にも `$ref` が残らず、JSON Schema として正しい。
  - 展開した inputSchema が、契約の例を通し、確認事項のないもの・ステップのないものをはじく（契約と同じ判定）。
  - 道具の結果が、展開とは別に referencing で `$ref` をたどった契約の outputSchema に通る。クライアントも、server が出す outputSchema で結果を確かめる。
  - `qata-server-mcp` を立ち上げて stdio でつなぐと、道具がすべて出る。
- 依存の向きは、`mcp_server` を `rest`・`runner_http` と同じ層に置く。
- `contract_check._registry` を `registry` にして、MCP の入口とテストから使う。

## S6. REST の入口と、runner への HTTP

- 決めた人：AI　レビュー：未（人のレビューは要らない。PoC が終わったときにまとめて振り返る、親の D25）
- 入口は `rest.py` の `create_app(service)`。組み立ては `main.py` で、設定は環境変数（`QATA_DATA_DIR`・`QATA_RUNNER_URL`・`QATA_HOST`・`QATA_PORT`）。起動は `uv run qata-server`。既定のポートは server が 8000、runner が 8001。
- テストケースの本文は FastAPI で検証しない（`Request` で受ける）。形式の誤りも validation_result で返す契約のため。JSON として読めない本文は、契約に合わない値として扱う（`schema` の問題で返す）。
- 引数はどれも文字列で受け、ID の形は Store が見る（S4）。FastAPI が自分で足す 422 は起きないので、OpenAPI から外す。
- 道がないときなど、FastAPI が出す HTTP のエラーも、契約の `error_response` の形で返す（`not_found`、それ以外は `http_<コード>`）。
- FastAPI は自分の `ValidationError`（loc・msg）で、契約の同じ名前の型を OpenAPI の中で上書きする。そのため OpenAPI を出すときに、契約の側に戻す。
- 「OpenAPI が openapi.yaml と合う」は、二つで確かめる。
  - 道ごとの operationId・引数（名前・場所・必須）・本文・応答のコードと media type が同じ。
  - openapi.yaml が契約を指すところで、FastAPI の OpenAPI がその契約から生成した型を指し、型の中身が生成した型の JSON Schema と同じ。生成した型が契約と合うことは、契約の検査（S1）で確かめている。
- 実際の応答が契約に通ることも、feature で確かめる。
- runner への道具は `runner_http.py` の `HttpRunner`（httpx）。届かない・HTTP のエラーは `RunnerUnavailable`（502）。JSON でない本文はそのまま返し、application 層が `invalid_runner_result` と判定する。待つ時間は 300 秒（実行が終わるまで待って返すため）。
- 依存の向きは import-linter の layers で、`main` → `rest`・`runner_http` → `application` → `contracts`。検査は pytest の feature から動かし、関門を `uv run pytest` に寄せる。
- テストの偽の runner は `tests/support.py` に移し、application と REST のテストで使い回す。

## S5. 実行のときの判定

- 決めた人：AI　レビュー：未（人のレビューは要らない。PoC が終わったときにまとめて振り返る、親の D25）
- 実行の前に、テストケースを部品の辞書に照らし直す。登録のあとで辞書が変わって合わなくなっていたら、`testcase_out_of_date` で断る（REST では 409 にする想定）。
- runner の結果は、まず親の `runner-result.schema.json` で判定する（S1）。そのうえで、`run_id` が命令と同じか、`index` が 0 から順か、`completed` ならステップの数が命令と同じか、スクショが Base64 で読めるかを確かめる。合わなければ、どのステップも `skipped` にして、実行の結果を `error`（`invalid_runner_result`）で残す。
- runner に届かないときは、実行の結果を残さない（REST では 502）。
- 実行の結果の `error` は、runner の結果の `error` をそのまま使う。
- 実行の結果の `started_at`・`finished_at` は、runner が返した時刻を使う。runner の結果が使えないときだけ、server の時刻を使う。
- エラーの応答の `code` は `not_found`・`review_pending`・`review_not_required`・`testcase_out_of_date`・`runner_unavailable`。契約では `code` は自由な文字列なので、契約は変えない。

## S4. 保存のしかた

- 決めた人：AI　レビュー：未（人のレビューは要らない。PoC が終わったときにまとめて振り返る、親の D25）
- 登録したテストケースと実行の結果は、SQLite に、契約の形（`testcase_record`・`run`）の JSON のまま一行で持つ。アプリ・テストケースで絞る列だけを別に持つ。中を探す要がいまはないため。
- 一覧の「新しい順」は、入れた順（rowid）の逆にする。
- スクショは PNG のファイルにし、名前は ID（`ss_` と UUID の 32 桁）。ID はファイルの名前に使うので、振った形のものだけを受ける（パスを外に出られないように）。
- ID は `tc_`・`run_`・`ss_` に UUID を付ける。
- 保存先のフォルダは、Service を作る側が渡す（REST の立ち上げで決める）。

## S3. アプリの設定と変換の枠

- 決めた人：AI　レビュー：未（人のレビューは要らない。PoC が終わったときにまとめて振り返る、親の D25）
- 親の D14 の「変換の枠」を、こう置いた。
  - アプリごとに、server の中の形の設定ファイルを一つ置く（`src/qata_server/apps/<アプリ>.json`）。起動のしかた・ウィンドウ・スクショの範囲・部品を持つ。
  - 部品には、アクションごとに変換の規則を `{"kind": ..., ...}` で書く。部品の辞書の `actions` は、規則のあるアクションから作る（二か所に書かず、食い違わないようにする）。
  - 規則の種類（kind）ごとの変換を `conversion.py` の `CONVERTERS` に持つ。いまは汎用の `key`（キーを押す）・`tap`（座標をタップする）・`uia`（UI Automation で読み、正規表現で値を取り出す）の三つ。内製のツールは、ここに種類を足して広げる。
  - 読み込むときに、規則の書き方と、変換の結果が runner への命令の契約（`runner-command.schema.json`）に合うかを確かめる。合わなければ server を立ち上げない。
- 電卓の座標は仮の値（親の例と同じ）。本物の runner に置き換えるときに測り直す。
- 親の契約は、実行のときにも `../qata/contracts/` から読む（S1 の判定のため。S2 と同じく、次の周回で直す）。そのため jsonschema を、開発のときだけでなく実行のときの依存にした。

## S2. 契約の検査は pytest-bdd で書く

- 決めた人：AI　レビュー：済（親を相対のパスで読むのは、次の周回で直す。親の ideas.md）
- `tests/contracts/contracts.feature` に日本語の Gherkin で観点を書く。はじく例は、契約の例の一か所を変える・消す形で表に並べ、「なぜ」の列を付ける。
- 親の契約は、作業フォルダで隣に並べた `../qata/` から読む。

## S1. 型の生成のしかた

- 決めた人：AI　レビュー：済
- datamodel-code-generator で、`../qata/contracts/schemas/` から `src/qata_server/contracts/` に生成する。手順は `scripts/generate_contracts.py`。
- 生成は、いつもリポジトリの外の一時フォルダで行ってから写す。生成先の ruff の設定で整形が変わり、「生成し直しても同じ」の検査が揺れないようにするため。生成物は ruff の対象から外す。
- 生成した型は、JSON Schema の `contains`（確認事項を一つは含む）や `if`/`then` を表せない。そのため、外から来るデータ（AI・web からのテストケース、runner の結果、部品の辞書のファイル）は、まず jsonschema で親の JSON Schema に照らして判定し、合格したものだけを型に読み込む。型は判定ではなく、コードで扱うための読み込みに使う（タスクの 1 で作る）。