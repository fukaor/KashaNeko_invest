import os
import json
import logging
from datetime import datetime

from .getTickersData import get_tickers_data
from .output import filter_and_enrich_data
from ..models.analysis import AnalysisFilter

def save_data_to_json(data: dict, file_prefix: str) -> str:
    """辞書データをタイムスタンプ付きのJSONファイルに保存します。

    Args:
        data (dict): 保存するデータを含む辞書。
        file_prefix (str): ファイル名の接頭辞（例: "raw_analysis"）。

    Returns:
        str: 保存されたファイルのパス。

    Raises:
        IOError: ファイルの書き込みに失敗した場合。
    """
    results_dir = 'data/results'
    if not os.path.exists(results_dir):
        os.makedirs(results_dir)
    
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
    file_path = os.path.join(results_dir, f"{file_prefix}_{timestamp}.json")
    
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        logging.info(f"Successfully saved data to {file_path}")
        return file_path
    except IOError as e:
        logging.error(f"Failed to write to file {file_path}: {e}")
        raise

def run_analysis_task(filters: AnalysisFilter):
    """株価分析のコアタスクを（バックグラウンドで）実行します。

    データの取得、分析、フィルタリング、保存までの一連の処理を担当します。

    Args:
        filters (AnalysisFilter): フィルタリング条件を定義したPydanticモデル。
    """
    logging.info("Starting stock analysis task...")
    
    raw_data = get_tickers_data()
    if not raw_data:
        logging.error("Failed to get tickers data. Aborting task.")
        return
    save_data_to_json(raw_data, "raw_analysis")

    enriched_data = filter_and_enrich_data(
        data=raw_data,
        rsi_decision=filters.rsi_decision,
        deviation_25_decision=filters.deviation_25_decision,
        sma_75_decision=filters.sma_75_decision
    )
    if not enriched_data:
        logging.warning("No data matched the filter criteria.")
    else:
        save_data_to_json(enriched_data, "enriched_output")
    
    logging.info("Stock analysis task finished.")
