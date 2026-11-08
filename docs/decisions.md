# 決めたこと

この部品の中だけで閉じることを残します。全体に関わることは親の `../qata/docs/decisions.md` に置きます。新しいものを上に足します。

---

## S1. 型の生成のしかた

- 決めた人：AI　レビュー：未
- datamodel-code-generator で、`../qata/contracts/schemas/` から `src/qata_server/contracts/` に生成する。手順は `scripts/generate_contracts.py`。
- 生成は、いつもリポジトリの外の一時フォルダで行ってから写す。生成先の ruff の設定で整形が変わり、「生成し直しても同じ」の検査が揺れないようにするため。生成物は ruff の対象から外す。
- 生成した型は、JSON Schema の `contains`（確認事項を一つは含む）や `if`/`then` を表せない。そのため、入ってきたテストケースの形式の検証は、型ではなく JSON Schema で行う（タスクの 1 で作る）。

## S2. 契約の検査は pytest-bdd で書く

- 決めた人：AI　レビュー：済（親を相対のパスで読むのは、次の周回で直す。親の ideas.md）
- `tests/contracts/contracts.feature` に日本語の Gherkin で観点を書く。はじく例は、契約の例の一か所を変える・消す形で表に並べ、「なぜ」の列を付ける。
- 親の契約は、作業フォルダで隣に並べた `../qata/` から読む。
