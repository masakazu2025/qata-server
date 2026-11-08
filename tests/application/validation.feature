# language: ja
機能: テストケースの検証と部品の辞書
  AI や web から来たテストケースを、二段で検証する：形式（親の JSON Schema）と、部品の辞書との照合。
  問題は、場所（JSON Pointer）と code で返す。

  シナリオ: 登録されたアプリと部品の辞書が見える
    ならば アプリの一覧に "calculator" の "電卓" がある
    かつ "calculator" の部品の辞書が契約 "part-dictionary.schema.json" に通る

  シナリオ: ないアプリの部品の辞書は見つからない
    ならば "notepad" の部品の辞書は見つからない

  シナリオ: 契約の例のテストケースが検証を通る
    前提 契約の例 "testcase.add.json" のテストケース
    もし 検証する
    ならば 検証を通る

  シナリオアウトライン: 間違ったテストケースをはじく
    前提 契約の例 "testcase.add.json" のテストケース
    もし "<場所>" を <値> に変える
    かつ 検証する
    ならば "<はじく場所>" が "<code>" ではじかれる

    例:
      | 場所          | 値                                                    | はじく場所     | code                 | なぜ                       |
      | /steps        | []                                                    | /steps         | schema               | ステップが一つもない       |
      | /steps/0/type | "double_click"                                        | /steps/0/type  | schema               | ないアクション             |
      | /steps/0      | {"type": "press_key"}                                 | /steps/0       | schema               | 部品がない                 |
      | /steps/4      | {"type": "expect_text", "part": "表示", "expected": 3} | /steps/4/expected | schema            | 期待する値が文字でない     |
      | /app_id       | "notepad"                                             | /app_id        | unknown_app          | 部品の辞書がないアプリ     |
      | /steps/0/part | "9"                                                   | /steps/0/part  | unknown_part         | 辞書にない部品             |
      | /steps/0/part | "表示"                                                | /steps/0/type  | action_not_supported | 表示は押せない             |
      | /steps/1/part | "クリア"                                              | /steps/1/type  | action_not_supported | クリアはタップできない     |
      | /steps/4/part | "1"                                                   | /steps/4/type  | action_not_supported | 数字のボタンは読めない     |

  シナリオ: 辞書との照合の問題は、すべてまとめて返す
    前提 契約の例 "testcase.add.json" のテストケース
    もし "/steps/0/part" を "9" に変える
    かつ "/steps/2/part" を "表示" に変える
    かつ 検証する
    ならば 問題が 2 つ返る
