import logging
from fastapi import APIRouter, HTTPException, BackgroundTasks

from ..logic.analysis import run_analysis_task, save_data_to_json
from ..models.analysis import AnalysisFilter, AnalysisResponse
from ..logic.getTickersData import get_tickers_data
from ..logic.output import filter_and_enrich_data

# --- Router Setup ---
router = APIRouter(
    prefix="/analyze",
    tags=["Analysis"],
)

# --- API Endpoints ---
@router.post("/run-async", response_model=AnalysisResponse, status_code=202)
async def run_async_analysis(
    background_tasks: BackgroundTasks,
    filters: AnalysisFilter = AnalysisFilter()
):
    """株価分析プロセスをバックグラウンドで非同期に実行します。

    リクエスト後すぐにレスポンスを返し、実際の処理はバックグラウンドで行います。
    時間のかかる処理に適しています。

    Args:
        background_tasks (BackgroundTasks): FastAPIのバックグラウンドタスク機能。
        filters (AnalysisFilter): ユーザーが指定するフィルタリング条件。

    Returns:
        dict: タスクがバックグラウンドで開始されたことを示す確認メッセージ。
    """
    background_tasks.add_task(run_analysis_task, filters)
    return {"message": "Analysis task started in the background."}



@router.post("/run-sync", response_model=AnalysisResponse)
async def run_sync_analysis(filters: AnalysisFilter = AnalysisFilter()):
    """株価分析プロセスを同期的に実行し、処理の完了を待って結果を返します。

    n8nのワークフローなど、後続の処理が分析結果を必要とする場合に適しています。

    Args:
        filters (AnalysisFilter): ユーザーが指定するフィルタリング条件。

    Returns:
        dict: 処理の完了メッセージ、生成されたファイルのパス、
              そして分析・フィルタリング後のデータ本体を含みます。
    """
    logging.info("Starting synchronous stock analysis...")

    raw_data = get_tickers_data()
    if not raw_data:
        raise HTTPException(status_code=500, detail="Failed to get tickers data.")
    raw_data_path = save_data_to_json(raw_data, "raw_analysis")

    enriched_data = filter_and_enrich_data(
        data=raw_data,
        rsi_decision=filters.rsi_decision,
        deviation_25_decision=filters.deviation_25_decision,
        sma_75_decision=filters.sma_75_decision
    )
    
    enriched_data_path = None
    if enriched_data:
        enriched_data_path = save_data_to_json(enriched_data, "enriched_output")
    else:
        logging.warning("No data matched the filter criteria.")

    logging.info("Synchronous stock analysis finished.")
    
    return {
        "message": "Analysis completed successfully.",
        "raw_data_path": raw_data_path,
        "enriched_data_path": enriched_data_path,
        "analysis_results": enriched_data
    }
