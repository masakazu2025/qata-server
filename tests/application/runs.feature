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
    かつ どのステップにもスクショがあり、runner が撮った PNG が取れる

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
    前提 runner は 3 番目のステップで止まる
    もし 実行する
    ならば 実行の結果は "error"
    かつ ステップの結果は "passed,passed,error,skipped,skipped"
    かつ 実行の結果が契約 "server.schema.json#/$defs/run" に通る

  シナリオ: runner がアプリを起動できなければ、どのステップも実行しない
    前提 runner はアプリを起動できない
    もし 実行する
    ならば 実行の結果は "error"
    かつ ステップの結果は "skipped,skipped,skipped,skipped,skipped"
    かつ 実行の結果が契約 "server.schema.json#/$defs/run" に通る

  シナリオ: runner の結果が契約に合わなければ、エラーにする
    前提 runner は契約に合わない結果を返す
    もし 実行する
    ならば 実行の結果は "error"
    かつ 実行のエラーは "invalid_runner_result"
    かつ 実行の結果が契約 "server.schema.json#/$defs/run" に通る

  シナリオ: runner に届かなければ、実行の結果を残さない
    前提 runner に届かない
    ならば 実行すると "runner_unavailable" で断られる
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
