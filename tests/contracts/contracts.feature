# language: ja
機能: 親の契約の検査
  親の契約（../qata/contracts）が壊れていないことと、
  この server が契約から生成した型が契約と合っていることを確かめる（親の decisions.md の D22）。

  シナリオ: JSON Schema が draft 2020-12 の形式に合う
    ならば すべての JSON Schema が draft 2020-12 の形式に合う

  シナリオ: ファイルの間の $ref が解決できる
    ならば JSON Schema・openapi.yaml・mcp-tools.json のすべての $ref が解決できる

  シナリオアウトライン: 契約の例が形式に通る
    前提 契約の例 "<ファイル>"
    ならば 契約 "<契約>" に通る

    例:
      | ファイル              | 契約                                      |
      | testcase.add.json     | testcase.schema.json                      |
      | calculator.parts.json | part-dictionary.schema.json               |
      | runner-command.json   | runner-command.schema.json                |
      | runner-result.json    | runner-result.schema.json                 |
      | testcase-record.json  | server.schema.json#/$defs/testcase_record |
      | run.json              | server.schema.json#/$defs/run             |

  シナリオアウトライン: 間違った値の例をはじく
    前提 契約の例 "<ファイル>"
    もし "<場所>" を <値> に変える
    ならば 契約 "<契約>" ではじかれる

    例:
      | ファイル              | 場所                   | 値                                   | 契約                                      | なぜ                   |
      | testcase.add.json     | /steps                 | []                                   | testcase.schema.json                      | ステップが一つもない   |
      | testcase.add.json     | /steps                 | [{"type": "press_key", "part": "1"}] | testcase.schema.json                      | 確認事項がない         |
      | testcase.add.json     | /steps/0/type          | "double_click"                       | testcase.schema.json                      | ないアクション         |
      | testcase.add.json     | /app_id                | "Calculator"                         | testcase.schema.json                      | app_id に大文字        |
      | testcase.add.json     | /extra                 | 1                                    | testcase.schema.json                      | 契約にない項目         |
      | calculator.parts.json | /parts                 | {}                                   | part-dictionary.schema.json               | 部品が一つもない       |
      | calculator.parts.json | /parts/表示/actions    | ["read"]                             | part-dictionary.schema.json               | ないアクション         |
      | runner-command.json   | /steps/0/key           | "Ctrl+C"                             | runner-command.schema.json                | 同時押しは扱わない     |
      | runner-command.json   | /steps/4/source/method | "ocr"                                | runner-command.schema.json                | まだない読み方         |
      | runner-command.json   | /screenshot/scope      | "desktop"                            | runner-command.schema.json                | ないスクショの範囲     |
      | runner-result.json    | /status                | "aborted"                            | runner-result.schema.json                 | 止めたのに理由がない   |
      | run.json              | /status                | "error"                              | server.schema.json#/$defs/run             | エラーなのに理由がない |
      | run.json              | /started_at            | "きのう"                             | server.schema.json#/$defs/run             | 日時の形でない         |
      | testcase-record.json  | /review_status         | "rejected"                           | server.schema.json#/$defs/testcase_record | ない確認の状態         |

  シナリオアウトライン: 要る項目がない例をはじく
    前提 契約の例 "<ファイル>"
    もし "<場所>" を消す
    ならば 契約 "<契約>" ではじかれる

    例:
      | ファイル           | 場所                | 契約                      | なぜ                           |
      | testcase.add.json  | /needs_review       | testcase.schema.json      | 人の確認の要否がない           |
      | testcase.add.json  | /steps/4/expected   | testcase.schema.json      | 確認事項に期待する値がない     |
      | runner-result.json | /steps/0/screenshot | runner-result.schema.json | 済んだステップにスクショがない |

  シナリオアウトライン: 生成した型で契約の例が読める
    前提 契約の例 "<ファイル>"
    ならば 生成した型 "<型>" で読める

    例:
      | ファイル              | 型                                    |
      | testcase.add.json     | testcase_schema.Testcase              |
      | calculator.parts.json | part_dictionary_schema.PartDictionary |
      | runner-command.json   | runner_command_schema.RunnerCommand   |
      | runner-result.json    | runner_result_schema.RunnerResult     |
      | testcase-record.json  | server_schema.TestcaseRecord          |
      | run.json              | server_schema.Run                     |

  シナリオ: 生成した型が契約と一致する
    ならば 契約から生成し直した型が、コミットした型と同じ
