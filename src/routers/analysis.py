import logging
from fastapi import APIRouter, BackgroundTasks, Depends
from sqlalchemy.orm import Session

from ..logic.analysis import run_analysis_task
from ..models.analysis import AnalysisResponse
from ..database import get_db

# --- Router Setup ---
router = APIRouter(
    prefix="/analyze",
    tags=["Analysis"],
)

# --- API Endpoints ---
@router.post("/run", response_model=AnalysisResponse, status_code=202)
async def run_analysis(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """株価分析プロセスをバックグラウンドで非同期に実行します。

    リクエスト後すぐにレスポンスを返し、実際の処理はバックグラウンドで行います。
    このエンドポイントは分析タスクを開始するだけで、フィルタリングは行いません。

    Args:
        background_tasks (BackgroundTasks): FastAPIのバックグラウンドタスク機能。
        db (Session): データベースセッション。

    Returns:
        dict: タスクがバックグラウンドで開始されたことを示す確認メッセージ。
    """
    logging.info("Received request to run analysis.")
    background_tasks.add_task(run_analysis_task, db=db)
    logging.info("Analysis task has been successfully started in the background.")
    return {"message": "Analysis task started in the background."}
