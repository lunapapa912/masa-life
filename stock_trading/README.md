# MASA式 株式短期売買判定 (masa-trade)

MASA式短期売買の判定ロジックを毎日自動実行するためのPythonプロジェクト。
このコミットでは **土台(フォルダ構成・設定ファイル)** のみを用意しており、
判定ロジックそのもの(`src/masa_trade/logic/masa.py` の `judge()`)は
スコアリングの条件が未実装のプレースホルダーになっている。

## フォルダ構成

```
stock_trading/
├── config/
│   ├── settings.yaml     # ロジックのパラメータ、データ取得設定、通知設定、ログ設定
│   └── watchlist.yaml    # 判定対象の銘柄リスト
├── src/masa_trade/
│   ├── config.py         # settings.yaml / watchlist.yaml / .env の読み込み
│   ├── data/
│   │   └── fetcher.py    # yfinanceによる株価データ取得
│   ├── logic/
│   │   └── masa.py       # MASA式判定ロジック(指標計算 + judge、要実装)
│   ├── notify/
│   │   └── notifier.py   # Slack/LINE/Emailへの通知(要実装)
│   └── main.py           # 日次実行のエントリーポイント
├── scripts/
│   └── run_daily.sh      # cron等から呼び出す実行スクリプト
├── tests/
│   └── test_masa.py      # 指標計算関数のユニットテスト
├── data/                 # 取得データのキャッシュ置き場(gitignore対象)
├── logs/                 # ログ出力先(gitignore対象)
├── .github/workflows/
│   └── daily.yml         # GitHub Actionsによる平日自動実行(15:30 JST)
├── .env.example          # 環境変数のテンプレート
├── pyproject.toml
└── .gitignore
```

## セットアップ

```bash
cd stock_trading
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env   # 通知を使う場合は値を埋める
```

## 実行

```bash
python -m masa_trade.main
# または
./scripts/run_daily.sh
```

## テスト

```bash
pytest
```

## 自動実行

`.github/workflows/daily.yml` により、平日15:30(JST)にGitHub Actions上で自動実行される。
Slack/LINE/Emailで通知する場合は、リポジトリの Settings > Secrets and variables > Actions に
`SLACK_WEBHOOK_URL` などのシークレットを登録し、`config/settings.yaml` の `notify.channels` を
有効にする。

自前のサーバーで動かす場合は `scripts/run_daily.sh` を cron に登録する:

```cron
30 15 * * 1-5 /path/to/stock_trading/scripts/run_daily.sh
```

## 銘柄の追加・変更

`config/watchlist.yaml` に `symbol`(yfinance形式、日本株は `XXXX.T`)と `name` を追加する。

## 今後実装が必要な部分(TODO)

- `src/masa_trade/logic/masa.py` の `judge()`: MASA式の具体的な条件・スコアリングロジック
- `src/masa_trade/notify/notifier.py`: Slack/LINE/Emailへの実際の送信処理
- `src/masa_trade/data/fetcher.py`: 取得データのローカルキャッシュ(`config.data.cache_dir`)の活用
