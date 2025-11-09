# システムアーキテクチャと設計

このドキュメントは、平日に定時実行されるAI分析、TypeScriptによるフロントエンド、メール通知、AIによる自動パフォーマンスレビューと**動的パラメータチューニング**、そしてフロントエンドでのグラフ描画といった機能を備えたフルスタックアプリケーションのアーキテクチャを概説します。

## 1. 拡張アーキテクチャ (コンポーネント図)

AIによる再評価の結果に基づき、テクニカル指標の計算で用いられる閾値（RSIのレベル、移動平均乖離率など）を動的に変更します。これらの閾値は「チューニングパラメータ」としてデータベースに保存され、分析ロジックおよび再評価ロジックから利用されます。

```plantuml
@startuml
!theme vibrant
skinparam linetype ortho
actor ユーザー

package "フロントエンド" {
  component "React App (TypeScript)" as Frontend
}

package "バックエンド (Python)" {
  component "FastAPIサーバー" as FastAPI

  package "API & ルーター" {
    component "分析結果ルーター" as ResultRouter
    component "グラフデータルーター" as GraphRouter
  }

  package "コアロジック" {
    component "分析ロジック" as AnalysisLogic
    component "再評価ロジック" as ReEvalLogic
    component "グラフデータロジック" as ChartLogic
  }

  package "サービス" {
    component "生成AIサービス" as AIService
    component "スケジューラ (APScheduler)" as Scheduler
  }

  package "データ & 状態" {
    database "データベース (PostgreSQL)" as DB
    database "ファイルシステム" as FS {
      collections "tickers.csv"
    }
  }
}

package "外部サービス" {
  component "yfinance API" as YFinance
  component "NewsAPI" as NewsAPI
  component "生成AI API\n(例: Gemini)" as GenAI
  component "メール送信サービス\n(SMTP/API)" as MailService
}

' --- 接続 ---
ユーザー ----> Frontend: ブラウザで操作
Frontend ----> FastAPI: APIリクエスト (HTTP/JSON)

FastAPI --> ResultRouter
FastAPI --> GraphRouter

Scheduler ----> AnalysisLogic: 定時分析を実行
Scheduler ----> ReEvalLogic: 再評価をトリガー

AnalysisLogic ----> YFinance: 株価データ取得
AnalysisLogic ----> NewsAPI: 最新ニュース取得
AnalysisLogic ----> MailService: 通知メール送信
AnalysisLogic ----> DB: チューニングパラメータ読込
AnalysisLogic ----> AIService: 投資判断理由を取得
AnalysisLogic ----> DB: 新規投資判断を保存

GraphRouter ----> ChartLogic
ChartLogic ----> YFinance: 価格履歴を取得
ChartLogic ----> DB: 投資判断履歴を取得

ReEvalLogic ----> DB: 過去の投資判断を読込
ReEvalLogic ----> YFinance: 現在価格を取得
ReEvalLogic ----> AIService: 再評価を取得
ReEvalLogic ----> DB: チューニングパラメータを更新

AIService ----> GenAI: API呼び出し

@enduml
```

## 2. フロントエンドアプリケーション

ユーザーインターフェースを提供するため、TypeScriptとReactフレームワークをベースとしたフロントエンドアプリケーションを導入します。バックエンドで定時実行された分析結果の閲覧や、インタラクティブなグラフの表示などを担います。

## 3. シーケンス図

### 3.1. シーケンス: 定時実行される条件付きAI分析と通知

スケジューラが平日の14:30に分析プロセスを自動的に開始します。分析ロジックは、まずデータベースから最新の**チューニングパラメータ（各種テクニカル指標の閾値など）**を読み込み、それを用いてスコアを計算します。スコアが閾値を超え、かつAI分析でリスク無しと判断された銘柄は、ユーザーにメールで通知されます。

```plantuml
@startuml
!theme vibrant
autonumber
participant "スケジューラ" as Scheduler
participant "分析ロジック" as Logic
participant "NewsAPI" as NewsAPI
participant "生成AIサービス" as AIService
participant "データベース" as DB
participant "メール送信サービス" as MailService

Scheduler -> Logic: run_scheduled_analysis() (後場の14:30頃に実行)
activate Logic

Logic -> DB: チューニングパラメータ(閾値など)を取得
Logic -> Logic: 全銘柄のテクニカル指標とスコアを計算

loop 各銘柄について
  opt スコアが閾値以上
    Logic -> NewsAPI: 最新ニュースを取得(銘柄)
    activate NewsAPI
    NewsAPI --> Logic: ニュース記事
    deactivate NewsAPI

    Logic -> AIService: generate_rationale_and_risk(スコア, ニュース記事)
    activate AIService
    AIService --> Logic: 投資判断理由とリスク評価
    deactivate AIService

    opt AIの評価でリスク無し
      Logic -> MailService: 通知メールを送信
      activate MailService
      MailService --> Logic: 送信成功
      deactivate MailService
    end
  end
  Logic -> DB: 投資判断を保存 (AI理由・リスク評価含む/含まず)
end

Logic --> Scheduler: タスク完了
deactivate Logic
@enduml
```

### 3.2. シーケンス: AIによる再評価とチューニング

このプロセスはバックエンド内部で完結し、スケジューラによって自動的に実行されます。AIからの提案に基づき、データベース内の**チューニングパラメータ（テクニカル指標の閾値の具体的な数値など）**を更新する処理が含まれます。

