import sys
import os
import json
import yfinance as yf
from datetime import datetime
import logging

# ロギング設定
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levellevelname)s - %(message)s')

def filter_and_enrich_data(data, rsi_decision=None, deviation_25_decision=None, sma_75_decision=None):
    """指定された条件に基づき、分析済み株価データをフィルタリングし、企業情報を付与し、スコア順にソートします。

    Args:
        data (dict): `get_tickers_data`から得られる、分析済みの株価データ。
        rsi_decision (list, optional): フィルタリング条件とするRSIの投資判断シグナル。
        deviation_25_decision (str, optional): フィルタリング条件とする25日移動平均乖離率の投資判断シグナル。
        sma_75_decision (str, optional): フィルタリング条件とする75日移動平均線の投資判断シグナル。

    Returns:
        list: フィルタリング・情報付加され、スコア順にソートされた銘柄データのリスト。
    """
    filtered_data = {}

    for ticker, metrics in data.items():
        # 日経平均は企業情報の付与対象外とする (スコアは付いている場合がある)
        if ticker == "^N225":
            continue

        signals = metrics.get("signals", {})
        rsi_match = (rsi_decision is None) or (signals.get("RSI") in rsi_decision)
        deviation_25_match = (deviation_25_decision is None) or (signals.get("Divergence_25d") == deviation_25_decision)
        sma_75_match = (sma_75_decision is None) or (signals.get("MA75_Trend") == sma_75_decision)

        if rsi_match and deviation_25_match and sma_75_match:
            try:
                ticker_yf = f"{ticker}.T"
                ticker_obj = yf.Ticker(ticker_yf)
                info = ticker_obj.info
                selected_fields = ["website", "industry", "sector", "longBusinessSummary", "shortName", "longName", "recommendationKey"]
                
                enriched_metrics = metrics.copy()
                enriched_metrics['info'] = {field: info.get(field, None) for field in selected_fields}
                filtered_data[ticker] = enriched_metrics

            except Exception as e:
                logging.error(f"Could not fetch 'info' for {ticker}: {e}")
                filtered_data[ticker] = metrics

    # スコアに基づいてソート
    # filtered_data.values()をリストに変換し、scoreキーで降順ソート
    sorted_list = sorted(list(filtered_data.values()), key=lambda item: item.get('score', 0), reverse=True)

    # 日経平均が存在する場合は、リストの先頭に追加する
    if "^N225" in data:
        nikkei_data = data["^N225"]
        # 形式の一貫性のためにtickerキーを追加しておく
        if 'ticker' not in nikkei_data:
            nikkei_data['ticker'] = "^N225"
        sorted_list.insert(0, nikkei_data)

    return sorted_list
