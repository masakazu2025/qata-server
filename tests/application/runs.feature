# language: ja
機能: テストケースの実行
  変換の枠で部品の名前を基本の操作に変えて runner に送り、返ってきた結果から合否を決めて保存する。
  runner は偽物（決まった結果を返す）を使う。

  背景:
    前提 人の確認が要らないテストケースを登録した

  シナリオ: 表示が期待する値なら、通る
    前提 runner は表示に "表示は 3 です" を返す
    もし 実行する
    ならば 実行の結果は "passed"
    かつ ステップの結果は "passed,passed,passed,passed,passed"
    かつ 確認事項で取り出した値は "3"
    かつ runner への命令が契約 "runner-command.schema.json" に通る
    かつ runner への命令は親の例 "runner-command.json" と、run_id のほかは同じ
    かつ 実行の結果が契約 "server.schema.json#/$defs/run" に通る
    かつ どのステップにもスクショがあり、runner がそのステップで撮った PNG が取れる

  シナリオ: 表示が期待する値と違えば、落ちる
    前提 runner は表示に "表示は 4 です" を返す
    もし 実行する
    ならば 実行の結果は "failed"
    かつ ステップの結果は "passed,passed,passed,passed,failed"
    かつ 確認事項で取り出した値は "4"

  シナリオ: 表示から値を取り出せなければ、落ちる
    前提 runner は表示に "3" を返す
    もし 実行する
    ならば 実行の結果は "failed"
    かつ ステップの結果は "passed,passed,passed,passed,failed"

  シナリオ: runner が途中で止まったら、残りは実行しない
    # 命令の頭に前準備が 2 つあるので、テストケースの 3 番目は命令の 5 番目
    前提 runner は命令の 5 番目のステップで止まる
    もし 実行する
    ならば 実行の結果は "error"
    かつ ステップの結果は "passed,passed,error,skipped,skipped"
    かつ 実行の結果が契約 "server.schema.json#/$defs/run" に通る

  シナリオ: runner が前準備で止まったら、どのステップも実行しない
    前提 runner は命令の 2 番目のステップで止まる
    もし 実行する
    ならば 実行の結果は "error"
    かつ ステップの結果は "skipped,skipped,skipped,skipped,skipped"
    かつ 実行のエラーの説明は "前準備で止まった" で始まる
    かつ 実行の結果が契約 "server.schema.json#/$defs/run" に通る

  シナリオ: runner がアプリを起動できなければ、どのステップも実行しない
    前提 runner はアプリを起動できない
    もし 実行する
    ならば 実行の結果は "error"
    かつ ステップの結果は "skipped,skipped,skipped,skipped,skipped"
    かつ 実行の結果が契約 "server.schema.json#/$defs/run" に通る

  シナリオアウトライン: runner の結果が壊れていれば、合否を決めずに壊れた結果として残す
    # 命令は前準備 2 つとテストケース 5 つ。runner の決まり：エラーが起きたらそこで止めて aborted
    前提 runner は結果を "<壊し方>" にして返す
    もし 実行する
    ならば 実行の結果は "error"
    かつ 実行のエラーは "invalid_runner_result"
    かつ 実行のエラーの説明に "<理由>" とある
    かつ ステップの結果は "skipped,skipped,skipped,skipped,skipped"
    かつ 実行の結果が契約 "server.schema.json#/$defs/run" に通る
    かつ 実行の結果の一覧は 1 件

    例:
      | 壊し方                                | 理由                                   |
      | 決めた形と違う                        | /status                                |
      | スクショが Base64 でない              | /steps/0/screenshot：Base64 として読めない |
      | スクショに ASCII でない文字がある     | /steps/0/screenshot：Base64 として読めない |
      | 実行の番号が命令と違う                | run_id が命令と違う                    |
      | ステップの番号が飛ぶ                  | 命令の順になっていない                 |
      | ステップが命令より多い                | 命令の順になっていない                 |
      | completed なのにステップが足りない    | ステップが 6 個しかない                |
      | completed なのに最後のステップが error | completed なのに、error のステップがある |
      | 前準備が error なのに completed       | error のあとにもステップがある         |
      | error のあとにもステップがある        | error のあとにもステップがある         |

  シナリオ: 登録のあとで部品の辞書から部品が消えたら、実行を断って結果を残さない
    もし 部品の辞書から部品 "等号" を外す
    ならば 実行すると "testcase_out_of_date" で断られる
    かつ 実行の結果の一覧は 0 件
    かつ runner に命令を送っていない

  シナリオ: runner に届かなければ、実行の結果を残さない
    前提 runner に届かない
    ならば 実行すると "runner_unavailable" で断られる
    かつ 実行の結果の一覧は 0 件

  シナリオ: runner がほかの実行の最中なら、実行の結果を残さない
    前提 runner はほかの実行の最中
    ならば 実行すると "runner_busy" で断られる
    かつ 実行の結果の一覧は 0 件

  シナリオ: 人の確認待ちのものは実行できない
    前提 人の確認が要るテストケースを登録した
    ならば 実行すると "review_pending" で断られる

  シナリオ: 承認したものは実行できる
    前提 人の確認が要るテストケースを登録した
    もし 承認する
    かつ 実行する
    ならば 実行の結果は "passed"

  シナリオ: 実行の結果の一覧は新しい順で、テストケースで絞れる
    前提 実行した
    かつ 実行した
    ならば 実行の結果の一覧は 2 件で、あとに実行したものが先
    かつ 実行の結果を ID で取れる