```plantuml
@startuml
!theme vibrant
autonumber
participant "スケジューラ" as Scheduler
participant "再評価ロジック" as Logic
participant "生成AIサービス" as AIService
participant "データベース" as DB
participant "yfinance API" as YFinance

Scheduler -> Logic: trigger_re_evaluation()
activate Logic
Logic -> DB: 10日以上前の投資判断を取得
activate DB
DB --> Logic: 過去の投資判断リスト
deactivate DB

loop 各投資判断について
  Logic -> YFinance: 現在価格を取得
  Logic -> Logic: パフォーマンスを評価 (利益/損失)
  Logic -> AIService: re_evaluate_and_suggest_tuning(判断, 結果)
  activate AIService
  AIService --> Logic: チューニング提案
  deactivate AIService
  Logic -> DB: 提案に基づきチューニングパラメータ(閾値など)を更新
end

Logic --> Scheduler: タスク完了
deactivate Logic
@enduml
```

### 3.3. シーケンス: 投資判断グラフの生成

バックエンドはグラフ描画用の生データを返却し、フロントエンドがブラウザ上で動的にグラフを描画します。

```plantuml
@startuml
!theme vibrant
autonumber
actor ユーザー
participant "フロントエンド" as Frontend
participant "グラフデータルーター" as Router
participant "グラフデータロジック" as Logic
participant "yfinance API" as YFinance
participant "データベース" as DB

ユーザー -> Frontend: グラフ表示を要求 (銘柄指定)
activate Frontend
Frontend -> Router: GET /graph-data/{ticker}
activate Router

Router -> Logic: get_chart_data(ticker)
activate Logic
Logic -> YFinance: 価格履歴を取得
Logic -> DB: 銘柄の投資判断履歴を取得
Logic --> Router: 価格履歴と投資判断のデータ (JSON)
deactivate Logic

Router --> Frontend: グラフ描画用のJSONデータ
deactivate Router
Frontend -> Frontend: 受信したデータで動的にグラフを描画
Frontend -> ユーザー: インタラクティブなグラフを表示
deactivate Frontend
@enduml
```

### 3.4. シーケンス: データベースアクセス詳細

APIがリクエストを受け取ってから、データベースを操作して分析を実行し、結果を保存するまでの一連の流れを以下に示します。

```plantuml
@startuml
!theme vibrant
autonumber

participant "FastAPI Router" as Router
participant "Dependency (get_db)" as Dep
participant "Analysis Logic" as Logic
database "PostgreSQL" as DB

Router -> Dep: get_db()
activate Dep
Dep -> DB: Create Session
activate DB
DB --> Dep: DB Session
deactivate DB
Dep --> Router: DB Session
deactivate Dep

Router -> Logic: run_analysis_task(db_session)
activate Logic

Logic -> DB: SELECT * FROM tuning_parameters
activate DB
DB --> Logic: Tuning Parameters
deactivate DB

Logic -> Logic: ...株価データ取得と分析実行...

Logic -> DB: INSERT INTO analysis_results (...)
activate DB
DB --> Logic: Commit OK
deactivate DB

Logic --> Router: Task Finished
deactivate Logic

Router -> Dep: close_db_session()
activate Dep
Dep -> DB: Close Session
activate DB
deactivate DB
deactivate Dep

@enduml
```

## 4. データベース設計 (ER図)

`tuning_parameters`、`analysis_runs`、`analysis_results`の各テーブル構成を以下に示します。

```plantuml
@startuml
!theme vibrant
hide circle
skinparam linetype ortho

entity "tuning_parameters" as TP {
  + id [PK]: INTEGER
  --
  * date: DATE
  * name: VARCHAR
  * value: FLOAT
  description: VARCHAR
  created_at: DATETIME
  updated_at: DATETIME
  --
  UniqueConstraint(date, name)
}

entity "analysis_runs" as Run {
  + id [PK]: INTEGER
  --
  * analyzed_at: DATETIME
  parameters_used: JSON
}

entity "analysis_results" as Result {
  + id [PK]: INTEGER
  --
  * analysis_run_id [FK]: INTEGER
  * ticker: VARCHAR
  price: FLOAT
  rsi: FLOAT
  deviation_rate_25: FLOAT
  trend: VARCHAR
  macd_line: FLOAT
  macd_signal: FLOAT
  dmi_dmp: FLOAT
  dmi_dmn: FLOAT
  adx: FLOAT
  volume: FLOAT
  signals: JSON
  buy_score: INTEGER
  short_score: INTEGER
}

Run ||--o{ Result : "has many"

@enduml
```

### テーブルの説明

-   **`tuning_parameters`**:
    *   **役割**: テクニカル分析で使用される各種パラメータ（RSIの期間、移動平均線の閾値など）を格納します。
    *   **特徴**: パラメータは日付ごとにバージョン管理され、分析実行時には最新の日付のパラメータセットが使用されます。これにより、パラメータの動的な調整と履歴管理が可能になります。

-   **`analysis_runs`**:
    *   **役割**: 個々の分析実行のメタデータ（いつ実行されたか、どのパラメータセットが使用されたかなど）を記録します。
    *   **特徴**: 各分析実行は一意のIDを持ち、その実行で使用された`tuning_parameters`のスナップショットが`parameters_used`カラムにJSON形式で保存されます。

-   **`analysis_results`**:
    *   **役割**: 各銘柄の具体的な分析結果（株価、テクニカル指標の値、シグナル、スコアなど）を格納します。
    *   **特徴**: `analysis_run_id`を通じて`analysis_runs`テーブルに紐付けられ、どの分析実行の結果であるかを識別できます。これにより、`parameters_used`の重複を避け、データベースの正規化が実現されています。