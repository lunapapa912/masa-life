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
(`tests/test_weekly_scoring.py`)で固定している。

「チャート/出来高」(15点)は、そのうち**ストップ高固定のプロキシ検出**
(`score_stop_high_lock_proxy()`)のみ実装済み。実装前にデータソースを確認した
結果、週間値幅ランキング画像は順位と上昇率(%)のみを提供し、絶対株価・基準値段
(直前営業日終値)を一切含まないと判明した(`RankEntry.price`はスキーマ上存在
するが、`loader.py`・実データとも常に`None`)。そのため、JPX制限値幅表を使った
正式なストップ高/安判定(`get_price_limit_width()`)は実装せず、「上昇率が
3時点以上連続で完全凍結」をストップ高の代理シグナルとして扱い、直近順位が
上位30%以内かどうかで「ストップ高で強い」(15点)と「出来高枯渇の疑い」(3点)
を区別している。誠建設工業(順位上位で凍結→15点)と古林紙工(順位下位で凍結
→3点)の実データで回帰テスト済み。

「CATALYST」(20点)は**TDnet適時開示のキーワード判定**(`score_catalyst_strength()`)
で実装済み。データ取得元は無料・認証不要のやのしんWEB-API
(`logic/weekly/tdnet.py`、https://webapi.yanoshin.jp/)を採用した。事前調査で、
`pip install tdnet`はPython 3.12以上必須(本プロジェクトは3.11)かつXBRL財務諸表を
丸ごとパースする大規模ライブラリで今回の用途には過剰と判明し、また公式サイト
`release.tdnet.info`はこのセッションの実行環境からプロキシ越しに到達不可
(CONNECT 502)だったため不採用とした。証券コードでの銘柄マッピングは不要にした:
やのしんAPIの日付範囲検索エンドポイントは1回のリクエストで全市場分の開示を返すため、
会社名の部分一致で絞り込める(週間ランキング画像には証券コードが載っていないことが
多いため、これはむしろ好都合)。開示タイトルはLLM判定を挟まず、`engine.py`内の
`CATALYST_POSITIVE_KEYWORDS`(好材料)・`CATALYST_NEGATIVE_KEYWORDS`(弱気、
深刻度別に0〜3点の辞書)・`CATALYST_NEUTRAL_KEYWORDS`(決算短信等の定型開示)の
3辞書でキーワード判定するのみの完全無料ロジック。

**実データでの発見**: 対象5銘柄(誠建設工業・オンコリスバイオ・テラドローン・
エプリー・古林紙工)について2026-09-07〜08の全市場開示210件を実際に取得し
会社名で絞り込んだ結果、**テラドローンにのみ開示があり**(2026-09-07 15:30
「第21回新株予約権(行使価額修正条項付)の大量行使...に関するお知らせ」)、
他4銘柄には開示がなかった。この開示は希薄化に直結する新株予約権の大量行使であり、
テラドローンの実際の急落(同日、前引け→終値で-14.7pt)と符合する。「新株予約権」を
`CATALYST_NEGATIVE_KEYWORDS`の重大区分(0点)に追加した根拠になっている。
一方、**誠建設工業のストップ高固定(前項)を裏付ける好材料の開示は見つからず**、
仮説は開示情報では確認できなかった(会社発表を伴わないテーマ/思惑・地合い起因の
値動きである可能性が残る)。

「テーマ/市場資金」(10点)は**JPX公式33業種区分による「業種集中度スコア」**
(`score_theme_market_flow()`)として実装済み。当初はみんかぶの人気テーマランキング・
株探のテーマ別銘柄一覧の利用を検討したが、実装前にみんかぶの利用規約フッターを
確認したところ「営業に利用することはもちろん、第三者へ提供する目的で情報を転用、
複製、販売、**加工**、再利用及び再配信することを固く禁じます」と明記されていた。
株探(kabutan.jp)はみんかぶと同一運営会社(MINKABU THE INFONOID, Inc.、両サイトの
フッターに同一著作権表記)であり同種の制限を受ける可能性が高く、今回作ろうとしている
「ランキング情報をスコアに加工する」処理はまさにこの禁止事項に該当するため、
両サイトとも不採用にした(技術的には到達可能だった)。代わりに、取引所自身が公開する
単純な銘柄コード→33業種区分の分類一覧である
JPX「東証上場銘柄一覧」(https://www.jpx.co.jp/markets/statistics-equities/misc/01.html、
`data_j.xlsx`、月1回更新)を`logic/weekly/sector.py`で取得・名寄せして使う。
週間ランキング画像上の銘柄名表記(カタカナ略称・英語表記等)とJPX正式名称の差異は
`SECTOR_NAME_ALIASES`辞書と部分一致フォールバックで吸収している。

**実データでの発見**: 2026-09-07(月)前引け時点の上位20銘柄をJPXデータで名寄せした
ところ、「情報・通信業」が5社(ソフトバンク・イメージ情報・VRAIN Solution・
メディカルネット・スカパー)と最も集中しており、対象5銘柄では**オンコリスバイオ
(医薬品、他にカイオムバイオ・ネクセラファーマの計3社)とエプリー(サービス業、
他にビジネスコーチ・INTLOOPの計3社)が業種集中の恩恵を受ける形(4点)**、
**誠建設工業(不動産業)・テラドローン(精密機器)・古林紙工(パルプ・紙)は
同業種の他銘柄が上位20位以内におらず中立(5点)**だった。また名寄せの過程で、
週間ランキング画像の「エプリー」がJPX銘柄名簿に見つからず、表記の近い「エブリー」
(コード607A、サービス業)を暫定的に採用した — 画像の transcription 時に
「ブ」を「プ」と誤読した可能性がある(`logic/weekly/sector.py`の
`SECTOR_NAME_ALIASES`にコメントを残してある。要検証)。

個別テーマ(AI関連・半導体関連等の思惑ベースの括り)は、上記のとおりみんかぶ・株探を
利用規約上の理由で使えないため今回のデータソースでは判定できず、対象外にしている。

「過去統計適合度」(10点)は`score_historical_fit()`として実装済みだが、
**常に中立基準点(5点)を返すプレースホルダー**。統計的な意味を持つ「過去の
類似パターンとの適合度」を計算するには複数週分の実績ログ(目安8〜12週)が
必要だが、現時点ではログが2026-09-07週の1週分しかないため、これ以上の実装は
時期尚早と判断した。ログ自体は `logic/weekly/history_log.py` で先に整備した:
`FutureMfeScore`(①〜⑦がネストしたリスト)を`HistoricalScoreLogEntry`という
①〜⑦それぞれ独立フィールドを持つ平坦な構造に変換し、`data/weekly_records/`配下に
JSON Lines形式で追記していく。独立フィールドにしているのは、将来
「今週のスコアパターン」と「過去の勝ちパターン」の類似度を計算しやすくするため。
このログは**振り返り専用**であり、LOOK-AHEAD BIAS禁止(v2.1 §26)を守るため
当該週の`score_future_mfe()`の判断には一切使わない(`score_historical_fit()`が
将来類似度計算に置き換わる際も、参照するのは「当該週より前の」レコードだけに
限定すること)。

これで**FUTURE MFE SCOREの①〜⑦全7項目が実装済み**になった(データが揃わない
場合の中立基準点フォールバックを含め、100点満点の"器"は完成)。
うち④CATALYST・⑤テーマ/市場資金・⑦過去統計適合度は、対象銘柄によっては
中立基準点にとどまる(開示なし・業種不明・ログ不足の場合)。残るタスクは
**②6ゲート相当のフラグ判定の自動化**(CONTINUATION OVERRIDE/TRAP CONTROL/
PEAK-OUT WARNING等)のみ。
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
│   │       ├── tdnet.py  # TDnet適時開示の取得(やのしんWEB-API、無料・認証不要)
│   │       ├── sector.py # JPX 33業種区分マスタの取得・名寄せ
│   │       ├── store.py  # WeeklyRecordのローカルJSONL永続化
│   │       └── history_log.py # ①〜⑦スコア内訳+実績のフラットな週次ログ(JSONL)
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
│   ├── test_weekly_scoring.py # v2.1 FUTURE MFE SCOREの実データ回帰テスト
│   ├── test_weekly_tdnet.py   # TDnet開示取得(やのしんAPI)のモックテスト
│   ├── test_weekly_sector.py  # JPX業種マスタのパース・名寄せのユニットテスト
│   └── test_weekly_history_log.py # 週次スコアログ(history_log.py)のユニットテスト
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
- `src/masa_trade/logic/weekly/engine.py` の `score_historical_fit()`: 現状は
  常に中立基準点(5/10点)を返すプレースホルダー。`logic/weekly/history_log.py`
  に週次ログが目安8〜12週分蓄積された時点で、今週のスコアパターン(①〜⑥の
  内訳)と過去の勝ちパターン(MODEL WINNER/EXECUTABLE WINNERになった週の
  スコアパターン)との類似度を計算するロジックに置き換える。その際も
  LOOK-AHEAD BIAS禁止(v2.1 §26)を守り、「当該週より前に書き込まれた」ログ
  だけを参照すること。
- `score_catalyst_strength()` のキーワード辞書ベース判定の限界: 皮肉な言い回し
  (例:「大幅な下方修正の可能性は低いと判断」のような否定を含む文)や、好材料と
  弱気材料が同じタイトルに混在する複合的な開示を誤判定する可能性がある。将来的には
  このセッション(Claude)自身が開示タイトル(必要なら本文)を読んで意味解釈する
  LLM判定に拡張する余地がある(キーワード辞書は一次スクリーニング、LLM判定は
  グレーゾーンの再判定、という二段構成も考えられる)。
- CATALYSTのデータ取得(`logic/weekly/tdnet.py`)は日付範囲の全市場検索を
  会社名で絞り込む設計にしており、証券コード解決には依存していない。ただし
  同名・類似名の別銘柄を誤って拾う可能性はゼロではない(部分一致のため)。
  証券コードが判明している銘柄は、`filter_by_company_name()`ではなく
  やのしんAPIの銘柄コード指定エンドポイント(`list/{code}.json2`)に切り替える
  ことでより厳密に絞り込める。
- ストップ高/安判定を「プロキシ(`score_stop_high_lock_proxy`, 上昇率凍結+順位
  ベース)」から「正式(`get_price_limit_width`, JPX制限値幅表ベース)」に
  切り替えるために必要なデータ:
  - 各銘柄の証券コード(現状`RankEntry.symbol`は画像から読めた場合のみ)
  - 基準値段(直前営業日終値)
  - 各チェックポイントの絶対株価(円)
  これらは画像からは取得できないため、証券コードさえ判明すれば
  `src/masa_trade/data/fetcher.py`(yfinance)で日足OHLCを取得し、
  直前終値・当日終値から`get_price_limit_width(base_price)`(JPX公式の
  制限値幅表を実装する関数、2026-09-04時点の値を確認済み)経由で判定する
  という経路が使える見込み。
- `classify_stock_type()` / `select_winners()`: A/B/C分類の境界・WINNER選定式
  (現状は原文に数値の明記がなくプレースホルダー)。FUTURE MFE SCOREの①〜⑦は
  全項目実装済み(うち④CATALYST・⑤テーマ/市場資金・⑦過去統計適合度は
  データ不足時に中立基準点へフォールバックする設計)になったが、これは
  「100点満点を必ず算出できる」ことを意味するだけで、その配点の閾値・
  重み付けが月曜前引け時点での実際の予測力(誰がMODEL WINNER/EXECUTABLE
  WINNERになるか)を正しく反映しているかはまだ検証できていない。
  `history_log.py` に複数週分のログが蓄積され、実際の勝敗パターンとの
  突き合わせができるようになってから着手する。
  `is_peak_out_warning()` の「複数成立」の具体的な閾値も同様に仮値(2件以上)。
- `score_theme_market_flow()` は「業種集中度」のみを見ており、個別テーマ
  (AI関連・半導体関連等の思惑ベースの括り)には対応していない。みんかぶ・株探は
  利用規約(「加工・再利用」の禁止)により不採用にしたため、将来的に規約準拠の
  個別テーマデータ源(例: 各社の適時開示や決算資料からClaude自身がテーマ性を
  読み取る、等)が見つかり次第、この項目を拡張する余地がある。
- `logic/weekly/sector.py` の `SECTOR_NAME_ALIASES`: 週間ランキング画像上の
  銘柄名表記とJPX正式名称の差異を都度追加していく運用。今回「エプリー」が
  JPX銘柄名簿に見つからず、近い表記の「エブリー」(コード607A)を暫定採用した
  ケースがあり、これは元画像の転記ミス(「ブ」を「プ」と誤読)の可能性がある。
  要検証。
- v2.1の週間値幅ランキング画像を構造化データ(`RankingSnapshot`)に変換する
  仕組み(現状はセッション内でClaudeが画像を読んで手動で構築する運用)。
- v2.1とv1.3の連携(EXECUTABLE WINNERをjudge()の6ゲートにも通すか)は、
  ユーザー判断により今回は見送り。将来必要になれば
  `WeeklyCandidate → JudgeInput` の変換ロジックを追加する。
