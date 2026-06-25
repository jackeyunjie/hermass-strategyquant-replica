"""TimescaleDB 时序数据存储客户端"""

import os
from datetime import datetime
from typing import List, Optional, Dict, Any

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker


class TimescaleDBClient:
    """TimescaleDB 时序数据存储客户端

    使用 PostgreSQL + TimescaleDB hypertable 存储行情数据。
    """

    def __init__(self, database_url: Optional[str] = None):
        self.database_url = database_url or os.getenv("DATABASE_URL")
        if not self.database_url:
            raise ValueError("Database URL not provided")
        self.engine = create_engine(self.database_url.replace("+asyncpg", ""))
        self.Session = sessionmaker(bind=self.engine)

    # ──────────────────────────── 表初始化 ────────────────────────────

    def init_tables(self):
        """初始化 hypertable 结构"""
        with self.engine.connect() as conn:
            # 创建 K 线数据表
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS market_data (
                    time TIMESTAMPTZ NOT NULL,
                    symbol TEXT NOT NULL,
                    timeframe TEXT NOT NULL,
                    open DOUBLE PRECISION,
                    high DOUBLE PRECISION,
                    low DOUBLE PRECISION,
                    close DOUBLE PRECISION,
                    volume DOUBLE PRECISION,
                    amount DOUBLE PRECISION,
                    adj_factor DOUBLE PRECISION DEFAULT 1.0,
                    PRIMARY KEY (time, symbol, timeframe)
                );
            """))

            # 转换为 hypertable
            conn.execute(text("""
                SELECT create_hypertable('market_data', 'time', 
                    if_not_exists => TRUE,
                    chunk_time_interval => INTERVAL '7 days'
                );
            """))

            # 创建索引
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_market_data_symbol 
                ON market_data (symbol, timeframe, time DESC);
            """))

            conn.commit()

    # ──────────────────────────── 数据写入 ────────────────────────────

    def insert_data(self, df: pd.DataFrame, symbol: str, timeframe: str = "D1"):
        """将 DataFrame 写入时序数据库

        Args:
            df: DataFrame 包含 time, open, high, low, close, volume, amount
            symbol: 股票代码
            timeframe: 周期 (D1, M1, M5, ...)
        """
        if df.empty:
            return

        df = df.copy()
        df["symbol"] = symbol
        df["timeframe"] = timeframe

        # 统一列名
        column_map = {
            "trade_date": "time",
            "trade_time": "time",
        }
        df.rename(columns=column_map, inplace=True, errors="ignore")

        # 确保 time 列是 datetime
        df["time"] = pd.to_datetime(df["time"])

        # 写入数据库
        df.to_sql(
            "market_data",
            self.engine,
            if_exists="append",
            index=False,
            method="multi",
        )

    # ──────────────────────────── 数据查询 ────────────────────────────

    def query_data(
        self,
        symbol: str,
        start: datetime,
        end: datetime,
        timeframe: str = "D1",
    ) -> pd.DataFrame:
        """查询单只股票历史数据

        Args:
            symbol: 股票代码
            start: 起始时间
            end: 结束时间
            timeframe: 周期

        Returns:
            DataFrame 按时间正序排列
        """
        query = """
            SELECT time, open, high, low, close, volume, amount
            FROM market_data
            WHERE symbol = :symbol
              AND timeframe = :timeframe
              AND time BETWEEN :start AND :end
            ORDER BY time ASC
        """
        with self.engine.connect() as conn:
            df = pd.read_sql(
                text(query),
                conn,
                params={
                    "symbol": symbol,
                    "timeframe": timeframe,
                    "start": start,
                    "end": end,
                },
            )
        return df

    def query_batch(
        self,
        symbols: List[str],
        start: datetime,
        end: datetime,
        timeframe: str = "D1",
    ) -> Dict[str, pd.DataFrame]:
        """批量查询多只股票数据"""
        results = {}
        for symbol in symbols:
            results[symbol] = self.query_data(symbol, start, end, timeframe)
        return results

    # ──────────────────────────── 数据管理 ────────────────────────────

    def get_data_coverage(self, symbol: str, timeframe: str = "D1") -> Dict[str, Any]:
        """获取某只股票的数据覆盖情况"""
        query = """
            SELECT 
                MIN(time) as earliest,
                MAX(time) as latest,
                COUNT(*) as total_rows
            FROM market_data
            WHERE symbol = :symbol AND timeframe = :timeframe
        """
        with self.engine.connect() as conn:
            result = conn.execute(
                text(query),
                {"symbol": symbol, "timeframe": timeframe},
            ).fetchone()

        return {
            "symbol": symbol,
            "timeframe": timeframe,
            "earliest": result.earliest,
            "latest": result.latest,
            "total_rows": result.total_rows,
        }

    def delete_data(self, symbol: str, timeframe: str, start: datetime, end: datetime):
        """删除指定范围内的数据"""
        query = """
            DELETE FROM market_data
            WHERE symbol = :symbol
              AND timeframe = :timeframe
              AND time BETWEEN :start AND :end
        """
        with self.engine.connect() as conn:
            conn.execute(
                text(query),
                {
                    "symbol": symbol,
                    "timeframe": timeframe,
                    "start": start,
                    "end": end,
                },
            )
            conn.commit()
