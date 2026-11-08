# 決めたこと

この部品の中だけで閉じることを残します。全体に関わることは親の `../qata/docs/decisions.md` に置きます。新しいものを上に足します。

---

## S5. 実行のときの判定

- 決めた人：AI　レビュー：未
- 実行の前に、テストケースを部品の辞書に照らし直す。登録のあとで辞書が変わって合わなくなっていたら、`testcase_out_of_date` で断る（REST では 409 にする想定）。
- runner の結果は、まず親の `runner-result.schema.json` で判定する（S1）。そのうえで、`run_id` が命令と同じか、`index` が 0 から順か、`completed` ならステップの数が命令と同じか、スクショが Base64 で読めるかを確かめる。合わなければ、どのステップも `skipped` にして、実行の結果を `error`（`invalid_runner_result`）で残す。
- runner に届かないときは、実行の結果を残さない（REST では 502）。
- 実行の結果の `error` は、runner の結果の `error` をそのまま使う。
- 実行の結果の `started_at`・`finished_at` は、runner が返した時刻を使う。runner の結果が使えないときだけ、server の時刻を使う。
- エラーの応答の `code` は `not_found`・`review_pending`・`review_not_required`・`testcase_out_of_date`・`runner_unavailable`。契約では `code` は自由な文字列なので、契約は変えない。

## S4. 保存のしかた

- 決めた人：AI　レビュー：未
- 登録したテストケースと実行の結果は、SQLite に、契約の形（`testcase_record`・`run`）の JSON のまま一行で持つ。アプリ・テストケースで絞る列だけを別に持つ。中を探す要がいまはないため。
- 一覧の「新しい順」は、入れた順（rowid）の逆にする。
- スクショは PNG のファイルにし、名前は ID（`ss_` と UUID の 32 桁）。ID はファイルの名前に使うので、振った形のものだけを受ける（パスを外に出られないように）。
- ID は `tc_`・`run_`・`ss_` に UUID を付ける。
- 保存先のフォルダは、Service を作る側が渡す（REST の立ち上げで決める）。

## S3. アプリの設定と変換の枠

- 決めた人：AI　レビュー：未
- 親の D14 の「変換の枠」を、こう置いた。
  - アプリごとに、server の中の形の設定ファイルを一つ置く（`src/qata_server/apps/<アプリ>.json`）。起動のしかた・ウィンドウ・スクショの範囲・部品を持つ。
  - 部品には、アクションごとに変換の規則を `{"kind": ..., ...}` で書く。部品の辞書の `actions` は、規則のあるアクションから作る（二か所に書かず、食い違わないようにする）。
  - 規則の種類（kind）ごとの変換を `conversion.py` の `CONVERTERS` に持つ。いまは汎用の `key`（キーを押す）・`tap`（座標をタップする）・`uia`（UI Automation で読み、正規表現で値を取り出す）の三つ。内製のツールは、ここに種類を足して広げる。
  - 読み込むときに、規則の書き方と、変換の結果が runner への命令の契約（`runner-command.schema.json`）に合うかを確かめる。合わなければ server を立ち上げない。
- 電卓の座標は仮の値（親の例と同じ）。本物の runner に置き換えるときに測り直す。
- 親の契約は、実行のときにも `../qata/contracts/` から読む（S1 の判定のため。S2 と同じく、次の周回で直す）。そのため jsonschema を、開発のときだけでなく実行のときの依存にした。

## S1. 型の生成のしかた

- 決めた人：AI　レビュー：済
- datamodel-code-generator で、`../qata/contracts/schemas/` から `src/qata_server/contracts/` に生成する。手順は `scripts/generate_contracts.py`。
- 生成は、いつもリポジトリの外の一時フォルダで行ってから写す。生成先の ruff の設定で整形が変わり、「生成し直しても同じ」の検査が揺れないようにするため。生成物は ruff の対象から外す。
- 生成した型は、JSON Schema の `contains`（確認事項を一つは含む）や `if`/`then` を表せない。そのため、外から来るデータ（AI・web からのテストケース、runner の結果、部品の辞書のファイル）は、まず jsonschema で親の JSON Schema に照らして判定し、合格したものだけを型に読み込む。型は判定ではなく、コードで扱うための読み込みに使う（タスクの 1 で作る）。

## S2. 契約の検査は pytest-bdd で書く

- 決めた人：AI　レビュー：済（親を相対のパスで読むのは、次の周回で直す。親の ideas.md）
- `tests/contracts/contracts.feature` に日本語の Gherkin で観点を書く。はじく例は、契約の例の一か所を変える・消す形で表に並べ、「なぜ」の列を付ける。
- 親の契約は、作業フォルダで隣に並べた `../qata/` から読む。
