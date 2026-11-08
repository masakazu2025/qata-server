# 作業の記録

セッションの終わりに、やったことを一行で残します。新しいものを上に足します。

- 2026-11-08：MCP の入口を作った。親の mcp-tools.json の道具を $ref を展開して stdio で出し、名前・説明・形・結果が契約と合うことを関門にした（S7）。
- 2026-11-08：application 層を REST（FastAPI）で出し、OpenAPI が openapi.yaml と合うこと・依存の向き（import-linter）を関門にした。本物の runner への HTTP の道具を置いた（S6）。
- 2026-11-08：application 層（検証・登録・実行・変換の枠・保存）を作り、偽の runner で pytest-bdd の関門にした（S3〜S5）。
- 2026-11-08：リポジトリを作り、契約の検査（例・はじく例・$ref・型の生成し直し）を pytest-bdd で関門にした。
