"""数据转换与预处理模块"""

from typing import Optional, List
from datetime import datetime

import pandas as pd
import numpy as np


class DataTransformer:
    """数据转换与预处理工具

    处理：复权、停牌标记、涨跌停标记、数据清洗、缺失值处理
    """

    # ──────────────────────────── 复权处理 ────────────────────────────

    @staticmethod
    def forward_adjust(df: pd.DataFrame, adj_factor: pd.Series) -> pd.DataFrame:
        """前复权处理

        Args:
            df: OHLCV DataFrame
            adj_factor: 复权因子序列（与 df 同索引）

        Returns:
            前复权后的 DataFrame
        """
        df_adj = df.copy()
        latest_factor = adj_factor.iloc[-1]
        for col in ["open", "high", "low", "close"]:
            if col in df_adj.columns:
                df_adj[col] = df_adj[col] * adj_factor / latest_factor
        return df_adj

    @staticmethod
    def backward_adjust(df: pd.DataFrame, adj_factor: pd.Series) -> pd.DataFrame:
        """后复权处理"""
        df_adj = df.copy()
        for col in ["open", "high", "low", "close"]:
            if col in df_adj.columns:
                df_adj[col] = df_adj[col] * adj_factor
        return df_adj

    # ──────────────────────────── 停牌标记 ────────────────────────────

    @staticmethod
    def mark_suspension(df: pd.DataFrame, suspension_dates: List[datetime]) -> pd.DataFrame:
        """标记停牌日

        Args:
            df: DataFrame (含 time/trade_date 列)
            suspension_dates: 停牌日期列表

        Returns:
            增加 is_suspended 列的 DataFrame
        """
        df = df.copy()
        time_col = "time" if "time" in df.columns else "trade_date"
        df[time_col] = pd.to_datetime(df[time_col])
        suspension_set = set(pd.to_datetime(suspension_dates))
        df["is_suspended"] = df[time_col].isin(suspension_set)
        return df

    # ──────────────────────────── 涨跌停标记 ────────────────────────────

    @staticmethod
    def mark_limit_up_down(df: pd.DataFrame, market: str = "main") -> pd.DataFrame:
        """标记涨跌停日

        A 股规则：
        - 主板/ST: 10%
        - 科创板/创业板: 20%
        - 北交所: 30%

        Args:
            df: DataFrame (含 close 列)
            market: 市场类型 (main, kcb, cyb, bse, st)
        """
        limit_map = {
            "main": 0.10,
            "st": 0.05,
            "kcb": 0.20,
            "cyb": 0.20,
            "bse": 0.30,
        }
        limit = limit_map.get(market, 0.10)

        df = df.copy()
        df["prev_close"] = df["close"].shift(1)
        df["change_pct"] = (df["close"] - df["prev_close"]) / df["prev_close"]
        df["is_limit_up"] = df["change_pct"] >= limit
        df["is_limit_down"] = df["change_pct"] <= -limit
        df.drop(columns=["prev_close"], inplace=True, errors="ignore")
        return df

    # ──────────────────────────── 缺失值处理 ────────────────────────────

    @staticmethod
    def fill_missing(
        df: pd.DataFrame,
        method: str = "ffill",
        limit: Optional[int] = None,
    ) -> pd.DataFrame:
        """缺失值填充

        Args:
            df: DataFrame
            method: ffill(前向填充), bfill(后向填充), linear(线性插值)
            limit: 最大连续填充天数
        """
        df = df.copy()
        if method == "ffill":
            df = df.ffill(limit=limit)
        elif method == "bfill":
            df = df.bfill(limit=limit)
        elif method == "linear":
            df = df.interpolate(method="linear", limit=limit)
        return df

    # ──────────────────────────── 数据清洗 ────────────────────────────

    @staticmethod
    def clean_ohlcv(df: pd.DataFrame) -> pd.DataFrame:
        """清洗 OHLCV 数据

        处理：
        - 异常价格（high < low, close < 0 等）
        - 零成交量过滤
        - 价格顺序修正（open <= high, low <= close <= high）
        """
        df = df.copy()

        # 移除零成交量
        if "volume" in df.columns:
            df = df[df["volume"] > 0]

        # 修正价格顺序
        for col in ["open", "high", "low", "close"]:
            if col in df.columns:
                df[col] = df[col].clip(lower=0.01)

        df["high"] = df[["open", "high", "low", "close"]].max(axis=1)
        df["low"] = df[["open", "high", "low", "close"]].min(axis=1)
        df["close"] = df["close"].clip(lower=df["low"], upper=df["high"])
        df["open"] = df["open"].clip(lower=df["low"], upper=df["high"])

        return df.reset_index(drop=True)

    # ──────────────────────────── 特征工程 ────────────────────────────

    @staticmethod
    def add_returns(df: pd.DataFrame) -> pd.DataFrame:
        """添加收益率列"""
        df = df.copy()
        df["returns"] = df["close"].pct_change()
        df["log_returns"] = np.log(df["close"] / df["close"].shift(1))
        return df

    @staticmethod
    def add_technical_features(df: pd.DataFrame) -> pd.DataFrame:
        """添加基础技术指标特征（stub）

        实际使用时接入 TA-Lib 或 engine/indicators/
        """
        df = df.copy()
        # 简单移动平均线
        df["ma_5"] = df["close"].rolling(5).mean()
        df["ma_10"] = df["close"].rolling(10).mean()
        df["ma_20"] = df["close"].rolling(20).mean()
        # 波动率
        df["volatility_20"] = df["returns"].rolling(20).std()
        return df
