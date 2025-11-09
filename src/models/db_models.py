from sqlalchemy import Column, Integer, String, Float, DateTime, JSON, Date, UniqueConstraint, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from ..database import Base

class TuningParameter(Base):
    """
    テクニカル分析のチューニングパラメータを格納するモデル。
    日付ごとにパラメータセットを持つことができる。
    """
    __tablename__ = "tuning_parameters"

    id = Column(Integer, primary_key=True, index=True)
    date = Column(Date, nullable=False, index=True)
    name = Column(String, index=True, nullable=False)
    value = Column(Float, nullable=False)
    description = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    __table_args__ = (UniqueConstraint('date', 'name', name='_date_name_uc'),)

class AnalysisRun(Base):
    """
    分析の実行単位を記録するモデル。
    """
    __tablename__ = "analysis_runs"

    id = Column(Integer, primary_key=True, index=True)
    analyzed_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    parameters_used = Column(JSON)
    
    results = relationship("AnalysisResult", back_populates="run")

class AnalysisResult(Base):
    """
    銘柄ごとの分析結果を格納するモデル。
    """
    __tablename__ = "analysis_results"

    id = Column(Integer, primary_key=True, index=True)
    analysis_run_id = Column(Integer, ForeignKey("analysis_runs.id"), nullable=False)
    ticker = Column(String, index=True, nullable=False)
    price = Column(Float)
    rsi = Column(Float)
    deviation_rate_25 = Column(Float)
    trend = Column(String)
    macd_line = Column(Float)
    macd_signal = Column(Float)
    dmi_dmp = Column(Float)
    dmi_dmn = Column(Float)
    adx = Column(Float)
    volume = Column(Float) # Volume can be large, Float is safer
    signals = Column(JSON)
    buy_score = Column(Integer)
    short_score = Column(Integer)

    run = relationship("AnalysisRun", back_populates="results")
