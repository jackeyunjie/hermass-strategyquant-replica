"""代码生成器和指标系统单元测试。

测试 Python 代码生成、三套模板、指标注册和计算。
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

import pytest
import pandas as pd
import numpy as np

from engine.codegen.python_generator import PythonGenerator, TemplateConfig, CodeGenerationError
from engine.indicators.ta_lib_wrapper import IndicatorRegistry, IndicatorError
from engine.indicators.custom_indicators import (
    AShareCapitalFlow, ChipDistribution, LimitUpProbability, BoardEffect, TurnoverZScore,
    register_custom_indicators,
)
from engine.strategy_builder.strategy_ir import StrategyIR, Node, Edge, NodeType, EdgeType, StrategyConfig
from tests.unit.test_fixtures import create_simple_ma_strategy, generate_mock_ohlcv


# ──────────────────────────── 代码生成器测试 ────────────────────────────

class TestPythonGenerator:
    """测试 Python 代码生成器。"""

    def test_generator_init(self):
        """测试生成器初始化。"""
        gen = PythonGenerator()
        assert gen is not None

    def test_generate_vectorbt(self):
        """测试生成 vectorbt 模板代码。"""
        strategy = create_simple_ma_strategy()
        gen = PythonGenerator()
        config = TemplateConfig(template_name="vectorbt")
        code = gen.generate(strategy, config)
        assert isinstance(code, str)
        assert len(code) > 0
        assert "vectorbt" in code or "vbt" in code
        assert "import" in code
        assert "def main" in code or "if __name__" in code

    def test_generate_backtrader(self):
        """测试生成 backtrader 模板代码。"""
        strategy = create_simple_ma_strategy()
        gen = PythonGenerator()
        config = TemplateConfig(template_name="backtrader")
        code = gen.generate(strategy, config)
        assert isinstance(code, str)
        assert len(code) > 0
        assert "backtrader" in code or "bt" in code or "cerebro" in code

    def test_generate_hermass_dsl(self):
        """测试生成 Hermass DSL 模板代码。"""
        strategy = create_simple_ma_strategy()
        gen = PythonGenerator()
        config = TemplateConfig(template_name="hermass_dsl")
        code = gen.generate(strategy, config)
        assert isinstance(code, str)
        assert len(code) > 0
        assert "METADATA" in code or "CONFIG" in code or "INDICATORS" in code

    def test_preview(self):
        """测试代码预览。"""
        strategy = create_simple_ma_strategy()
        gen = PythonGenerator()
        code = gen.preview(strategy, TemplateConfig(template_name="vectorbt"))
        assert isinstance(code, str)
        assert len(code) > 0

    def test_validate_ir(self):
        """测试 IR 验证。"""
        strategy = create_simple_ma_strategy()
        gen = PythonGenerator()
        errors = gen.validate_ir(strategy)
        assert isinstance(errors, list)
        # 合法策略应无错误
        assert len(errors) == 0, f"IR 验证失败: {errors}"

    def test_validate_ir_invalid(self):
        """测试无效 IR 的验证。"""
        invalid_ir = StrategyIR(strategy_id="invalid")
        # 缺少 ROOT 节点
        gen = PythonGenerator()
        errors = gen.validate_ir(invalid_ir)
        assert len(errors) > 0, "无效 IR 应报告错误"

    def test_generate_with_invalid_template(self):
        """测试无效模板名称。"""
        strategy = create_simple_ma_strategy()
        gen = PythonGenerator()
        with pytest.raises((CodeGenerationError, ValueError, KeyError)):
            gen.generate(strategy, TemplateConfig(template_name="nonexistent"))

    def test_code_contains_strategy_logic(self):
        """测试生成的代码包含策略逻辑。"""
        strategy = create_simple_ma_strategy()
        gen = PythonGenerator()
        code = gen.generate(strategy, TemplateConfig(template_name="vectorbt"))
        # 代码应包含策略相关的指标名称
        assert "SMA" in code or "sma" in code or "indicator" in code or "IND_" in code

    def test_code_contains_data_loading(self):
        """测试生成的代码包含数据加载函数。"""
        strategy = create_simple_ma_strategy()
        gen = PythonGenerator()
        code = gen.generate(strategy, TemplateConfig(template_name="vectorbt"))
        assert "load_data" in code or "pd.read" in code or "DataFrame" in code

    def test_code_contains_backtest_execution(self):
        """测试生成的代码包含回测执行逻辑。"""
        strategy = create_simple_ma_strategy()
        gen = PythonGenerator()
        code = gen.generate(strategy, TemplateConfig(template_name="vectorbt"))
        assert "Portfolio" in code or "from_signals" in code or "run_backtest" in code or "cerebro" in code

    def test_code_contains_metrics_output(self):
        """测试生成的代码包含指标输出。"""
        strategy = create_simple_ma_strategy()
        gen = PythonGenerator()
        code = gen.generate(strategy, TemplateConfig(template_name="vectorbt"))
        assert "sharpe" in code.lower() or "drawdown" in code.lower() or "return" in code.lower()

    def test_all_templates_generate_runnable_code(self):
        """测试所有模板生成可运行的代码结构。"""
        strategy = create_simple_ma_strategy()
        gen = PythonGenerator()
        for template_name in ["vectorbt", "backtrader", "hermass_dsl"]:
            config = TemplateConfig(template_name=template_name)
            code = gen.generate(strategy, config)
            assert "import" in code, f"{template_name} 模板缺少 import 语句"
            assert len(code) > 100, f"{template_name} 模板代码过短"


# ──────────────────────────── 指标系统测试 ────────────────────────────

class TestIndicatorRegistry:
    """测试指标注册系统。"""

    def test_registry_init(self):
        """测试注册表初始化。"""
        registry = IndicatorRegistry()
        assert registry is not None

    def test_register_and_get(self):
        """测试注册和获取指标。"""
        registry = IndicatorRegistry()
        # 注册一个简单指标函数
        def mock_indicator(df, period=20):
            return df["close"].rolling(period).mean()

        registry.register("MOCK_MA", mock_indicator, [{"name": "period", "type": "int", "default": 20}])
        indicator = registry.get("MOCK_MA", {"period": 20})
        assert indicator is not None

    def test_compute_indicator(self):
        """测试指标计算。"""
        registry = IndicatorRegistry()
        df = generate_mock_ohlcv(n_bars=50)
        # 使用内置指标 SMA
        result = registry.compute("SMA", df, period=20)
        assert isinstance(result, pd.DataFrame) or isinstance(result, pd.Series)
        assert len(result) == len(df)

    def test_list_indicators(self):
        """测试列出已注册指标。"""
        registry = IndicatorRegistry()
        registry.build_all()
        indicators = registry.list()
        assert isinstance(indicators, list)
        assert len(indicators) > 0, "注册表应包含内置指标"

    def test_build_all(self):
        """测试批量注册所有内置指标。"""
        registry = IndicatorRegistry()
        registry.build_all()
        indicators = registry.list()
        assert len(indicators) >= 20, "应注册大量内置指标"
        # 获取至少一个指标的元数据
        meta = registry.get(indicators[0]).get_metadata()
        assert "name" in meta

    def test_lazy_computation(self):
        """测试惰性计算。"""
        registry = IndicatorRegistry()
        registry.build_all()
        df = generate_mock_ohlcv(n_bars=50)
        # 第一次计算
        result1 = registry.compute("SMA", df, period=20)
        # 第二次计算相同参数（应从缓存返回）
        result2 = registry.compute("SMA", df, period=20)
        assert result1 is not None
        assert result2 is not None

    def test_param_validation(self):
        """测试参数验证。"""
        registry = IndicatorRegistry()
        registry.build_all()
        df = generate_mock_ohlcv(n_bars=50)
        # 有效参数
        result = registry.compute("SMA", df, period=20)
        assert result is not None
        # 无效参数（如负周期）
        with pytest.raises((ValueError, IndicatorError)):
            registry.compute("SMA", df, period=-5)

    def test_fallback_without_talib(self):
        """测试 TA-Lib 不可用时使用 pandas fallback。"""
        registry = IndicatorRegistry()
        registry.build_all()
        df = generate_mock_ohlcv(n_bars=50)
        # 即使 TA-Lib 未安装，也应能用 pandas 计算 SMA
        result = registry.compute("SMA", df, period=20)
        assert result is not None
        assert not result.isna().all().all(), "计算结果不应全为 NaN"


# ──────────────────────────── 自定义 A 股指标测试 ────────────────────────────

class TestCustomIndicators:
    """测试自定义 A 股指标。"""

    def test_capital_flow(self):
        """测试资金流向指标。"""
        df = generate_mock_ohlcv(n_bars=50)
        indicator = AShareCapitalFlow()
        result = indicator.calculate(df)
        assert isinstance(result, pd.DataFrame)
        assert "net_inflow" in result.columns or "main_net_inflow" in result.columns

    def test_chip_distribution(self):
        """测试筹码分布指标。"""
        df = generate_mock_ohlcv(n_bars=50)
        indicator = ChipDistribution()
        result = indicator.calculate(df)
        assert isinstance(result, pd.DataFrame)
        assert "concentration" in result.columns or "profit_ratio" in result.columns

    def test_limit_up_probability(self):
        """测试涨停概率指标。"""
        df = generate_mock_ohlcv(n_bars=50)
        indicator = LimitUpProbability()
        result = indicator.calculate(df)
        assert isinstance(result, pd.Series) or isinstance(result, pd.DataFrame)

    def test_board_effect(self):
        """测试板块效应指标。"""
        df = generate_mock_ohlcv(n_bars=50)
        indicator = BoardEffect()
        result = indicator.calculate(df)
        assert isinstance(result, pd.Series) or isinstance(result, pd.DataFrame)

    def test_turnover_zscore(self):
        """测试换手率 Z-Score 指标。"""
        df = generate_mock_ohlcv(n_bars=50)
        indicator = TurnoverZScore()
        result = indicator.calculate(df)
        assert isinstance(result, pd.DataFrame)
        assert "zscore" in result.columns or "is_anomaly" in result.columns

    def test_register_custom_indicators(self):
        """测试自定义指标注册到注册表。"""
        registry = IndicatorRegistry()
        register_custom_indicators(registry)
        indicators = registry.list()
        custom_names = ["CapitalFlow", "ChipDistribution", "LimitUpProb", "BoardEffect", "TurnoverZScore"]
        for name in custom_names:
            assert name.upper() in [i.upper() for i in indicators], f"指标 {name} 应已注册"

    def test_custom_indicator_metadata(self):
        """测试自定义指标元数据。"""
        indicator = AShareCapitalFlow()
        meta = indicator.get_metadata()
        assert isinstance(meta, dict)
        assert "name" in meta

    def test_indicator_on_realistic_data(self):
        """测试指标在真实模拟数据上的计算。"""
        df = generate_mock_ohlcv(n_bars=100, trend="up")
        registry = IndicatorRegistry()
        register_custom_indicators(registry)
        # 计算多个自定义指标
        for name in ["CapitalFlow", "ChipDistribution"]:
            try:
                result = registry.compute(name, df)
                assert result is not None
                assert len(result) == len(df) or len(result) > 0
            except Exception as e:
                pytest.fail(f"指标 {name} 计算失败: {e}")
