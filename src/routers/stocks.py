import logging
from typing import List
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..logic.stocks import search_stocks, get_top_stocks_summary
from ..database import get_db
from ..models.analysis import AnalysisResponse, StockSummaryResponse

logger = logging.getLogger(__name__)

# --- Router Setup ---
router = APIRouter(
    prefix="/stocks",
    tags=["Stocks"],
)

# --- API Endpoints ---
@router.get("/summary", response_model=StockSummaryResponse)
async def get_summary_endpoint(
    db: Session = Depends(get_db),
    top_n: int = Query(5, description="上位何件を取得するか")
):
    """
    最新の分析結果から、買いスコアと空売りスコアがトップNの銘柄リストを取得します。
    """
    logger.info(f"Received request to get top {top_n} stocks summary.")
    summary = get_top_stocks_summary(db=db, top_n=top_n)
    return summary

@router.get("/search", response_model=AnalysisResponse)
async def search_stocks_endpoint(
    db: Session = Depends(get_db),
    min_buy_score: int = Query(0, description="買いスコアの最小値"),
    min_short_score: int = Query(0, description="空売りスコアの最小値"),
    sort_by: str = Query("buy_score", description="ソート対象のカラム ('buy_score' or 'short_score')"),
    sort_order: str = Query("desc", description="ソート順 ('asc' or 'desc')"),
    limit: int = Query(100, description="取得する最大件数")
):
    """
    分析済みの銘柄データをデータベースから検索し、フィルタリングして返します。

    最新の分析結果を対象に、指定された条件でフィルタリングとソートを行います。
    """
    logger.info("Received request to search stocks.")
    
    results = search_stocks(
        db=db,
        min_buy_score=min_buy_score,
        min_short_score=min_short_score,
        sort_by=sort_by,
        sort_order=sort_order,
        limit=limit
    )
    
    return {
        "message": f"Found {len(results)} stocks.",
        "analysis_results": results
    }
