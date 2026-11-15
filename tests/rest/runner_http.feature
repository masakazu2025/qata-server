# language: ja
機能: runner に HTTP で命令を送る
  本物の runner の `POST /runs` に命令を送り、返ってきた本文を返す。判定は server の application 層が行う。

  シナリオ: 命令を POST /runs に送り、返ってきた本文を返す
    前提 runner は契約の例 "runner-result.json" を返す
    もし 契約の例 "runner-command.json" の命令を送る
    ならば runner は "/runs" に、その命令をそのまま受けた
    かつ 返ってきた本文は契約の例 "runner-result.json" と同じ

  シナリオ: JSON でない本文は、そのまま返す（server が契約に合わないと判定する）
    前提 runner は JSON でない本文を返す
    もし 契約の例 "runner-command.json" の命令を送る
    ならば 返ってきた本文は "<html>"

  シナリオ: runner が runner_busy で断ったら、ほかの実行の最中として扱う
    前提 runner は 409 で "runner_busy" を返す
    ならば 命令を送ると、runner はほかの実行の最中とされる

  シナリオ: runner がエラーを返したら、届かないものとして扱う
    前提 runner は HTTP 500 を返す
    ならば 命令を送ると、runner に届かないとされる

  シナリオ: runner が立ち上がっていなければ、届かないものとして扱う
    前提 runner が立ち上がっていない
    ならば 命令を送ると、runner に届かないとされる
