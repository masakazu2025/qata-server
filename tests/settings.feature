# language: ja
機能: 設定
  設定は環境変数で渡す。読むのは settings.py の Settings だけで、ほかは Settings を受け取る。

  シナリオ: 環境変数がなければ、既定の値になる
    前提 qata の環境変数を置いていない
    ならば 設定の "data_dir" は "data"
    かつ 設定の "runner_url" は "http://127.0.0.1:8001"
    かつ 設定の "host" は "127.0.0.1"
    かつ 設定の "port" は "8000"
    かつ 親のリポジトリは、隣に並べた qata を指す

  シナリオ: 環境変数で、設定を変えられる
    前提 qata の環境変数を置いていない
    かつ 環境変数 "QATA_DATA_DIR" を "elsewhere/data" にする
    かつ 環境変数 "QATA_RUNNER_URL" を "http://runner.example:9001" にする
    かつ 環境変数 "QATA_HOST" を "0.0.0.0" にする
    かつ 環境変数 "QATA_PORT" を "9000" にする
    かつ 環境変数 "QATA_PARENT_DIR" を "elsewhere/qata" にする
    ならば 設定の "data_dir" は "elsewhere/data"
    かつ 設定の "runner_url" は "http://runner.example:9001"
    かつ 設定の "host" は "0.0.0.0"
    かつ 設定の "port" は "9000"
    かつ 設定の "parent_dir" は "elsewhere/qata"

  シナリオ: 空の環境変数は、置いていないものとして扱う
    前提 qata の環境変数を置いていない
    かつ 環境変数 "QATA_PARENT_DIR" を "" にする
    ならば 親のリポジトリは、隣に並べた qata を指す

  シナリオ: 数でないポートは、立ち上げる前にはじく
    前提 qata の環境変数を置いていない
    かつ 環境変数 "QATA_PORT" を "eighty" にする
    ならば 設定を読むと、"port" の誤りになる

  シナリオ: 組み立ては、受け取った設定の保存先と runner の場所を使う
    前提 保存先を一時フォルダに、runner の場所を "http://runner.example:9001" にした設定
    もし その設定で server を組み立てる
    ならば 保存先の一時フォルダに、保存のファイルができる
    かつ runner への道具は "http://runner.example:9001" を指す

  シナリオ: 環境変数を読むのは Settings だけ
    ならば src と scripts に、Settings を通さずに環境変数の値を読むところがない
