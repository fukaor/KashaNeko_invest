from pydantic import BaseModel
from typing import List, Optional, Dict, Any

class AnalysisFilter(BaseModel):
    """分析結果をフィルタリングするための条件を定義するモデル。"""
    rsi_decision: Optional[List[str]] = ["買い", "買い準備"]
    deviation_25_decision: Optional[str] = "買い"
    sma_75_decision: Optional[str] = "買い"

class AnalysisResponse(BaseModel):
    """APIレスポンスの構造を定義するモデル。"""
    message: str
    raw_data_path: Optional[str] = None
    enriched_data_path: Optional[str] = None
    analysis_results: Optional[List[Any]] = None

class StockSummaryResponse(BaseModel):
    """トップ銘柄サマリーAPIのレスポンスモデル。"""
    top_buys: List[Any]
    top_shorts: List[Any]
