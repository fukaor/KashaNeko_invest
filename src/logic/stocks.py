import logging
import yfinance as yf
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import desc

from ..models.db_models import AnalysisResult, AnalysisRun

logger = logging.getLogger(__name__)

def _enrich_results(results: list, latest_run: AnalysisRun) -> list:
    """
    分析結果のリストに企業情報と実行情報を付加する内部関数。
    """
    enriched_results = []
    for result in results:
        enriched_result = {col.name: getattr(result, col.name) for col in result.__table__.columns}
        enriched_result["analyzed_at"] = latest_run.analyzed_at
        enriched_result["parameters_used"] = latest_run.parameters_used
        
        try:
            if result.ticker == "^N225":
                enriched_result['info'] = {}
                enriched_results.append(enriched_result)
                continue

            ticker_yf = f"{result.ticker}.T"
            ticker_obj = yf.Ticker(ticker_yf)
            info = ticker_obj.info
            selected_fields = ["website", "industry", "sector", "longBusinessSummary", "shortName", "longName", "recommendationKey"]
            enriched_result['info'] = {field: info.get(field) for field in selected_fields}
            enriched_results.append(enriched_result)
            logger.debug(f"Enriched data for {result.ticker}")

        except Exception as e:
            logger.error(f"Could not fetch 'info' for {result.ticker}: {e}")
            enriched_result['info'] = {}
            enriched_results.append(enriched_result)
    return enriched_results

def get_top_stocks_summary(db: Session, top_n: int = 5):
    """
    最新の分析結果から、買いスコアと空売りスコアがトップNの銘柄リストを取得します。

    Args:
        db (Session): データベースセッション。
        top_n (int): 上位何件を取得するか。

    Returns:
        dict: "top_buys"と"top_shorts"をキーに持つ辞書。
    """
    logger.info(f"Fetching top {top_n} stocks summary...")
    try:
        latest_run = db.query(AnalysisRun).order_by(desc(AnalysisRun.analyzed_at)).first()
        if not latest_run:
            logger.warning("No analysis runs found in the database.")
            return {"top_buys": [], "top_shorts": []}

        # Top N Buy Score
        top_buys_query = db.query(AnalysisResult)\
            .filter(AnalysisResult.analysis_run_id == latest_run.id)\
            .order_by(desc(AnalysisResult.buy_score))\
            .limit(top_n)\
            .all()

        # Top N Short Score
        top_shorts_query = db.query(AnalysisResult)\
            .filter(AnalysisResult.analysis_run_id == latest_run.id)\
            .order_by(desc(AnalysisResult.short_score))\
            .limit(top_n)\
            .all()
            
        enriched_buys = _enrich_results(top_buys_query, latest_run)
        enriched_shorts = _enrich_results(top_shorts_query, latest_run)

        logger.info("Successfully fetched top stocks summary.")
        return {"top_buys": enriched_buys, "top_shorts": enriched_shorts}

    except Exception as e:
        logger.error(f"An error occurred while fetching top stocks summary: {e}", exc_info=True)
        return {"top_buys": [], "top_shorts": []}


def search_stocks(
    db: Session,
    min_buy_score: int = 0,
    min_short_score: int = 0,
    sort_by: str = "buy_score",
    sort_order: str = "desc",
    limit: int = 100
):
    """
    データベースに保存された最新の分析結果をフィルタリング、ソート、情報付加して取得します。

    Args:
        db (Session): データベースセッション。
        min_buy_score (int): 買いスコアの最小値。
        min_short_score (int): 空売りスコアの最小値。
        sort_by (str): ソート対象のカラム名 ('buy_score' or 'short_score').
        sort_order (str): ソート順 ('asc' or 'desc').
        limit (int): 取得する最大件数。

    Returns:
        list: フィルタリング、ソート、情報付加された銘柄データのリスト。
    """
    logger.info(f"Searching stocks with criteria: min_buy_score={min_buy_score}, min_short_score={min_short_score}, sort_by={sort_by}, limit={limit}")

    try:
        # 最新の分析実行を取得
        latest_run = db.query(AnalysisRun).order_by(desc(AnalysisRun.analyzed_at)).first()
        if not latest_run:
            logger.warning("No analysis runs found in the database.")
            return []
        
        logger.info(f"Querying results for the latest analysis run: {latest_run.id} at {latest_run.analyzed_at}")

        # 最新の実行IDに紐づく分析結果をクエリ
        query = db.query(AnalysisResult).filter(AnalysisResult.analysis_run_id == latest_run.id)

        # フィルタリング
        if min_buy_score > 0:
            query = query.filter(AnalysisResult.buy_score >= min_buy_score)
        if min_short_score > 0:
            query = query.filter(AnalysisResult.short_score >= min_short_score)

        # ソート
        sort_column = AnalysisResult.buy_score if sort_by == "buy_score" else AnalysisResult.short_score
        if sort_order == "desc":
            query = query.order_by(desc(sort_column))
        else:
            query = query.order_by(sort_column)

        # 取得件数制限
        results = query.limit(limit).all()
        logger.info(f"Found {len(results)} stocks matching criteria.")

        # yfinanceで企業情報を付加
        enriched_results = _enrich_results(results, latest_run)
        
        logger.info("Stock search and enrichment completed successfully.")
        return enriched_results

    except Exception as e:
        logger.error(f"An error occurred during stock search: {e}", exc_info=True)
        return []