"""数据下载器抽象基类"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any
from datetime import datetime

import pandas as pd


class BaseDownloader(ABC):
    """数据下载器抽象基类

    所有数据源（Tushare、Yahoo Finance、Dukascopy 等）必须实现此接口。
    """

    @abstractmethod
    def download(self, symbol: str, start: str, end: str, **kwargs) -> pd.DataFrame:
        """下载单只股票数据

        Args:
            symbol: 股票代码
            start: 起始日期 (YYYY-MM-DD 或 YYYYMMDD)
            end: 结束日期
            **kwargs: 额外参数（周期、复权等）

        Returns:
            DataFrame 包含 OHLCV 数据
        """
        pass

    @abstractmethod
    def download_async(
        self, symbols: List[str], start: str, end: str, **kwargs
    ) -> Dict[str, pd.DataFrame]:
        """异步批量下载多只股票数据

        Args:
            symbols: 股票代码列表
            start: 起始日期
            end: 结束日期
            **kwargs: 额外参数

        Returns:
            Dict[symbol, DataFrame]
        """
        pass
