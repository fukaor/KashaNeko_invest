import logging
from sqlalchemy.orm import Session

from .getTickersData import get_tickers_data
from ..models.db_models import AnalysisResult, AnalysisRun

def save_results_to_db(db: Session, results: dict, params: dict):
    """分析結果をデータベースに保存します。"""
    logging.info(f"Saving {len(results)} analysis results to the database...")
    try:
        # 1. 分析実行の記録を作成
        analysis_run = AnalysisRun(parameters_used=params)
        db.add(analysis_run)
        db.flush() # run.id を確定させる

        # 2. 各銘柄の分析結果を、上記の実行記録に紐づけて保存
        for ticker, data in results.items():
            result = AnalysisResult(
                analysis_run_id=analysis_run.id,
                ticker=data["ticker"],
                price=float(data["price"]),
                rsi=float(data["rsi"]),
                deviation_rate_25=float(data["deviation_rate_25"]),
                trend=data["trend"],
                macd_line=float(data["MACD"]["line"]),
                macd_signal=float(data["MACD"]["signal"]),
                dmi_dmp=float(data["DMI"]["dmp"]),
                dmi_dmn=float(data["DMI"]["dmn"]),
                adx=float(data["ADX"]),
                volume=int(data["Volume"]),
                signals=data["signals"],
                buy_score=int(data["buy_score"]),
                short_score=int(data["short_score"]),
            )
            db.add(result)
        
        db.commit()
        logging.info(f"Successfully saved analysis run {analysis_run.id} and {len(results)} results to the database.")
    except Exception as e:
        db.rollback()
        logging.error(f"Failed to save analysis results to database: {e}")
        raise

def run_analysis_task(db: Session):
    """株価分析のコアタスクを（バックグラウンドで）実行します。

    データの取得、分析、DBへの保存までの一連の処理を担当します。

    Args:
        db (Session): データベースセッション。
    """
    logging.info("Starting stock analysis task...")
    
    try:
        raw_data = get_tickers_data(db=db)
        if not raw_data:
            logging.error("Failed to get tickers data. Aborting task.")
            return
        
        # パラメータは全結果で共通なので、最初の一つから取り出す
        params_used = next(iter(raw_data.values()))['parameters_used']
        
        # データベースに保存
        save_results_to_db(db, raw_data, params_used)
        
        logging.info("Stock analysis task finished successfully.")
    except Exception as e:
        logging.error(f"An error occurred during the analysis task: {e}", exc_info=True)
    finally:
        db.close() # バックグラウンドタスクではセッションを明示的にクローズする
