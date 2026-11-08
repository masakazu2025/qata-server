# language: ja
機能: REST の入口
  web が使う REST の API。形の正は親の openapi.yaml で、FastAPI が出す OpenAPI がそれと合うことを確かめる。
  runner は偽物（決まった結果を返す）を使う。

  シナリオ: 道・引数・応答のコードと media type が openapi.yaml と同じ
    ならば FastAPI が出す OpenAPI の道ごとの operationId・引数・本文・応答のコードと media type が、openapi.yaml と同じ

  シナリオ: 本文と応答の形が、契約から生成した型と同じ
    ならば openapi.yaml が契約を指すところで、FastAPI が出す OpenAPI は、その契約から生成した型を指す
    かつ FastAPI が出す OpenAPI の型の中身は、生成した型の JSON Schema と同じ

  シナリオ: 登録して、実行して、結果とスクショを見る
    もし 人の確認が要らない例を "/testcases" に POST する
    ならば 応答は 201 で、本文が契約 "server.schema.json#/$defs/testcase_record" に通る
    もし 登録したテストケースを実行する
    ならば 応答は 201 で、本文が契約 "server.schema.json#/$defs/run" に通る
    かつ 実行の結果は "passed"
    かつ 最初のステップのスクショが PNG で取れる
    かつ "/runs" の一覧は 1 件で、どれも契約 "server.schema.json#/$defs/run" に通る
    かつ "/testcases" の一覧は 1 件で、どれも契約 "server.schema.json#/$defs/testcase_record" に通る
    かつ "/apps" の一覧は 1 件で、どれも契約 "server.schema.json#/$defs/app_summary" に通る

  シナリオ: 部品の辞書を返す
    もし "/apps/calculator/parts" を GET する
    ならば 応答は 200 で、本文が契約 "part-dictionary.schema.json" に通る

  シナリオ: 検証は、問題があっても 200 で返す
    もし 部品を "存在しない部品" にした例を "/testcases/validate" に POST する
    ならば 応答は 200 で、本文が契約 "server.schema.json#/$defs/validation_result" に通る
    かつ 問題の code は "unknown_part"

  シナリオ: 検証を通らないものは、422 で返して登録しない
    もし 部品を "存在しない部品" にした例を "/testcases" に POST する
    ならば 応答は 422 で、本文が契約 "server.schema.json#/$defs/validation_result" に通る
    かつ 問題の code は "unknown_part"
    かつ "/testcases" の一覧は 0 件で、どれも契約 "server.schema.json#/$defs/testcase_record" に通る

  シナリオ: JSON として読めない本文は、形式の誤りとして返す
    もし JSON でない本文を "/testcases" に POST する
    ならば 応答は 422 で、本文が契約 "server.schema.json#/$defs/validation_result" に通る
    かつ 問題の code は "schema"

  シナリオアウトライン: ないものは 404 で返す
    もし "<道>" を GET する
    ならば 応答は 404 で、本文が契約 "server.schema.json#/$defs/error_response" に通る
    かつ エラーの code は "not_found"

    例:
      | 道                                                  |
      | /apps/notepad/parts                                 |
      | /testcases/tc_00000000000000000000000000000000      |
      | /runs/run_00000000000000000000000000000000          |
      | /screenshots/ss_00000000000000000000000000000000    |
      | /screenshots/..%2F..%2Fqata.sqlite3                 |

  シナリオ: 人の確認待ちのものは、承認するまで 409 で実行しない
    もし 人の確認が要る例を "/testcases" に POST する
    かつ 登録したテストケースを実行する
    ならば 応答は 409 で、本文が契約 "server.schema.json#/$defs/error_response" に通る
    かつ エラーの code は "review_pending"
    もし 登録したテストケースを承認する
    ならば 応答は 200 で、本文が契約 "server.schema.json#/$defs/testcase_record" に通る
    もし 登録したテストケースを実行する
    ならば 応答は 201 で、本文が契約 "server.schema.json#/$defs/run" に通る

  シナリオ: 確認の要らないものを承認しようとすると 409
    もし 人の確認が要らない例を "/testcases" に POST する
    かつ 登録したテストケースを承認する
    ならば 応答は 409 で、本文が契約 "server.schema.json#/$defs/error_response" に通る
    かつ エラーの code は "review_not_required"

  シナリオ: runner に届かなければ 502
    前提 runner に届かない
    もし 人の確認が要らない例を "/testcases" に POST する
    かつ 登録したテストケースを実行する
    ならば 応答は 502 で、本文が契約 "server.schema.json#/$defs/error_response" に通る
    かつ エラーの code は "runner_unavailable"

  シナリオ: 消したものは 404 になる
    もし 人の確認が要らない例を "/testcases" に POST する
    かつ 登録したテストケースを消す
    ならば 応答は 204 で、本文はない
    もし 登録したテストケースを消す
    ならば 応答は 404 で、本文が契約 "server.schema.json#/$defs/error_response" に通る
