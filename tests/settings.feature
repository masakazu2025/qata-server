# language: ja
機能: 設定
  設定は環境変数で渡す。読むのは settings.py の Settings だけで、ほかはその型を受け取る。契約の場所は設定にしない（読む版の写しの qata-contracts/ を読む）。

  シナリオ: 環境変数がなければ、既定の値になる
    前提 qata の環境変数を置いていない
    ならば 設定の "data_dir" は "data"
    かつ 設定の "runner_url" は "http://127.0.0.1:8001"
    かつ 設定の "host" は "127.0.0.1"
    かつ 設定の "port" は "8000"

  シナリオ: 環境変数で、設定を変えられる
    前提 qata の環境変数を置いていない
    かつ 環境変数 "QATA_DATA_DIR" を "elsewhere/data" にする
    かつ 環境変数 "QATA_RUNNER_URL" を "http://runner.example:9001" にする
    かつ 環境変数 "QATA_HOST" を "0.0.0.0" にする
    かつ 環境変数 "QATA_PORT" を "9000" にする
    ならば 設定の "data_dir" は "elsewhere/data"
    かつ 設定の "runner_url" は "http://runner.example:9001"
    かつ 設定の "host" は "0.0.0.0"
    かつ 設定の "port" は "9000"

  シナリオ: 空の環境変数は、置いていないものとして扱う
    前提 qata の環境変数を置いていない
    かつ 環境変数 "QATA_DATA_DIR" を "" にする
    ならば 設定の "data_dir" は "data"

  シナリオ: 数でないポートは、立ち上げる前にはじく
    前提 qata の環境変数を置いていない
    かつ 環境変数 "QATA_PORT" を "eighty" にする
    ならば 設定を読むと、"port" の誤りになる

  シナリオ: 立ち上げの設定が誤っていても、契約の判定は読み込める
    前提 qata の環境変数を置いていない
    かつ 環境変数 "QATA_PORT" を "eighty" にする
    ならば 契約の判定を読み込み直しても、誤りにならない

  シナリオ: 組み立ては、受け取った設定の保存先と runner の場所を使う
    前提 保存先を一時フォルダに、runner の場所を "http://runner.example:9001" にした設定
    もし その設定で server を組み立てる
    ならば 保存先の一時フォルダに、保存のファイルができる
    かつ runner への道具は "http://runner.example:9001" を指す

  シナリオ: 立ち上げは、環境変数の待ち受ける場所を使う
    前提 qata の環境変数を置いていない
    かつ 環境変数 "QATA_DATA_DIR" を一時フォルダにする
    かつ 環境変数 "QATA_HOST" を "0.0.0.0" にする
    かつ 環境変数 "QATA_PORT" を "9000" にする
    もし server を立ち上げる
    ならば "0.0.0.0" の 9000 番で待ち受ける

  シナリオ: 環境変数を読むのは settings.py だけ
    ならば src と scripts に、settings.py を通さずに環境変数を読むところがない

  シナリオアウトライン: 環境変数を読む書き方を、見落とさない
    ならば <書き方> は、環境変数を読むとみなす

    例:
      | 書き方                                   |
      | os.environ.get("QATA_X")                 |
      | os.environ["QATA_X"]                     |
      | os.getenv("QATA_X")                      |
      | "QATA_X" in os.environ                   |
      | os.environ.copy()["QATA_X"]              |
      | from os import environ                   |

  シナリオ: 子のプロセスに環境をそのまま渡すのは、読むとみなさない
    ならば env={**os.environ, "RUFF_NO_CACHE": "true"} は、環境変数を読むとみなさない
