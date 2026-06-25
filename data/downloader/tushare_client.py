#!/usr/bin/env python3
"""
Tushare 数据下载器 — A 股行情数据获取

支持：日线、分钟线、Tick 数据
数据来源：Tushare Pro API
"""

import os
import asyncio
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta

import pandas as pd
import tushare as ts

from .base import BaseDownloader


class TushareDownloader(BaseDownloader):
    """Tushare Pro 数据下载器封装"""

    def __init__(self, token: Optional[str] = None):
        self.token = token or os.getenv("TUSHARE_TOKEN")
        if not self.token:
            raise ValueError("Tushare token not provided. Set TUSHARE_TOKEN env var.")
        ts.set_token(self.token)
        self.pro = ts.pro_api()

    # ──────────────────────────── 股票列表 ────────────────────────────

    def get_stock_list(self, market: str = "A") -> pd.DataFrame:
        """获取 A 股股票列表

        Returns:
            DataFrame: ts_code, symbol, name, area, industry, list_date, exchange
        """
        df = self.pro.stock_basic(exchange="", list_status="L")
        return df[["ts_code", "symbol", "name", "area", "industry", "list_date", "exchange"]]

    # ──────────────────────────── 日线数据 ────────────────────────────

    def get_daily(
        self,
        ts_code: str,
        start_date: str,
        end_date: str,
        adj: str = "qfq",  # 前复权
    ) -> pd.DataFrame:
        """获取单只股票日线数据

        Args:
            ts_code: 股票代码 (如 000001.SZ)
            start_date: 起始日期 (YYYYMMDD)
            end_date: 结束日期 (YYYYMMDD)
            adj: 复权类型 (qfq=前复权, hfq=后复权, None=不复权)

        Returns:
            DataFrame: trade_date, open, high, low, close, vol, amount
        """
        df = self.pro.daily(
            ts_code=ts_code,
            start_date=start_date,
            end_date=end_date,
        )
        if df.empty:
            return pd.DataFrame()

        df["trade_date"] = pd.to_datetime(df["trade_date"])
        df = df.sort_values("trade_date").reset_index(drop=True)

        # 复权处理
        if adj:
            adj_df = self.pro.adj_factor(ts_code=ts_code, start_date=start_date, end_date=end_date)
            if not adj_df.empty:
                adj_df["trade_date"] = pd.to_datetime(adj_df["trade_date"])
                df = df.merge(adj_df[["trade_date", "adj_factor"]], on="trade_date", how="left")
                if adj == "qfq":
                    for col in ["open", "high", "low", "close"]:
                        df[col] = df[col] * df["adj_factor"] / df["adj_factor"].iloc[-1]
                elif adj == "hfq":
                    for col in ["open", "high", "low", "close"]:
                        df[col] = df[col] * df["adj_factor"]
                df.drop(columns=["adj_factor"], inplace=True, errors="ignore")

        return df[["trade_date", "open", "high", "low", "close", "vol", "amount"]]

    # ──────────────────────────── 分钟线数据 ────────────────────────────

    def get_minutely(
        self,
        ts_code: str,
        start_date: str,
        end_date: str,
        freq: str = "1min",
    ) -> pd.DataFrame:
        """获取单只股票分钟线数据

        Args:
            ts_code: 股票代码
            start_date: 起始日期 (YYYYMMDD)
            end_date: 结束日期 (YYYYMMDD)
            freq: 频率 (1min, 5min, 15min, 30min, 60min)
        """
        df = self.pro.stk_mins(
            ts_code=ts_code,
            start_date=start_date,
            end_date=end_date,
            freq=freq,
        )
        if df.empty:
            return pd.DataFrame()

        df["trade_time"] = pd.to_datetime(df["trade_time"])
        df = df.sort_values("trade_time").reset_index(drop=True)
        return df[["trade_time", "open", "high", "low", "close", "vol", "amount"]]

    # ──────────────────────────── 批量下载 ────────────────────────────

    def download_batch(
        self,
        ts_codes: List[str],
        start_date: str,
        end_date: str,
        timeframe: str = "D",
    ) -> Dict[str, pd.DataFrame]:
        """批量下载多只股票数据

        Args:
            ts_codes: 股票代码列表
            start_date: 起始日期
            end_date: 结束日期
            timeframe: 周期 (D=日线, 1min=1分钟, 5min=5分钟, ...)

        Returns:
            Dict[str, DataFrame]: {ts_code: df}
        """
        results = {}
        for code in ts_codes:
            try:
                if timeframe == "D":
                    df = self.get_daily(code, start_date, end_date)
                else:
                    df = self.get_minutely(code, start_date, end_date, freq=timeframe)
                results[code] = df
                print(f"✓ Downloaded {code}: {len(df)} rows")
            except Exception as e:
                print(f"✗ Failed {code}: {e}")
                results[code] = pd.DataFrame()
        return results

    # ──────────────────────────── 辅助信息 ────────────────────────────

    def get_trade_calendar(self, start_date: str, end_date: str) -> pd.DataFrame:
        """获取交易日历"""
        return self.pro.trade_cal(
            exchange="SSE",
            start_date=start_date,
            end_date=end_date,
            is_open="1",
        )

    def get_suspended(self, ts_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        """获取停牌信息"""
        return self.pro.suspend_d(
            ts_code=ts_code,
            start_date=start_date,
            end_date=end_date,
        )

    def get_stocks_limit(self, trade_date: str) -> pd.DataFrame:
        """获取每日涨跌停统计"""
        return self.pro.limit_list(trade_date=trade_date)

    # ──────────────────────────── 抽象方法实现 ────────────────────────────

    def download(self, symbol: str, start: str, end: str, **kwargs) -> pd.DataFrame:
        """BaseDownloader 接口实现"""
        return self.get_daily(symbol, start, end, **kwargs)

    def download_async(self, symbols: List[str], start: str, end: str, **kwargs) -> Dict[str, pd.DataFrame]:
        """异步批量下载（简化实现，实际可优化）"""
        return self.download_batch(symbols, start, end, **kwargs)
