# language: ja
機能: MCP の入口
  AI が使う MCP の道具。形の正は親の mcp-tools.json で、server が出す道具がそれと合うことを確かめる。
  MCP のクライアントは同じプロセスの中でつなぐ。runner は偽物（決まった結果を返す）を使う。
  クライアントは、道具の結果（structuredContent）が、server が出す outputSchema に合うかを自分でも確かめる。

  シナリオ: qata-server-mcp を立ち上げると、stdio で道具を出す
    ならば qata-server-mcp を立ち上げてつなぐと、mcp-tools.json の道具がすべて出る

  シナリオ: 道具の名前と説明が mcp-tools.json と同じ
    ならば 道具の一覧の名前と説明は、mcp-tools.json と同じ

  シナリオ: 道具の形は、それだけで読める
    ならば どの道具の inputSchema と outputSchema にも $ref が残っていない
    かつ どの道具の inputSchema と outputSchema も、JSON Schema として正しい

  シナリオアウトライン: 展開した形は、契約と同じものを通し、同じものをはじく
    ならば 道具 "<道具>" の inputSchema で、<テストケース>テストケースは契約と同じく <判定>

    例:
      | 道具              | テストケース     | 判定     |
      | validate_testcase | 契約の例の       | 通る     |
      | register_testcase | 契約の例の       | 通る     |
      | register_testcase | 確認事項のない   | はじかれる |
      | register_testcase | ステップのない   | はじかれる |

  シナリオ: 登録して、実行して、結果を見る
    もし 道具 "list_apps" を呼ぶ
    ならば 結果は契約の outputSchema に通る
    もし 道具 "get_part_dictionary" を app_id "calculator" で呼ぶ
    ならば 結果は契約の outputSchema に通る
    もし 人の確認が要らない例で、道具 "validate_testcase" を呼ぶ
    ならば 結果は契約の outputSchema に通る
    かつ 結果の "valid" は true
    もし 人の確認が要らない例で、道具 "register_testcase" を呼ぶ
    ならば 結果は契約の outputSchema に通る
    かつ 結果の "registered" は true
    もし 登録したテストケースで、道具 "run_testcase" を呼ぶ
    ならば 結果は契約の outputSchema に通る
    かつ 結果の "status" は "passed"
    もし 実行の結果で、道具 "get_run" を呼ぶ
    ならば 結果は契約の outputSchema に通る
    もし 道具 "list_testcases" を app_id "calculator" で呼ぶ
    ならば 結果は契約の outputSchema に通る
    かつ 結果の "testcases" は 1 件

  シナリオ: 検証を通らないものは、登録せずに問題を返す
    もし 部品を "存在しない部品" にした例で、道具 "register_testcase" を呼ぶ
    ならば 結果は契約の outputSchema に通る
    かつ 結果の "registered" は false
    かつ 問題の code は "unknown_part"
    もし 道具 "list_testcases" を app_id "calculator" で呼ぶ
    ならば 結果の "testcases" は 0 件

  シナリオ: 人の確認待ちのものは実行しない
    もし 人の確認が要る例で、道具 "register_testcase" を呼ぶ
    かつ 登録したテストケースで、道具 "run_testcase" を呼ぶ
    ならば 道具はエラーを返し、code は "review_pending"

  シナリオ: runner に届かなければエラー
    前提 runner に届かない
    もし 人の確認が要らない例で、道具 "register_testcase" を呼ぶ
    かつ 登録したテストケースで、道具 "run_testcase" を呼ぶ
    ならば 道具はエラーを返し、code は "runner_unavailable"

  シナリオアウトライン: 呼び方の誤りはエラーで返す
    もし 道具 "<道具>" を引数 <引数> で呼ぶ
    ならば 道具はエラーを返し、code は "<code>"

    例:
      | 道具                | 引数                                           | code              |
      | get_part_dictionary | {"app_id": "notepad"}                          | not_found         |
      | get_run             | {"run_id": "run_00000000000000000000000000000000"} | not_found     |
      | get_run             | {}                                             | invalid_arguments |
      | list_apps           | {"extra": 1}                                   | invalid_arguments |
      | delete_everything   | {}                                             | unknown_tool      |
