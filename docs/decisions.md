# 決めたこと

この部品の中だけで閉じることを残します。全体に関わることは親の `../qata/docs/decisions.md` に置きます。新しいものを上に足します。

---

## S14. 読む契約の版を写して持ち、立ち上げたときにそろっていることを確かめる

- 決めた人：AI　レビュー：未（人のレビューは要らない。形は親の D54 で決めたもの）
- 形は親の [repos-and-contracts.md の「子の持ち方」](https://github.com/masakazu2025/qata/blob/main/.claude/rules/qata/repos-and-contracts.md#子の持ち方)のとおり。写す道具 `scripts/sync_contracts.py` は、runner のもの（qata-runner の R6）と同じ中身にした。写す・`--check`・`--warn-if-old` を一つに持つ。子の道具は子が持つ決まりなので、共通にはしない。
- **契約の場所は設定にしない。** `ParentSettings`・`QATA_PARENT_DIR` を消した。読む場所は `qata-contracts/` の一つだけで、変えられると、読む版を固定した意味がなくなるため。場所は `contract_check.py` が持ち（`CONTRACTS_DIR`・`SCHEMAS_DIR`・`MCP_TOOLS`）、MCP の入口もそこから取る。
- **`main.build` で、使う契約がそろっていることを確かめる（`contract_check.ensure_ready`）。** server は動いている間も契約を読む（テストケースと runner の結果の判定、部品の辞書と変換の結果の判定、MCP の道具の形）。使う契約から `$ref` をたどり、指す先（`common` も）がすべて引けることまで見る。`$ref` の解決は判定のときまで遅れ、ファイルが一つ欠けても最初の呼び出しまで気づけないため（runner の R6 と同じ理由）。Service を直に作るテストは通らないので、確かめは組み立ての入口に置いた。
- **`--warn-if-old` は、タグを取る（`list_tags`）・出す一行を作る（`old_version_notice`）・出す（`warn_if_old`）に分けた。** 警告の形と、タグが取れないときに落ちないことを、ネットにつながずにテストで確かめるため（reviewer の指摘。runner は版を比べる関数だけをテストしている）。
- 1.0.0 で型を作り直したが、変わらなかった（タグの型は qata-server#22 で、親の `main` から作っていた）。

---

## S13. タグは、記録の JSON とは別に、テストケースとタグの組の表にも持つ

- 決めた人：AI（タグの形と絞り込みの約束は親の D49・D50）　レビュー：未（人のレビューは要らない。あとで変えてよい）
- **正は記録の JSON の中のタグ。絞り込みのために、組の表（`testcase_tags`：テストケースの ID とタグ、二つで主キー）に写す。** 記録を JSON のまま持つ形（S4）は変えない。タグで絞るには中を探す要が出たので、探す分だけを表にした。SQLite の JSON の関数（`json_each`）で記録の中を探す形もあるが、表にしておけば、ほかの保存先に移るときも同じ問い合わせで済む。
- **保存のたびに、組を記録に合わせて入れ直す。** 承認の上書きでも同じ。消すときは組も消す。同じトランザクションの中で行うので、記録と組はずれない。
- **絞り込みは、指定したタグを持つ組を ID ごとに数え、数が重なりを除いたタグの数と同じものを返す（AND）。** タグごとに副問い合わせを重ねる形は、タグを 1000 個ほど並べると SQLite の式の深さの上限に届き、500 になった（別の AI のレビュー）。重なりは集合にして一つと見なし、空なら絞り込まない（契約の `tag_filter`）。
- **マイグレーション 0002 で表を作り、もうある記録のタグも写す。** タグを足す前の記録はタグを持たないので、ふつうは写すものがない。写す処理は数行で、記録と組がずれた保存先を作らないために入れた。
- **REST の `tag` は検証しない。** ほかの引数と同じく文字列で受ける（S6）。空の文字や 101 文字のタグは、どのテストケースも持たないので 0 件になる。MCP は道具の入力の形で検査するので、同じものは `invalid_arguments` で断る。どちらも、正しいタグなら同じものを返す（`tests/mcp/mcp.feature` で比べる）。

## S12. MCP は Streamable HTTP にして、REST と同じプロセスに載せる

- 決めた人：AI（同じプロセスにすることは親の D43）　レビュー：未（人のレビューは要らない。あとで変えてよい）
- **道は `/mcp`。** `main.py` の `build` で、MCP の SDK の `streamable_http_app` が作る道を FastAPI の道に足し、SDK のセッションの管理を FastAPI の lifespan で回す。REST と MCP は同じ Service（同じ Store・同じ runner への道具）を使う。MCP の道は FastAPI の道ではないので、OpenAPI には出ず、openapi.yaml との突き合わせは変わらない。
- **stdio の入口（`qata-server-mcp`）は消す。** 残すと、二つのプロセスから runner に命令を送れる形が残り、まとめて流す・進み具合を見るための実行の待ち行列を、一か所に持てないため（qata-server#14）。MCP のクライアントは、先に立ち上げた server に HTTP でつなぐ。
- **セッションは SDK の既定のまま（状態あり、応答は SSE）。** Claude Code も TypeScript の SDK もそのままつながる。困ってから変える。
- **DNS rebinding の守りは SDK に任せる。** 待ち受ける場所（`QATA_HOST`）を渡すと、手元（`127.0.0.1` など）のときは SDK が Host と Origin を確かめる。手元でないときは守りが入らないが、いまは手元でしか使わない。
- 「一つのプロセスで REST と MCP の両方に答える」は、`qata-server` を本当に立ち上げて確かめる（`tests/mcp/mcp.feature`）。REST の `/apps`、MCP の道具の一覧と `list_apps`、ほかの名前で届いた呼び出しを断ること。ほかの MCP のシナリオは、いままでどおり同じプロセスの中でつなぐ。

## S11. 保存は SQLAlchemy の Core と Alembic で扱う

- 決めた人：AI（SQLAlchemy 2・Alembic にすることは親の D43）　レビュー：未（人のレビューは要らない。あとで変えてよい）
- **ORM ではなく Core。** 記録は契約の形の JSON のまま持つので（S4）、行をオブジェクトに写す要がない。表の定義（`store.py` の `METADATA`）は、マイグレーションと突き合わせる正としても使う。
- **立ち上げるときに、最新まで当てる。** Store を作るときに、つないだ connection を Alembic に渡して当てる。人が手で当てる手順を増やさないため。server の立ち上げで当たる。
- **Alembic の前の保存先は、最初のマイグレーションで受ける。** 表はあるが記録がない保存先では、表を作らずに記録だけを付ける。保存先を消さずに、そのまま読めるようにするため。
- **表と並びは変えない。** 新しい順は、いままでどおり rowid の逆（S4）。並べる列を足すと、表の形が変わるため。
- **出力は stderr。** はじめは MCP が stdout を通り道に使っていたため（いまは HTTP、S12）。
- **alembic.ini は英数字だけ。** Windows では、Alembic が設定ファイルを日本語の文字コード（cp932）で読み、UTF-8 の日本語で落ちるため。説明は README に書く。
- **当てる間は、SQLite のファイルを排他で握る。** REST と MCP が別のプロセスで同時に立ち上がると、二つが同じマイグレーションを当てようとして、片方が落ちる（別の AI のレビューで見つかった。前の作りは `CREATE TABLE IF NOT EXISTS` で落ちなかった）。`BEGIN EXCLUSIVE` で一つずつにし、あとから来たほうは待ってから版を読む。MCP を REST と同じプロセスにしたので（S12）、この場面はなくなった。残るのは、server を二つ同じ保存先で立ち上げるときと、立ち上げと CLI の `alembic upgrade` がぶつかるときだけ。どちらも普通の使い方ではないが、手当ては小さいので残す。
- **同時に立ち上げるテストは置かない。** 排他が効かなくなっても、普通でない場面で立ち上げが一度落ちるだけで、データは失わず、結果も誤らない（親の findings.md の基準で、どちらも「いいえ」）。二つのプロセスで試すテストは 12 秒かかり、見合わない。作ったときに、排他を外すと落ち、入れると通ることは確かめた（人、2026-11-16）。

## S10. 設定は settings.py の型で読む

- 決めた人：AI　レビュー：未（人のレビューは要らない。PoC が終わったときにまとめて振り返る、親の D25）
- 環境変数から読むのは `src/qata_server/settings.py` の pydantic-settings の型だけ。名前と既定値は前のまま。
  - `Settings`：立ち上げの設定（`QATA_DATA_DIR`・`QATA_RUNNER_URL`・`QATA_HOST`・`QATA_PORT`）
  - `ParentSettings`：親の契約の場所（`QATA_PARENT_DIR`）。S14 で消した
  - 二つに分けたのは、契約を読むところが、関係のない立ち上げの設定の誤り（数でない `QATA_PORT` など）で巻き添えに落ちないようにするため（レビューの指摘）。
- `main.py` の組み立て（`build`・`build_service`）は `Settings` を受け取る。立ち上げ（`serve`）が一度だけ `Settings()` を作る。
- 親の契約の場所は、契約の判定（`contract_check.py`）と型の生成（`scripts/generate_contracts.py`）が、読み込んだときに `ParentSettings().parent_dir` から取る（S14 で、`qata-contracts/` を読む形に変えた）。判定の道具はプロセスの間使い回していて、受け取る形にすると Service や MCP まで通すことになり、いまは得がないため。
- `settings.py` は依存の層で、契約の型と同じ一番下に置く。application からも読めるようにするため。
- 空の環境変数は、置いていないものとして扱う（前の `QATA_PARENT_DIR` と同じ）。ほかの設定も、空なら既定値になる。数でない `QATA_PORT` は、立ち上げる前に誤りにする。
- ほかに環境変数を読むところがないことは、テスト（`tests/settings.feature`）で確かめる。`environ`・`getenv` が出てきたら読むとみなし、子のプロセスに環境をそのまま渡す `{**os.environ}` の形だけを許す。

## S9. 型の検査は pyright の standard で、契約から生成した型は報告から外す

- 決めた人：AI　レビュー：未（人のレビューは要らない。PoC が終わったときにまとめて振り返る、親の D25）
- 関門に `uv run pyright` を足した。設定は pyproject.toml の `[tool.pyright]`。対象は src・tests・scripts。
- モードは standard。strict は、型の付いていないライブラリ（jsonschema など）の扱いで誤りが多く出て、中身より抑えの記述が増えるため。困ったら上げる。
- 契約から生成した型（`src/qata_server/contracts`）は、ruff と同じく報告から外す。手で直さない生成物のため。外しても、import されれば型は読まれるので、使い方の誤りは捕まる。
- `extraPaths` は pytest の `pythonpath` と同じ（scripts・tests）。テストが直下のモジュールを import するため。
- 出た誤りは、動きを変えずに型を合わせて直した（`isinstance` で絞る、注釈を足す）。

## S8. 本物の電卓に合わせる：大きさ・前準備・座標

- 決めた人：AI　レビュー：未（人のレビューは要らない。PoC が終わったときにまとめて振り返る、親の D25）
- 電卓の大きさは 400 x 600。電卓は 336 x 509 より小さくできない（runner の R3）ので、余裕を持たせた。
- 電卓は前に使ったモード（標準・関数電卓）で開き、モードでボタンの位置が変わる。そこで、アプリの設定に `prepare`（前準備）を足し、決まった状態から始める。電卓では、ナビのボタン（32, 57）→「標準」（136, 137）をタップする。この二つの位置はモードによらない。
  - 契約は変えない。キーの同時押し（Alt+1 で標準になる）は契約で扱わない（親の D13）ので、タップにした。
  - 前準備は runner への命令の基本の操作で書き、読み込むときに契約に照らす。server が命令の頭に足し、結果からは除いて、番号をテストケースのステップに合わせる。前準備のスクショは残さない。
  - 前準備で止まったら、テストケースのステップはどれも skipped にし、エラーの説明を「前準備で止まった：」で始める。
- 標準・400 x 600 での座標（外枠の左上から、物理ピクセル）は、本物の電卓で UI Automation のボタンの中心を測った。1（58, 499）・2（153, 499）・3（248, 499）・＋（342, 499）・＝（342, 559）。関数電卓・標準のどちらから始めても、タップで計算が合うことを本物の runner で確かめた。
- 親の契約の例 runner-command.json は、server が電卓に送る命令そのものにした（前準備・大きさ・座標）。関門の「命令は親の例と、run_id のほかは同じ」が、本物に合う命令を確かめる形になる。

## S7. MCP の入口

- 決めた人：AI　レビュー：未（人のレビューは要らない。PoC が終わったときにまとめて振り返る、親の D25）
- 入口は `mcp_server.py` の `create_server(service)`。MCP の Python SDK（2.x）の低い層の `Server` を使う。道具の形を、関数の型から作らせず、契約のままに出すため。
- 道具の名前・説明・inputSchema・outputSchema は、実行のときに親の `mcp-tools.json` を読んで、そのまま出す。`$ref` は referencing でたどって中身に置き換え、それだけで読める形にする（クライアントは外の `$ref` をたどらない）。契約の `$ref` は循環しないので、展開で足りる。
- 道具と、それを受ける Service の呼び出しが一対一でなければ、server を立ち上げない。
- 引数は inputSchema で検査し、合わなければ `invalid_arguments` のエラーにする。ただしテストケースの中身は見ず、Service が validation_result・register_result で返す（S6 と同じ）。ない道具は `unknown_tool`。
- 道具のエラー（Service のエラーを含む）は、`isError` にして、契約の `error_response` の形を文字で返す。`code` は REST と同じ（S5）。
- 結果は structuredContent に入れ、同じものを JSON の文字でも返す（structuredContent を読まないクライアントのため）。
- 道具の呼び出しはスレッドで動かす。`run_testcase` は実行が終わるまで待つため。
- 立ち上げは、はじめ stdio（`uv run qata-server-mcp`）で、REST とは別のプロセスだった。いまは Streamable HTTP で REST と同じプロセスに載せている（S12）。
- 「MCP の道具が mcp-tools.json と合う」は、同じプロセスの中でつないだ MCP のクライアントから確かめる。
  - 名前と説明が同じ。どの形にも `$ref` が残らず、JSON Schema として正しい。
  - 展開した inputSchema が、契約の例を通し、確認事項のないもの・ステップのないものをはじく（契約と同じ判定）。
  - 道具の結果が、展開とは別に referencing で `$ref` をたどった契約の outputSchema に通る。クライアントも、server が出す outputSchema で結果を確かめる。
  - `qata-server` を立ち上げて HTTP でつなぐと、道具がすべて出る（S12）。
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
- 電卓の座標は仮の値（親の例と同じ）だった。本物の電卓で測り直した（S8）。
- 親の契約は、実行のときにも `../qata/contracts/` から読む（S1 の判定のため。S2 と同じく、次の周回で直す）。S14 で、読む版の写し `qata-contracts/` を読む形に直した。そのため jsonschema を、開発のときだけでなく実行のときの依存にした。

## S2. 契約の検査は pytest-bdd で書く

- 決めた人：AI　レビュー：済（親を相対のパスで読むのは、次の周回で直す。親の ideas.md）
- `tests/contracts/contracts.feature` に日本語の Gherkin で観点を書く。はじく例は、契約の例の一か所を変える・消す形で表に並べ、「なぜ」の列を付ける。
- 親の契約は、作業フォルダで隣に並べた `../qata/` から読む。S14 で、読む版の写し `qata-contracts/` を読む形に直した。

## S1. 型の生成のしかた

- 決めた人：AI　レビュー：済
- datamodel-code-generator で、`../qata/contracts/schemas/`（S14 から `qata-contracts/schemas/`）から `src/qata_server/contracts/` に生成する。手順は `scripts/generate_contracts.py`。
- 生成は、いつもリポジトリの外の一時フォルダで行ってから写す。生成先の ruff の設定で整形が変わり、「生成し直しても同じ」の検査が揺れないようにするため。生成物は ruff の対象から外す。
- 生成した型は、JSON Schema の `contains`（確認事項を一つは含む）や `if`/`then` を表せない。そのため、外から来るデータ（AI・web からのテストケース、runner の結果、部品の辞書のファイル）は、まず jsonschema で親の JSON Schema に照らして判定し、合格したものだけを型に読み込む。型は判定ではなく、コードで扱うための読み込みに使う（タスクの 1 で作る）。