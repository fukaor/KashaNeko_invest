from fastapi import FastAPI
from src.routers import analysis

app = FastAPI()

app.include_router(analysis.router)

@app.get("/")
def read_root():
    return {"message": "Stock Analysis API"}
