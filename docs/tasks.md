# タスク

これからやることを、優先順に並べます。上から順にやります。全体の段取りは親の `../qata/docs/tasks.md` にあります。

- 終わったタスクは消し、やったことは [log.md](log.md) に書きます。

## 次にやること（優先順）

1. **application 層を REST で出す**　担当：AI
   - FastAPI が出す OpenAPI が親の `openapi.yaml` と合うことをテストで確かめる。
   - 本物の runner に命令を送る道具（HTTP）を置く。
   - 層ができるので、import-linter で依存の向きを関門にする。
   - application 層の例外（`NotFound`・`Conflict`・`RunnerUnavailable`）を、openapi.yaml の 404・409・502 に変える（S5）。
2. **MCP の道具を出す**　担当：AI
   - 出す道具が親の `mcp-tools.json` と合うことをテストで確かめる。

## 人の判断待ち

いまはありません。
