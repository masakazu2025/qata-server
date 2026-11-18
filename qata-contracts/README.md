# 契約

部品の間でやり取りするデータの形です。**正はここだけ。** 部品はここから型を生成し、生成物もコミットします（[repos-and-contracts.md](https://github.com/masakazu2025/qata/blob/main/.claude/rules/qata/repos-and-contracts.md)）。

部品のリポジトリには、この `contracts/` の写しがあります。写しの中から親の文書を指すリンクは、親のリポジトリの URL にしています。

PoC の間は仮に確定しています。変えるときは [decisions.md](https://github.com/masakazu2025/qata/blob/main/docs/decisions.md) に残します。

## 版

- いまの版は [VERSION](VERSION)、版ごとの変更は [CHANGELOG.md](CHANGELOG.md) にあります。
- 契約を変える pull request では、同じ pull request の中で版を上げ、変更の記録を書きます。マージしたら `contracts-v<版>` のタグを付けます。
- 部品は、タグからその版の契約を自分のリポジトリに写して読みます。上げ方と持ち方は [repos-and-contracts.md](https://github.com/masakazu2025/qata/blob/main/.claude/rules/qata/repos-and-contracts.md) の「契約の版」にあります。

## ファイル

| 契約 | ファイル | 使う部品 |
| --- | --- | --- |
| テストケースの形式 | [schemas/testcase.schema.json](schemas/testcase.schema.json) | server・web・AI（MCP） |
| 画面の部品の辞書の形式 | [schemas/part-dictionary.schema.json](schemas/part-dictionary.schema.json) | server・AI（MCP） |
| runner への命令 | [schemas/runner-command.schema.json](schemas/runner-command.schema.json) | server → runner |
| runner からの結果 | [schemas/runner-result.schema.json](schemas/runner-result.schema.json) | runner → server |
| server の API | [openapi.yaml](openapi.yaml)（形は [schemas/server.schema.json](schemas/server.schema.json)） | web → server |
| server の MCP の道具 | [mcp-tools.json](mcp-tools.json)（形は [schemas/server.schema.json](schemas/server.schema.json)） | AI → server |
| 共通の部品 | [schemas/common.schema.json](schemas/common.schema.json) | すべて |

- JSON Schema は draft 2020-12。ファイルの間は相対パスの `$ref` でつなぐ。
- 例は [examples/](examples/) に置く（電卓で 1 + 2 = 3 を確かめる流れ）。座標は仮の値。
- 部品の辞書の契約は、AI と web に見せる部分（名前・説明・使えるアクション）だけ。名前を具体的な操作に変える規則は server の変換の枠に置く（[D14](https://github.com/masakazu2025/qata/blob/main/docs/decisions.md)）。

## データの流れ

```
AI ──MCP──→ server：testcase（部品の名前で書く）
                │ 検証：形式（testcase.schema.json）＋ 部品の辞書との照合（部品があり、そのアクションに対応しているか）
                │ 実行：変換の枠で、部品の名前をキー・座標・AutomationId に変える
                ▼
            runner：runner-command → 操作・スクショ → runner-result
                │
                ▼
            server：読んだ文字から値を取り出し（変換の規則）、expected と比べて run を作る
                │   スクショは PNG のファイルに保存し、screenshot_id で指す
                ▼
web ──REST──→ server：testcase_record・run・スクショ
```

## 部品ごとの約束

### runner

- 入口は `POST /runs`（本文 runner-command、応答 runner-result）。実行が終わるまで待って返す。
- 一度に一つの実行しか受け付けない（1 台の PC の画面で本物のアプリを動かすため）。実行中に次の命令が来たら、待たずに 409 で断り、本文は共通の部品 `error`（`code` は `runner_busy`）にする。
- 実行のたびにアプリを起動し直し、命令に大きさがあればウィンドウをその大きさにそろえてから始める。
- ステップごとにスクショを撮る。範囲は命令の `screenshot.scope`（ウィンドウだけか、すべての画面か）。
- 判定はしない。読んだ文字をそのまま返す。文字の読み方は `read_text` の `source.method` で選ぶ（いまは `uia` だけ）。

### server

- 検証は二段：形式（JSON Schema）と、部品の辞書との照合。問題は `validation_error` の `code` で返す。
  - 部品がステップのアクションに対応していなければ（`actions` になければ）、`action_not_supported` ではじく。
- 名前を具体的な操作に変える規則は、差し込める枠にする。汎用の規則（キー、座標のタップ、UI Automation で読む）は server に置き、それ以外は内製のツールで足せるようにする。
- スクショの範囲は、アプリごとの設定で決める。
- テストケースの一覧は、`app_id` とタグで絞り込める。タグは、指定したものを全部持つもの（AND）を返す。一致は文字の完全な一致で、全角と半角・大文字と小文字・前後の空白を整えない（慣習の区切りは半角の「:」）。REST では `tag` を一つごとに繰り返し、MCP の `list_testcases` では `tags` に並べる。同じタグの重なりは一つと見なし、指定しないとき（MCP では空の並びも）は、タグで絞り込まない。
- タグはテストケースの形式の中に持つので、登録したテストケースの記録（`testcase_record`）にも、そのまま出る。登録で `tags` を省いたものは、記録でも省く（空の並びを補わない）。登録したあとに直すことは、まだできない（登録し直す）。
- `needs_review` が true のテストケースは `pending` で登録し、承認されるまで実行しない。false なら `not_required`。
- 確認事項が合わなくても、ステップは最後まで実行する（runner はまとめて実行するため）。runner が止まったら、残りは `skipped`。
- 想定していない誤りが起きても、REST は 500、MCP は isError の結果で、どちらも error_response の形（`code` は `internal_error`）で返す。理由が分かるように、例外の種類を `message` に入れる。
- FastAPI が出す OpenAPI が [openapi.yaml](openapi.yaml) と合うこと、MCP で出す道具が [mcp-tools.json](mcp-tools.json) と合うことを、テストで確かめる。

### web

- [openapi.yaml](openapi.yaml) から型を生成する。
