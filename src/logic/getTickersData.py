import sys
import os
import yfinance as yf
import json
import pandas as pd
import pandas_ta as ta
import logging
import warnings
from datetime import datetime, date
from sqlalchemy.orm import Session
from sqlalchemy import desc, func # funcをインポート
from ..models.db_models import TuningParameter

warnings.filterwarnings("ignore", category=FutureWarning)

TARGET_TIME = os.environ.get("TARGET_TIME", '15:00')
# logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s') # Removed

DEFAULT_PARAMS = {
    "rsi_length": 14,
    "rsi_buy_threshold": 25,
    "rsi_buy_prepare_threshold": 40,
    "rsi_sell_threshold": 75,
    "rsi_sell_prepare_threshold": 60,
    "sma_short_length": 25,
    "sma_long_length": 75,
    "deviation_buy_threshold": -5,
    "deviation_sell_threshold": 5,
    "macd_fast": 12,
    "macd_slow": 26,
    "macd_signal": 9,
    "adx_length": 14,
    "adx_threshold": 25
}

def get_tuning_parameters(db: Session) -> dict:
    """データベースから最新日付のチューニングパラメータを取得します。存在しない場合はデフォルト値を設定します。"""
    logging.info("Fetching tuning parameters from database...")
    params = {}
    try:
        latest_date = db.query(func.max(TuningParameter.date)).scalar()

        if not latest_date:
            logging.info("No tuning parameters found in DB. Seeding with default values for today.")
            today = date.today()
            for name, value in DEFAULT_PARAMS.items():
                param = TuningParameter(date=today, name=name, value=value, description="Default value")
                db.add(param)
            db.commit()
            logging.info(f"Seeded default parameters for date: {today}")
            latest_date = today

        parameters = db.query(TuningParameter).filter(TuningParameter.date == latest_date).all()

        for param in parameters:
            # 整数であるべきパラメータを変換
            if param.name in ["rsi_length", "sma_short_length", "sma_long_length", "macd_fast", "macd_slow", "macd_signal", "adx_length", "adx_threshold"]:
                params[param.name] = int(param.value)
            else:
                params[param.name] = param.value
        
        # パラメータセットに日付も追加しておく
        params['date'] = latest_date.isoformat()
        logging.info(f"Successfully loaded tuning parameters for date: {latest_date}")
        return params
    except Exception as e:
        db.rollback()
        logging.error(f"Failed to get tuning parameters from DB, using default values. Error: {e}")
        return DEFAULT_PARAMS


def read_tickers_from_csv(csv_path='/app/data/csv/tickers.csv'):
    """CSVファイルからティッカーシンボルのリストを読み込みます。"""
    logging.info(f"Reading tickers from {csv_path}...")
    try:
        df = pd.read_csv(csv_path, header=None, dtype=str)
        tickers = df[0].dropna().tolist()
        logging.info(f"Successfully read {len(tickers)} tickers from CSV.")
        return tickers
    except Exception as e:
        logging.error(f"Error reading CSV file: {e}")
        return None

def download_stock_data(tickers, period="100d", interval="1d"):
    """yfinanceを使用して、指定されたティッカーリストの株価データをダウンロードします。"""
    logging.info(f"Downloading stock data for {len(tickers)} tickers...")
    try:
        multi_data = yf.download(tickers, period=period, interval=interval)
        intra_day_data = yf.download(tickers, period="1d", interval="1m")
        logging.info("Stock data download successful.")
        return multi_data, intra_day_data
    except Exception as e:
        logging.error(f"Error downloading stock data: {e}")
        return None, None

