# language: ja
機能: 読む契約の版
  server は、親のタグ contracts-v<版> の contracts/ を qata-contracts/ に写して持ち、その版だけを読む（親の decisions.md の D54）。
  写しを手で直していないことと、親に新しい版が出たら知らせることを確かめる。

  シナリオアウトライン: 親のタグに、読む版より新しい版があれば知らせる
    前提 読む版 "<読む版>"
    かつ 親のタグ "<タグ>"
    ならば 知らせる新しい版は "<新しい版>"

    例:
      | 読む版 | タグ                                        | 新しい版 |
      | 1.0.0  | contracts-v1.0.0                            | なし     |
      | 1.0.0  | contracts-v1.0.0,contracts-v1.1.0           | 1.1.0    |
      | 1.9.0  | contracts-v1.9.0,contracts-v1.10.0          | 1.10.0   |
      | 1.10.0 | contracts-v1.9.0,contracts-v1.10.0          | なし     |
      | 2.0.0  | contracts-v1.5.0                            | なし     |
      | 1.0.0  | contracts-v1.0.0,contracts-v2.0.0^{},other  | 2.0.0    |
      | 1.0.0  |                                             | なし     |

  シナリオアウトライン: CI に出す一行は、古いときだけ警告の形にする
    前提 読む版 "<読む版>"
    かつ 親のタグ "<タグ>"
    ならば CI に出す一行は<形>

    例:
      | 読む版 | タグ                              | 形           |
      | 1.0.0  | contracts-v1.0.0,contracts-v1.1.0 | 警告         |
      | 1.0.0  | contracts-v1.0.0                  | 警告ではない |

  シナリオアウトライン: タグが取れなくても、警告だけで終わる
    前提 タグを取ると "<誤り>" になる
    もし 古い版の警告を出す
    ならば 出した一行は警告

    例:
      | 誤り               |
      | OSError            |
      | CalledProcessError |
      | TimeoutExpired     |

  シナリオ: 写しが、その版のタグの中身と同じなら違いはない
    前提 写しと同じ中身の、親のタグの tarball
    ならば 写しとの違いはない

  シナリオ: 写しを手で直すと、違いとして見つかる
    前提 写しと同じ中身の、親のタグの tarball
    もし 写しの "VERSION" を書き換える
    ならば 写しとの違いに "VERSION" がある

  シナリオアウトライン: 写しのファイルを足したり消したりすると、違いとして見つかる
    前提 写しと同じ中身の、親のタグの tarball
    もし 写しの "<ファイル>" を<する>
    ならば 写しとの違いに "<ファイル>" がある

    例:
      | ファイル                   | する |
      | schemas/extra.schema.json  | 足す |
      | schemas/common.schema.json | 消す |

  シナリオ: tarball からは contracts/ の中だけを写す
    前提 一段目のフォルダに "README.md" と "contracts/VERSION" がある tarball
    ならば 写すファイルは "VERSION" だけ

  シナリオ: contracts/ のない tarball は写さない
    前提 一段目のフォルダに "README.md" がある tarball
    ならば 写すと、写しを残したまま失敗する

  シナリオアウトライン: 使う契約が欠けていれば、立ち上げで落ちる
    前提 写しから "<ファイル>" を除く
    ならば server の組み立てが失敗する

    例:
      | ファイル                            | なぜ                               |
      | schemas/testcase.schema.json        | テストケースの判定に使う           |
      | schemas/runner-result.schema.json   | runner の結果の判定に使う          |
      | schemas/runner-command.schema.json  | アプリの設定の変換の結果の判定に使う |
      | schemas/server.schema.json          | MCP の道具の形が指す               |
      | schemas/common.schema.json          | ほかの契約が $ref で指す           |
      | mcp-tools.json                      | MCP の道具の形                     |

  シナリオ: 使う契約が指す先の、そのまた先が欠けていても、立ち上げで落ちる
    # testcase の tags は common の tags を指し、その tags が common の tag を指す
    前提 写しの "schemas/common.schema.json" から定義 "tag" を除く
    ならば server の組み立てが失敗する

  シナリオ: 契約がそろっていれば、組み立ては通る
    ならば server を組み立てられる
