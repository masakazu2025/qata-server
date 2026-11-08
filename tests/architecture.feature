# language: ja
機能: 依存の向き
  組み立て（main）→ 入口（rest）・runner への道具（runner_http）→ application → 契約の型、の向きにだけ依存する。
  決まりは pyproject.toml の [tool.importlinter] に書く。

  シナリオ: 依存の向きが決まりに合う
    ならば import-linter の決まりがすべて守られている
