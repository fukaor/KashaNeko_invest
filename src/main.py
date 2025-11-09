import logging
from logging.handlers import RotatingFileHandler
import os
from fastapi import FastAPI
from src.routers import analysis, stocks # stocksルーターをインポート
from src.database import engine, Base
from src.models import db_models

# ロギング設定
LOG_DIR = "data/logs"
LOG_FILE = os.path.join(LOG_DIR, "app.log")

# ログディレクトリが存在しない場合は作成
os.makedirs(LOG_DIR, exist_ok=True)

# ロガーの取得
logger = logging.getLogger()
logger.setLevel(logging.INFO) # デフォルトのログレベルを設定

# 既存のハンドラをクリア
if logger.hasHandlers():
    logger.handlers.clear()

# ファイルハンドラの設定
file_handler = RotatingFileHandler(LOG_FILE, maxBytes=10*1024*1024, backupCount=5, encoding='utf-8')
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
logger.addHandler(file_handler)

# コンソールハンドラも追加（Dockerログにも出力されるように）
console_handler = logging.StreamHandler()
console_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
logger.addHandler(console_handler)


app = FastAPI()

@app.on_event("startup")
def on_startup():
    # データベーステーブルを作成
    db_models.Base.metadata.create_all(bind=engine)
    logger.info("Database tables created or already exist.")

app.include_router(analysis.router)
app.include_router(stocks.router) # stocksルーターを追加

@app.get("/")
def read_root():
    logger.info("Root endpoint accessed.")
    return {"message": "Stock Analysis API"}