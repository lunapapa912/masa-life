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

さらに、v1.3・v2.19を補完する第3の戦略として **v2.1(まー式・鉄人戦週間ランキング
戦略)** がある。月曜日の3時点(始まり値・10:30・前引け)を起点に、週間値幅
ランキング(全50銘柄)をゼロベース評価し、MODEL WINNER(理論上のベスト)と
EXECUTABLE WINNER(実際に買える現実解)を分離して選定、月〜金でMFE/MAEを追跡し、
金曜にWEEKLY AUDITを行う週次サイクル。v1.3・v2.19が日次/都度なのに対し、
v2.1は **週をまたぐ状態(月曜に決めた本命の固定、複数週の統計蓄積)を持つ点**が
大きく異なるため、`logic/weekly/` として独立させている
(**現時点ではv1.3のjudge()とは連携させていない**)。

## 実装状況

`src/masa_trade/logic/schema.py` に、v1.3原文の【スコア】【6ゲート】
【CIO決裁書を冒頭に表示】の項目名・配点をそのまま反映したデータスキーマを定義している。
`src/masa_trade/logic/masa.py` の `judge()` はこのスキーマに沿って6ゲート判定・
3スコア・CIO決裁書を組み立てるが、**各ゲートの合否条件・各スコア項目の配点式・
CIO決裁書の企業判定/売買判定を導く最終ロジックはv1.3の詳細ルール確定待ち**のプレー
スホルダーになっている(詳細は「今後実装が必要な部分」を参照)。

同様に `src/masa_trade/logic/weekly/schema.py` に v2.1原文の【FUTURE MFE SCORE】
(7項目・配点)、A/B/C分類、6ゲート相当のフラグ群(CONTINUATION OVERRIDE/TRAP
CONTROL/PEAK-OUT WARNING/EXIT等)、MFE/MAE/CAPTURE RATEのデータスキーマを定義し、
`logic/weekly/engine.py` に判定関数を実装している。**原文に数値が明記されている
部分**(FUTURE MFE SCOREの配点、MARKET REGIME DEFENSEの閾値、CONTINUATION
OVERRIDEの「3項目以上」、MFE/MAE/CAPTURE RATEの計算式)はそのまま実装済み。
FUTURE MFE SCOREの7項目のうち「ランキング推移」「上昇率加速度」「過熱/下落
リスク」(計45点)は、2026-09-07/08の実データ(週間値幅ランキング50銘柄・
月火6時点)から導いた配点式を実装し、実データでの回帰テスト
(`tests/test_weekly_scoring.py`)で固定している。残り4項目(チャート/出来高・
CATALYST・テーマ/市場資金・過去統計適合度)は出来高・材料・テーマ・複数週の
統計データが未取得のため未算出(`points=None`)。
**数値の明記がない部分**(A/B/C分類の境界、MODEL/EXECUTABLE WINNERの選定式、
PEAK-OUT WARNINGの具体的な組み合わせ数)はTODOのプレースホルダー。

重要な設計上の知見: 実データ検証で、「ランキング推移」「上昇率加速度」
「過熱/下落リスク」の3項目は**月曜前引け時点で入手可能なデータだけでは
その後の急落を予測できない**ことが分かった(前引けまでの2時点だけでは、
後に急落した銘柄と継続に成功した銘柄が同じスコアになった)。そのため
これらは「月曜前引け一発のFUTURE MFE SCORE」としてではなく、**新しい
チェックポイントが来るたびに再評価するHOLDスコア的な用途**を想定している
(`tests/test_weekly_scoring.py` の
`test_ranking_and_momentum_cannot_distinguish_reversal_risk_at_monday_midday_close`
参照)。

週間値幅ランキング画像の読み取りは自動化しておらず、セッション(Claude)が画像を
見て構造化データに変換し、`logic/weekly/`の各関数に渡す運用を前提としている。
週次記録は `logic/weekly/store.py` でローカルJSONL(`data/weekly_records/`)に
保存する(gitignore対象)。

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
│   │   ├── masa.py       # v1.3判定ロジック本体(6ゲート判定・3スコア・CIO決裁書組み立て)
│   │   ├── common/
│   │   │   └── order.py  # OrderProposal/PriceTiers/MarketRegime(v1.3・v2.1共通)
│   │   └── weekly/       # v2.1(週間ランキング戦略)。v1.3とは独立
│   │       ├── schema.py # A/B/C分類・FUTURE MFE SCORE・WeeklyRecord等
│   │       ├── engine.py # market regime判定・FUTURE MFE SCORE(3/7項目実装)・MFE/MAE/CAPTURE RATE計算
│   │       ├── loader.py # ランキング画像から読み取ったJSON/dictをスキーマへ変換
│   │       └── store.py  # WeeklyRecordのローカルJSONL永続化
│   ├── notify/
│   │   └── notifier.py   # Slack/LINE/Emailへの通知(要実装)
│   └── main.py           # 日次実行のエントリーポイント(v1.3のみ。v2.1は未配線)
├── scripts/
│   └── run_daily.sh      # cron等から呼び出す実行スクリプト
├── tests/
│   ├── test_indicators.py     # テクニカル指標のユニットテスト
│   ├── test_masa.py           # v1.3ゲート判定・CIO決裁書組み立てのユニットテスト
│   ├── test_weekly.py         # v2.1スコア定義・market regime・MFE/MAE等のユニットテスト
│   ├── test_weekly_loader.py  # v2.1ランキング画像JSONの読み込みユニットテスト
│   └── test_weekly_scoring.py # v2.1 FUTURE MFE SCOREの実データ回帰テスト
├── data/                 # 取得データのキャッシュ置き場(gitignore対象)
│   └── weekly_records/   # v2.1のWeeklyRecord JSONL保存先(gitignore対象)
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
- `src/masa_trade/logic/weekly/engine.py` の `score_future_mfe()`: FUTURE MFE
  SCOREの残り4項目(チャート/出来高15・CATALYST20・テーマ/市場資金10・
  過去統計適合度10)。出来高・材料・テーマ・複数週の統計データが必要。
- `classify_stock_type()` / `select_winners()`: A/B/C分類の境界・WINNER選定式
  (現状は原文に数値の明記がなくプレースホルダー)。実装済みの3項目(ランキング
  推移・上昇率加速度・過熱/下落リスク)だけでは月曜前引け時点での予測力が
  不十分なことが実データで判明しているため、残り4項目が揃ってから着手する。
  `is_peak_out_warning()` の「複数成立」の具体的な閾値も同様に仮値(2件以上)。
- v2.1の週間値幅ランキング画像を構造化データ(`RankingSnapshot`)に変換する
  仕組み(現状はセッション内でClaudeが画像を読んで手動で構築する運用)。
- v2.1とv1.3の連携(EXECUTABLE WINNERをjudge()の6ゲートにも通すか)は、
  ユーザー判断により今回は見送り。将来必要になれば
  `WeeklyCandidate → JudgeInput` の変換ロジックを追加する。