def calculate_metrics_for_ticker(ticker, multi_data, intra_day_data, params):
    """単一のティッカーについて、各種テクニカル指標と総合スコアを計算します。"""
    logging.debug(f"Calculating metrics for {ticker}...")
    try:
        df = pd.DataFrame({
            'high': multi_data['High'][ticker],
            'low': multi_data['Low'][ticker],
            'close': multi_data['Close'][ticker],
            'volume': multi_data['Volume'][ticker]
        }).dropna()

        if len(df) < params["sma_long_length"]:
            logging.warning(f"Skipping {ticker}: insufficient data (less than {params['sma_long_length']} days).")
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
        df.ta.rsi(length=params["rsi_length"], append=True)
        df.ta.sma(length=params["sma_short_length"], append=True)
        df.ta.sma(length=params["sma_long_length"], append=True)
        df.ta.macd(fast=params["macd_fast"], slow=params["macd_slow"], signal=params["macd_signal"], append=True)
        df.ta.adx(length=params["adx_length"], append=True)

        # Extract latest values
        latest = df.iloc[-1]
        rsi = latest.get(f'RSI_{params["rsi_length"]}')
        sma_25 = latest.get(f'SMA_{params["sma_short_length"]}')
        sma_75 = latest.get(f'SMA_{params["sma_long_length"]}')
        previous_sma_75 = df[f'SMA_{params["sma_long_length"]}'].iloc[-2]
        macd_line = latest.get(f'MACD_{params["macd_fast"]}_{params["macd_slow"]}_{params["macd_signal"]}')
        macd_signal_val = latest.get(f'MACDs_{params["macd_fast"]}_{params["macd_slow"]}_{params["macd_signal"]}')
        adx = latest.get(f'ADX_{params["adx_length"]}')
        dmp = latest.get(f'DMP_{params["adx_length"]}')
        dmn = latest.get(f'DMN_{params["adx_length"]}')

        if any(v is None for v in [rsi, sma_25, sma_75, macd_line, macd_signal_val, adx, dmp, dmn]):
            logging.warning(f"Could not calculate all indicators for {ticker}. Skipping.")
            return None

        deviation_rate_25 = ((price_at_time - sma_25) / sma_25) * 100
        trend = "Upward" if sma_75 > previous_sma_75 else "Downward" if sma_75 < previous_sma_75 else "No change"

        # --- Signal Generation and Scoring ---
        buy_score = 0
        short_score = 0
        signals = {}

        # RSI Scoring
        if rsi < params["rsi_buy_threshold"]: (signals['RSI'], buy_score) = ('買い', buy_score + 2)
        elif params["rsi_buy_threshold"] <= rsi < params["rsi_buy_prepare_threshold"]: (signals['RSI'], buy_score) = ('買い準備', buy_score + 1)
        elif rsi > params["rsi_sell_threshold"]: (signals['RSI'], short_score) = ('売り', short_score + 2)
        elif params["rsi_sell_prepare_threshold"] <= rsi <= params["rsi_sell_threshold"]: (signals['RSI'], short_score) = ('売り準備', short_score + 1)
        else: signals['RSI'] = '中立'

        # 25-day Divergence Scoring
        if deviation_rate_25 <= params["deviation_buy_threshold"]: (signals['Divergence_25d'], buy_score) = ('買い', buy_score + 2)
        elif deviation_rate_25 >= params["deviation_sell_threshold"]: (signals['Divergence_25d'], short_score) = ('売り', short_score + 2)
        else: signals['Divergence_25d'] = '中立'

        # 75-day MA Trend Scoring
        signals['MA75_Trend'] = trend
        if trend == "Upward": buy_score += 1
        elif trend == "Downward": short_score += 1

        # MACD Scoring
        if macd_line > macd_signal_val: (signals['MACD'], buy_score) = ('買い', buy_score + 2)
        else: (signals['MACD'], short_score) = ('売り', short_score + 2)

        # DMI Scoring
        if dmp > dmn: (signals['DMI'], buy_score) = ('ゴールデンクロス', buy_score + 2)
        else: (signals['DMI'], short_score) = ('デッドクロス', short_score + 2)
        
        # ADX Scoring
        if adx > params["adx_threshold"] and dmp > dmn: (signals['ADX'], buy_score) = ('強い上昇トレンド', buy_score + 1)
        elif adx > params["adx_threshold"] and dmp < dmn: (signals['ADX'], short_score) = ('強い下降トレンド', short_score + 1)
        else: signals['ADX'] = 'トレンドレス'

        logging.debug(f"Successfully calculated metrics for {ticker}.")
        return {
            "ticker": ticker,
            "price": price_at_time,
            "rsi": rsi,
            "deviation_rate_25": deviation_rate_25,
            "trend": trend,
            "MACD": {"line": macd_line, "signal": macd_signal_val},
            "DMI": {"dmp": dmp, "dmn": dmn},
            "ADX": adx,
            "Volume": df['volume'].iloc[-1],
            "signals": signals,
            "buy_score": buy_score,
            "short_score": short_score,
            "parameters_used": params
        }
    except Exception as e:
        logging.error(f"Error processing data for {ticker}: {e}")
        return None

def get_tickers_data(db: Session):
    """ティッカーリストの読み込み、株価データのダウンロード、テクニカル指標の計算までの一連の処理を実行します。"""
    logging.info("Starting main data retrieval and analysis process...")
    params = get_tuning_parameters(db)
    
    tickers = read_tickers_from_csv()
    if tickers is None: 
        logging.error("Ticker list is empty. Aborting.")
        return None

    yf_tickers = [f"{t}.T" if not t.startswith('^') else t for t in tickers]
    multi_data, intra_day_data = download_stock_data(yf_tickers)
    if multi_data is None or intra_day_data is None or multi_data.empty:
        logging.error('Failed to download stock data or data is empty. Aborting.')
        return None

    results = {}
    logging.info(f"Starting analysis for {len(tickers)} tickers...")
    for ticker, ticker_yf in zip(tickers, yf_tickers):
        if ticker_yf not in multi_data['Close'].columns:
            logging.warning(f"Data for ticker {ticker_yf} not found in downloaded data. Skipping.")
            continue
        
        metrics = calculate_metrics_for_ticker(ticker_yf, multi_data, intra_day_data, params)
        if metrics:
            results[ticker] = metrics

    logging.info(f"Analysis complete. Successfully processed {len(results)} tickers.")
    return results