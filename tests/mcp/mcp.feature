# language: ja
機能: MCP の入口
  AI が使う MCP の道具。形の正は親の mcp-tools.json で、server が出す道具がそれと合うことを確かめる。
  MCP は REST と同じプロセスの /mcp で、Streamable HTTP で答える。ほかのシナリオでは、MCP のクライアントは同じプロセスの中でつなぐ。runner は偽物（決まった結果を返す）を使う。
  クライアントは、道具の結果（structuredContent）が、server が出す outputSchema に合うかを自分でも確かめる。

  シナリオ: 一つのプロセスで、REST と MCP（Streamable HTTP）の両方に答える
    ならば qata-server を立ち上げると、同じプロセスが REST と MCP の両方に答える

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

  シナリオアウトライン: タグで絞った一覧は、REST と MCP で同じものを返す
    前提 タグ ["機能:加算", "設計書:電卓の基本操作"] の例を、道具 register_testcase で登録した
    かつ タグ ["機能:加算"] の例を、道具 register_testcase で登録した
    かつ タグのない例を、道具 register_testcase で登録した
    もし 道具 list_testcases を tags <絞り込み> で呼ぶ
    ならば 結果は契約の outputSchema に通る
    かつ REST の /testcases を tag <絞り込み> で読むと、同じ <件数> 件を返す

    例:
      | 絞り込み                               | 件数 | なぜ                             |
      | ["機能:加算"]                          | 2    | 一つのタグ                       |
      | ["機能:加算", "設計書:電卓の基本操作"] | 1    | 全部持つものだけ（AND）          |
      | ["機能:加算", "機能:加算"]             | 2    | 重なりは一つと見なす             |
      | ["機能：加算"]                         | 0    | 全角の「：」は半角の絞り込みに出ない |
      | []                                     | 3    | 空の並びは、指定しないときと同じ |

  シナリオ: MCP の空の tags は、指定しないときと同じ件数で、タグのない記録に tags は出ない
    前提 タグ ["機能:加算"] の例を、道具 register_testcase で登録した
    かつ タグのない例を、道具 register_testcase で登録した
    もし 道具 list_testcases を tags [] で呼ぶ
    ならば REST の /testcases を引数なしで読むと、同じ 2 件を返す
    かつ タグのない記録には、REST でも MCP でも tags が出ない
    もし 道具 "list_testcases" を呼ぶ
    ならば 結果の "testcases" は 2 件

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

  シナリオ: runner がほかの実行の最中ならエラーで、実行の結果を残さない
    前提 runner はほかの実行の最中
    もし 人の確認が要らない例で、道具 "register_testcase" を呼ぶ
    かつ 登録したテストケースで、道具 "run_testcase" を呼ぶ
    ならば 道具はエラーを返し、code は "runner_busy"
    かつ 実行の結果は残っていない

  シナリオ: 想定していない誤りも、契約の形のエラーで返す
    前提 server の中で想定していない誤りが起きる
    もし 人の確認が要らない例で、道具 "register_testcase" を呼ぶ
    かつ 登録したテストケースで、道具 "run_testcase" を呼ぶ
    ならば 道具はエラーを返し、code は "internal_error"

  シナリオアウトライン: 呼び方の誤りはエラーで返す
    もし 道具 "<道具>" を引数 <引数> で呼ぶ
    ならば 道具はエラーを返し、code は "<code>"

    例:
      | 道具                | 引数                                           | code              |
      | get_part_dictionary | {"app_id": "notepad"}                          | not_found         |
      | get_run             | {"run_id": "run_00000000000000000000000000000000"} | not_found     |
      | get_run             | {}                                             | invalid_arguments |
      | list_apps           | {"extra": 1}                                   | invalid_arguments |
      | list_testcases      | {"tags": [""]}                                 | invalid_arguments |
      | list_testcases      | {"tags": "機能:加算"}                          | invalid_arguments |
      | delete_everything   | {}                                             | unknown_tool      |
