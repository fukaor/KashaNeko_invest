import sys
import os
import yfinance as yf
import json
import pandas as pd
import pandas_ta as ta
import logging
import warnings
from datetime import datetime

warnings.filterwarnings("ignore", category=FutureWarning)

TARGET_TIME = os.environ.get("TARGET_TIME", '15:00')
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def read_tickers_from_csv(csv_path='/app/data/csv/tickers.csv'):
    """CSVファイルからティッカーシンボルのリストを読み込みます。"""
    try:
        df = pd.read_csv(csv_path, header=None, dtype=str)
        tickers = df[0].dropna().tolist()
        logging.info("CSVからティッカーを正常に読み込みました。")
        return tickers
    except Exception as e:
        logging.error(f"CSVファイルの読み込みでエラーが発生しました: {e}")
        return None

def download_stock_data(tickers, period="100d", interval="1d"):
    """yfinanceを使用して、指定されたティッカーリストの株価データをダウンロードします。"""
    try:
        multi_data = yf.download(tickers, period=period, interval=interval)
        intra_day_data = yf.download(tickers, period="1d", interval="1m")
        logging.info("株価データのダウンロードが成功しました。")
        return multi_data, intra_day_data
    except Exception as e:
        logging.error(f"株価データのダウンロードでエラーが発生しました: {e}")
        return None, None

def calculate_metrics_for_ticker(ticker, multi_data, intra_day_data):
    """単一のティッカーについて、各種テクニカル指標と総合スコアを計算します。"""
    try:
        df = pd.DataFrame({
            'high': multi_data['High'][ticker],
            'low': multi_data['Low'][ticker],
            'close': multi_data['Close'][ticker],
            'volume': multi_data['Volume'][ticker]
        }).dropna()

        if len(df) < 75:
            logging.warning(f"{ticker}は75日分のデータが不足しているため、スキップします。")
            return None

        price_at_time = df['close'].iloc[-1]
        if not intra_day_data.empty and ticker in intra_day_data['Close'].columns:
            data_today = intra_day_data['Close'][ticker].dropna()
            if not data_today.empty:
                target_time_data = data_today.at_time(pd.Timestamp(TARGET_TIME, tz='Asia/Tokyo').time())
                if not target_time_data.empty:
                    price_at_time = target_time_data.iloc[0]
                else:
                    closest_previous_time_data = data_today[data_today.index < pd.Timestamp(TARGET_TIME, tz='Asia/Tokyo')]
                    if not closest_previous_time_data.empty:
                        price_at_time = closest_previous_time_data.iloc[-1]
        
        df.loc[df.index[-1], 'close'] = price_at_time

        # Calculate all indicators using pandas-ta
        df.ta.rsi(length=14, append=True)
        df.ta.sma(length=25, append=True)
        df.ta.sma(length=75, append=True)
        df.ta.macd(fast=12, slow=26, signal=9, append=True)
        df.ta.adx(length=14, append=True)

        # Extract latest values
        latest = df.iloc[-1]
        rsi = latest.get('RSI_14')
        sma_25 = latest.get('SMA_25')
        sma_75 = latest.get('SMA_75')
        previous_sma_75 = df['SMA_75'].iloc[-2]
        macd_line = latest.get('MACD_12_26_9')
        macd_signal = latest.get('MACDs_12_26_9')
        adx = latest.get('ADX_14')
        dmp = latest.get('DMP_14')
        dmn = latest.get('DMN_14')

        if any(v is None for v in [rsi, sma_25, sma_75, macd_line, macd_signal, adx, dmp, dmn]):
            logging.warning(f"{ticker}の指標計算に必要なデータが不足しています。")
            return None

        deviation_rate_25 = ((price_at_time - sma_25) / sma_25) * 100
        trend = "Upward" if sma_75 > previous_sma_75 else "Downward" if sma_75 < previous_sma_75 else "No change"

        # --- Signal Generation and Scoring ---
        buy_score = 0
        short_score = 0
        signals = {}

        # RSI Scoring
        if rsi < 25: (signals['RSI'], buy_score) = ('買い', buy_score + 2)
        elif 25 <= rsi < 40: (signals['RSI'], buy_score) = ('買い準備', buy_score + 1)
        elif rsi > 75: (signals['RSI'], short_score) = ('売り', short_score + 2)
        elif 60 <= rsi <= 75: (signals['RSI'], short_score) = ('売り準備', short_score + 1)
        else: signals['RSI'] = '中立'

        # 25-day Divergence Scoring
        if deviation_rate_25 <= -5: (signals['Divergence_25d'], buy_score) = ('買い', buy_score + 2)
        elif deviation_rate_25 >= 5: (signals['Divergence_25d'], short_score) = ('売り', short_score + 2)
        else: signals['Divergence_25d'] = '中立'

        # 75-day MA Trend Scoring
        signals['MA75_Trend'] = trend
        if trend == "Upward": buy_score += 1
        elif trend == "Downward": short_score += 1

        # MACD Scoring
        if macd_line > macd_signal: (signals['MACD'], buy_score) = ('買い', buy_score + 2)
        else: (signals['MACD'], short_score) = ('売り', short_score + 2)

        # DMI Scoring
        if dmp > dmn: (signals['DMI'], buy_score) = ('ゴールデンクロス', buy_score + 2)
        else: (signals['DMI'], short_score) = ('デッドクロス', short_score + 2)
        
        # ADX Scoring
        if adx > 25 and dmp > dmn: (signals['ADX'], buy_score) = ('強い上昇トレンド', buy_score + 1)
        elif adx > 25 and dmp < dmn: (signals['ADX'], short_score) = ('強い下降トレンド', short_score + 1)
        else: signals['ADX'] = 'トレンドレス'

        return {
            "ticker": ticker,
            "price": price_at_time,
            "rsi": rsi,
            "deviation_rate_25": deviation_rate_25,
            "trend": trend,
            "MACD": {"line": macd_line, "signal": macd_signal},
            "DMI": {"dmp": dmp, "dmn": dmn},
            "ADX": adx,
            "Volume": df['volume'].iloc[-1],
            "signals": signals,
            "buy_score": buy_score,
            "short_score": short_score
        }
    except Exception as e:
        logging.error(f"{ticker}のデータ処理でエラーが発生しました: {e}")
        return None

def get_tickers_data():
    """ティッカーリストの読み込み、株価データのダウンロード、テクニカル指標の計算までの一連の処理を実行します。"""
    tickers = read_tickers_from_csv()
    if tickers is None: return None

    yf_tickers = [f"{t}.T" if not t.startswith('^') else t for t in tickers]
    multi_data, intra_day_data = download_stock_data(yf_tickers)
    if multi_data is None or intra_day_data is None or multi_data.empty:
        logging.error('株価データのダウンロードに失敗しました、またはデータが空です。')
        return None

    results = {}
    for ticker, ticker_yf in zip(tickers, yf_tickers):
        if ticker_yf not in multi_data['Close'].columns:
            logging.warning(f"ティッカー {ticker_yf} のデータがダウンロードされませんでした。スキップします。")
            continue
        
        metrics = calculate_metrics_for_ticker(ticker_yf, multi_data, intra_day_data)
        if metrics:
            results[ticker] = metrics

    if not results:
        logging.info("分析対象の銘柄データがありませんでした。")
    return results