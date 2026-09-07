# まー式 株式短期売買判定 (masa-trade)

まー式短期売買の判定ロジックを毎日自動実行するためのPythonプロジェクト。

## 役割分担(v2.19 / v1.3)

このプロジェクトは、2つの独立したプロンプト(思想)で構成される「まー式」のうち、
**v1.3(統合運用プロンプト)** の自動化を担当する。

- **v2.19(ZERO-BASE DISCOVERY / ANCHORING CONTROL / BARON DISCOVERY LAYER /
  EXECUTION CONSTRAINT LAYER / EXECUTABLE EV PRINCIPLE)**:
  日次スクリーニングで新規候補を発掘するロジック。既存の保有・WATCH・過去銘柄を
  見ずに全市場から **NEW DISCOVERY**(新規候補)を抽出・仮ランキングし、そのあとで
  初めて **EXISTING WATCH**(既存WATCH・保有・過去相談銘柄)を合流させて
  **FINAL RANKING** を作る。候補は100点満点
  (材料・カタリスト25 / 需給20 / チャート・ENTRY位置20 / BARON SCORE15 /
  新規性・材料鮮度10 / EXECUTION適性10)でスコアリングされ、
  「①今夜PTSで入れる ②事前注文なら入れる ③12:30以降から狙える ④WATCHのみ
  ⑤時間制約により除外」の5分類から **MAIN ACTION**(必要なら **SUB ACTION** も)を
  決定する。**このプロジェクトはv2.19に一切手を入れない**。
- **v1.3(まー式AI投資会社・統合運用プロンプト)**: v2.19のFINAL RANKINGで選ばれた
  候補を、モードA(全市場発掘)/B(候補比較)/C(個別精査)でさらに深く検証し、
  3種類のスコア(企業価値100点・短期ENTRY100点・実行可能性100点)、
  6ゲート判定(会計/希薄化/材料実在/業績接続/織込み度/短期カタリスト)、
  CIO決裁書形式の最終出力まで落とし込む。**このプロジェクトが自動化するのはここ**。

`config/watchlist.yaml` は、本来は v2.19 の FINAL RANKING 結果を反映する想定の
連携ポイント。現時点ではv2.19との自動連携は未実装のため、サンプル銘柄を手動で
置いている(TODO参照)。

## 実装状況

`src/masa_trade/logic/schema.py` に、v1.3原文の【スコア】【6ゲート】
【CIO決裁書を冒頭に表示】の項目名・配点をそのまま反映したデータスキーマを定義している。
`src/masa_trade/logic/masa.py` の `judge()` はこのスキーマに沿って6ゲート判定・
3スコア・CIO決裁書を組み立てるが、**各ゲートの合否条件・各スコア項目の配点式・
CIO決裁書の企業判定/売買判定を導く最終ロジックはv1.3の詳細ルール確定待ち**のプレー
スホルダーになっている(詳細は「今後実装が必要な部分」を参照)。

## フォルダ構成

```
stock_trading/
├── config/
│   ├── settings.yaml     # データ取得設定、cio_review(ゲート閾値等)、通知設定、ログ設定
│   └── watchlist.yaml    # 判定対象の銘柄リスト(本来はv2.19のFINAL RANKING連携ポイント)
├── src/masa_trade/
│   ├── config.py         # settings.yaml / watchlist.yaml / .env の読み込み
│   ├── data/
│   │   └── fetcher.py    # yfinanceによる株価データ取得
│   ├── logic/
│   │   ├── schema.py     # v1.3の【スコア】【6ゲート】【CIO決裁書】データスキーマ
│   │   ├── indicators.py # 汎用テクニカル指標(SMA/RSI/出来高倍率)
│   │   └── masa.py       # v1.3判定ロジック本体(6ゲート判定・3スコア・CIO決裁書組み立て)
│   ├── notify/
│   │   └── notifier.py   # Slack/LINE/Emailへの通知(要実装)
│   └── main.py           # 日次実行のエントリーポイント
├── scripts/
│   └── run_daily.sh      # cron等から呼び出す実行スクリプト
├── tests/
│   ├── test_indicators.py # テクニカル指標のユニットテスト
│   └── test_masa.py       # ゲート判定・CIO決裁書組み立てのユニットテスト
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

- `src/masa_trade/logic/masa.py` の各ゲート判定関数: PASS/CAUTION/FAIL/UNKNOWN の
  具体的な合否条件(現状は保守的なプレースホルダー)。CAUTION判定は未実装。
- `src/masa_trade/logic/masa.py` の `score_corporate_value()` / `score_entry()` /
  `score_feasibility()`: 各スコア項目(`schema.py` の `*_ITEM_DEFINITIONS`)の
  配点式そのもの(現状は全項目 `points=None` で合計スコアが算出できない)。
- CIO決裁書の `corporate_judgment`(企業判定)・`ratings`(総合/短中長/テンバガー)・
  `supporting_points`/`opposing_points`(根拠3/反対3)・`order_proposal`(注文案)を
  導出するロジック。
- `src/masa_trade/notify/notifier.py`: Slack/LINE/Emailへの実際の送信処理。
- `src/masa_trade/data/fetcher.py`: 材料(適時開示・IR)・会計・希薄化・需給データの
  取得元の実装、および取得データのローカルキャッシュ(`config.data.cache_dir`)の活用。
- v2.19との連携: `config/watchlist.yaml` を v2.19 の FINAL RANKING 出力から
  自動生成する仕組み(現状は手動管理)。
