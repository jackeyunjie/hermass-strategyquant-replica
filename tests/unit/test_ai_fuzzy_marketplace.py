import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from engine.indicators.marketplace import IndicatorMarketplace
from engine.results_ai import ResultsAIAnalyzer
from engine.strategy_builder.fuzzy_logic import FuzzyStrategyGenerator


def test_results_ai_generates_actionable_report():
    backtest = {
        "metrics": {
            "sharpe_ratio": 0.72,
            "max_drawdown_pct": -22.5,
            "profit_factor": 1.08,
            "win_rate": 39,
            "total_trades": 34,
            "total_return_pct": 8.1,
            "calmar_ratio": 0.4,
        },
        "trades": [{"pnl": 1}] * 34,
        "equity_curve": [{"date": f"2024-01-{i:02d}", "equity": 1000000 - i * 1000} for i in range(1, 20)],
    }

    report = ResultsAIAnalyzer().analyze(backtest, question="是否进入实盘候选池")

    assert report.risk_score > 0
    assert report.insights
    assert any(item.severity == "high" for item in report.insights)
    assert report.suggested_actions


def test_results_ai_accepts_flat_summary_with_numeric_trade_count():
    backtest = {
        "total_return": 15.0,
        "sharpe_ratio": 1.2,
        "max_drawdown": -8.0,
        "win_rate": 55,
        "profit_factor": 1.4,
        "trades": 100,
    }

    report = ResultsAIAnalyzer().analyze(backtest, question="生产烟测")

    assert report.prompt_context["metrics"]["total_trades"] == 100
    assert report.prompt_context["sample_size"]["trades"] == 0
    assert report.summary
    assert report.insights


def test_fuzzy_strategy_generator_outputs_ir_and_graph():
    generator = FuzzyStrategyGenerator()
    spec = generator.generate(template="balanced", name="Unit Fuzzy")

    strategy_ir = generator.to_strategy_ir(spec)
    graph = generator.to_frontend_graph(spec)

    assert strategy_ir.name == "Unit Fuzzy"
    assert strategy_ir.variables["fuzzy_spec"]["rules"]
    assert graph["nodes"]
    assert graph["edges"]


def test_marketplace_formula_indicator_calculates_dataframe():
    marketplace = IndicatorMarketplace()
    indicator = marketplace.install("trend-volume-confirm")
    df = pd.DataFrame({
        "open": np.linspace(10, 12, 80),
        "high": np.linspace(10.5, 12.5, 80),
        "low": np.linspace(9.5, 11.5, 80),
        "close": np.linspace(10, 13, 80),
        "volume": np.linspace(1000, 2400, 80),
        "amount": np.linspace(10000, 28000, 80),
    })

    result = indicator.calculate(df)

    assert "TrendVolumeConfirm" in result.columns
    assert len(result) == len(df)
    assert result["TrendVolumeConfirm"].notna().sum() > 0
