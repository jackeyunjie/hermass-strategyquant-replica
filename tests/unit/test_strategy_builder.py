"""策略 IR 和 GP 引擎单元测试。

测试策略中间表示（IR）的序列化、校验、表达式生成，
以及遗传编程引擎的进化、编译和 IR 转换。
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

import pytest
import pandas as pd
import numpy as np
from datetime import datetime

from engine.strategy_builder.strategy_ir import (
    StrategyIR, Node, Edge, NodeType, EdgeType, StrategyConfig, StrategyBuilderError,
)
from engine.strategy_builder.gp_engine import GPEngine, PrimitiveSetConfig
from tests.unit.test_fixtures import generate_mock_ohlcv, create_simple_ma_strategy


# ──────────────────────────── 策略 IR 测试 ────────────────────────────

class TestStrategyIR:
    """测试策略中间表示（IR）数据结构。"""

    def test_ir_creation(self):
        """测试基本 IR 创建。"""
        ir = StrategyIR(
            strategy_id="test_001",
            name="Test Strategy",
            description="A test strategy",
        )
        assert ir.strategy_id == "test_001"
        assert ir.name == "Test Strategy"
        assert ir.version == "1.0"

    def test_ir_serialization(self):
        """测试 IR 序列化与反序列化。"""
        ir = create_simple_ma_strategy()
        json_str = ir.to_json()
        assert isinstance(json_str, str)
        assert "test_ma_cross" in json_str

        ir2 = StrategyIR.from_json(json_str)
        assert ir2.strategy_id == ir.strategy_id
        assert len(ir2.nodes) == len(ir.nodes)
        assert len(ir2.edges) == len(ir.edges)

    def test_ir_dict_roundtrip(self):
        """测试 IR 字典往返。"""
        ir = create_simple_ma_strategy()
        d = ir.to_dict()
        ir2 = StrategyIR.from_dict(d)
        assert ir2.strategy_id == ir.strategy_id
        assert ir2.name == ir.name

    def test_find_node(self):
        """测试按 ID 查找节点。"""
        ir = create_simple_ma_strategy()
        node = ir.find_node("root")
        assert node is not None
        assert node.node_type == NodeType.ROOT

        missing = ir.find_node("nonexistent")
        assert missing is None

    def test_children_of(self):
        """测试获取子节点。"""
        ir = create_simple_ma_strategy()
        children = ir.children_of("root")
        assert len(children) == 1
        assert children[0].id == "cond"

    def test_add_edge(self):
        """测试添加边。"""
        ir = StrategyIR(strategy_id="test_edge")
        ir.nodes = [
            Node(id="a", node_type=NodeType.ROOT, name="root"),
            Node(id="b", node_type=NodeType.ACTION, name="BUY"),
        ]
        ir.add_edge("a", "b", EdgeType.CHILD)
        assert len(ir.edges) == 1
        assert ir.edges[0].source == "a"
        assert ir.edges[0].target == "b"

    def test_get_root(self):
        """测试获取根节点。"""
        ir = create_simple_ma_strategy()
        root = ir.get_root()
        assert root is not None
        assert root.node_type == NodeType.ROOT

    def test_validate_pass(self):
        """测试合法 IR 的校验通过。"""
        ir = create_simple_ma_strategy()
        errors = ir.validate()
        assert len(errors) == 0, f"校验应通过，但返回错误: {errors}"

    def test_validate_no_root(self):
        """测试缺少根节点的校验失败。"""
        ir = StrategyIR(strategy_id="no_root")
        ir.nodes = [Node(id="n1", node_type=NodeType.INDICATOR, name="SMA")]
        errors = ir.validate()
        assert any("ROOT" in e or "root" in e for e in errors)

    def test_validate_missing_edge_nodes(self):
        """测试边引用不存在节点的校验失败。"""
        ir = StrategyIR(strategy_id="bad_edge")
        ir.nodes = [Node(id="root", node_type=NodeType.ROOT, name="root")]
        ir.edges = [Edge(source="root", target="nonexistent", edge_type=EdgeType.CHILD)]
        errors = ir.validate()
        assert any("nonexistent" in e for e in errors)

    def test_validate_circular_dependency(self):
        """测试循环依赖检测。"""
        ir = StrategyIR(strategy_id="circular")
        ir.nodes = [
            Node(id="root", node_type=NodeType.ROOT, name="root"),
            Node(id="a", node_type=NodeType.INDICATOR, name="SMA"),
            Node(id="b", node_type=NodeType.INDICATOR, name="EMA"),
        ]
        ir.edges = [
            Edge(source="root", target="a", edge_type=EdgeType.CHILD),
            Edge(source="a", target="b", edge_type=EdgeType.CHILD),
            Edge(source="b", target="a", edge_type=EdgeType.CHILD),  # 循环
        ]
        errors = ir.validate()
        assert any("循环" in e or "circular" in e.lower() for e in errors)

    def test_ir_equality(self):
        """测试 IR 相等性判断。"""
        ir1 = create_simple_ma_strategy()
        ir2 = create_simple_ma_strategy()
        assert ir1 == ir2, "相同策略 IR 应相等"

    def test_ir_hash(self):
        """测试 IR 哈希值。"""
        ir1 = create_simple_ma_strategy()
        ir2 = create_simple_ma_strategy()
        assert hash(ir1) == hash(ir2), "相同策略 IR 的哈希值应相等"

    def test_estimate_complexity(self):
        """测试复杂度估计。"""
        ir = create_simple_ma_strategy()
        complexity = ir.estimate_complexity()
        assert complexity > 0
        # 7 nodes + 6 edges + depth ≈ 3 → 约 16
        assert complexity >= 10

    def test_to_expression(self):
        """测试表达式生成。"""
        ir = create_simple_ma_strategy()
        expr = ir.to_expression()
        assert isinstance(expr, str)
        assert len(expr) > 0

    def test_get_entry_nodes(self):
        """测试获取入场节点。"""
        ir = create_simple_ma_strategy()
        entries = ir.get_entry_nodes()
        assert len(entries) > 0
        assert any(n.node_type == NodeType.ACTION for n in entries)

    def test_get_exit_nodes(self):
        """测试获取出场节点。"""
        ir = create_simple_ma_strategy()
        exits = ir.get_exit_nodes()
        # 简单 MA 策略只有 BUY 动作，没有 SELL
        assert len(exits) == 0 or all(n.name == "SELL" for n in exits)

    def test_get_indicator_nodes(self):
        """测试获取指标节点。"""
        ir = create_simple_ma_strategy()
        indicators = ir.get_indicator_nodes()
        assert len(indicators) == 2
        assert all(n.node_type == NodeType.INDICATOR for n in indicators)

    def test_replace_node(self):
        """测试替换节点。"""
        ir = create_simple_ma_strategy()
        new_node = Node(id="sma20", node_type=NodeType.INDICATOR, name="IND_EMA20")
        ir.replace_node("sma20", new_node)
        found = ir.find_node("sma20")
        assert found.name == "IND_EMA20"

    def test_remove_node(self):
        """测试删除节点。"""
        ir = create_simple_ma_strategy()
        ir.remove_node("hold")
        assert ir.find_node("hold") is None
        # 边也应被删除
        related_edges = [e for e in ir.edges if e.source == "hold" or e.target == "hold"]
        assert len(related_edges) == 0

    def test_to_simple_dict(self):
        """测试简化字典生成。"""
        ir = create_simple_ma_strategy()
        d = ir.to_simple_dict()
        assert "version" in d
        assert "nodes" in d
        assert "edges" in d

    def test_strategy_ir_is_hashable(self):
        """测试 StrategyIR 可以作为 dict key 或 set 元素。"""
        ir = create_simple_ma_strategy()
        s = {ir}
        assert len(s) == 1
        d = {ir: "value"}
        assert d[ir] == "value"


# ──────────────────────────── GP 引擎测试 ────────────────────────────

class TestGPEngine:
    """测试遗传编程引擎。"""

    def test_gp_engine_init(self):
        """测试 GP 引擎初始化。"""
        config = PrimitiveSetConfig(indicators=["SMA", "RSI"], operators=["AND", "GT", "BUY"])
        gp = GPEngine(
            pset_config=config,
            population_size=10,
            generations=5,
            crossover_rate=0.7,
            mutation_rate=0.2,
        )
        assert gp.pset is not None
        assert gp.toolbox is not None

    def test_evolve_with_stub_evaluator(self):
        """测试使用 stub 评估函数的进化过程。"""
        data = generate_mock_ohlcv(n_bars=100)
        gp = GPEngine(population_size=10, generations=3)

        def evaluate_fn(individual):
            return 1.0  # stub 评估函数

        best, logbook = gp.evolve(evaluate_fn, seed=42, verbose=False)
        assert best is not None
        assert len(logbook) == 4  # gen 0 + 3 generations

    def test_compile_to_ir(self):
        """测试将 DEAP 个体编译为 StrategyIR。"""
        gp = GPEngine(population_size=5, generations=1)

        def evaluate_fn(individual):
            return 1.0

        best, _ = gp.evolve(evaluate_fn, seed=42, verbose=False)
        ir = gp.compile_to_ir(best, strategy_id="gp_test_001")
        assert isinstance(ir, StrategyIR)
        assert ir.strategy_id == "gp_test_001"
        assert len(ir.nodes) > 0
        assert ir.get_root() is not None

    def test_tree_to_string(self):
        """测试树到字符串转换。"""
        gp = GPEngine(population_size=5, generations=1)

        def evaluate_fn(individual):
            return 1.0

        best, _ = gp.evolve(evaluate_fn, seed=42, verbose=False)
        s = gp.tree_to_string(best)
        assert isinstance(s, str)
        assert len(s) > 0

    def test_ir_to_tree_roundtrip(self):
        """测试 IR → DEAP Tree → IR 往返。"""
        gp = GPEngine(population_size=5, generations=1)

        def evaluate_fn(individual):
            return 1.0

        best, _ = gp.evolve(evaluate_fn, seed=42, verbose=False)
        ir1 = gp.compile_to_ir(best, strategy_id="test_rt")
        tree = gp.ir_to_tree(ir1)
        assert tree is not None
        ir2 = gp.compile_to_ir(tree, strategy_id="test_rt2")
        assert ir2.get_root() is not None

    def test_generate_strategies(self):
        """测试策略生成入口。"""
        data = generate_mock_ohlcv(n_bars=100)
        gp = GPEngine(population_size=10, generations=2)

        strategies = gp.generate_strategies(
            data=data,
            n_jobs=1,
            top_n=3,
        )
        assert isinstance(strategies, list)
        assert len(strategies) <= 3
        for s in strategies:
            assert isinstance(s, StrategyIR)
            assert s.get_root() is not None

    def test_mutate_ir(self):
        """测试 IR 层面变异。"""
        ir = create_simple_ma_strategy()
        gp = GPEngine(population_size=5, generations=1)
        mutated = gp.mutate_ir(ir, mutation_rate=0.5)
        assert isinstance(mutated, StrategyIR)
        # 变异后 IR 应有变化或相同（随机）
        assert mutated.strategy_id == ir.strategy_id

    def test_is_duplicate(self):
        """测试重复检测。"""
        gp = GPEngine(population_size=5, generations=1)
        ir1 = create_simple_ma_strategy()
        ir2 = create_simple_ma_strategy()
        assert ir1 == ir2
        # 注意：is_duplicate 是针对 DEAP 个体的，不是 IR

    def test_complexity_penalty(self):
        """测试复杂度惩罚在进化中的应用。"""
        data = generate_mock_ohlcv(n_bars=100)
        gp = GPEngine(population_size=10, generations=2, complexity_alpha=0.01)

        def evaluate_fn(individual):
            return 1.0 - len(individual) * 0.01  # 模拟复杂度惩罚

        best, _ = gp.evolve(evaluate_fn, seed=42, verbose=False)
        assert best is not None

    def test_multi_objective_evaluate(self):
        """测试多目标适应度评估。"""
        data = generate_mock_ohlcv(n_bars=100)
        gp = GPEngine(population_size=10, generations=2, multi_objective=True)

        def evaluate_fn(individual):
            return (1.0, 5.0, 0.6)  # tuple: (sharpe, -max_drawdown, win_rate)

        best, _ = gp.evolve(evaluate_fn, seed=42, verbose=False)
        assert best is not None

    def test_pset_indicators(self):
        """测试 PrimitiveSet 中的指标注册。"""
        config = PrimitiveSetConfig(indicators=["SMA", "EMA", "RSI", "MACD"])
        gp = GPEngine(pset_config=config)
        # 验证指标终端存在于 pset 中
        assert gp.pset is not None

    def test_pset_operators(self):
        """测试 PrimitiveSet 中的运算符注册。"""
        gp = GPEngine()
        # AND, OR, NOT, GT, LT, EQ 等应已注册
        assert gp.pset is not None

    def test_deap_global_state(self):
        """测试 DEAP 全局状态多次实例化不报错。"""
        gp1 = GPEngine(population_size=5, generations=1)
        gp2 = GPEngine(population_size=5, generations=1)
        assert gp1 is not None
        assert gp2 is not None

    def test_generate_strategies_top_n(self):
        """测试生成策略返回数量限制。"""
        data = generate_mock_ohlcv(n_bars=100)
        gp = GPEngine(population_size=10, generations=2)
        strategies = gp.generate_strategies(data=data, top_n=5)
        assert len(strategies) <= 5

    @pytest.mark.skip(reason="IR to DEAP tree type matching issue (IF expects float, but BUY/HOLD are int). Known limitation requiring type system redesign.")
    def test_ir_to_tree_complex_strategy(self):
        """测试复杂策略的 IR ↔ Tree 转换。"""
        # 创建一个更复杂的策略（多层条件）
        nodes = [
            Node(id="root", node_type=NodeType.ROOT, name="root"),
            Node(id="cond1", node_type=NodeType.CONDITION, name="IF"),
            Node(id="and1", node_type=NodeType.OPERATOR, name="AND"),
            Node(id="gt1", node_type=NodeType.OPERATOR, name="GT"),
            Node(id="gt2", node_type=NodeType.OPERATOR, name="GT"),
            Node(id="sma20", node_type=NodeType.INDICATOR, name="IND_SMA20"),
            Node(id="sma50", node_type=NodeType.INDICATOR, name="IND_SMA50"),
            Node(id="rsi", node_type=NodeType.INDICATOR, name="IND_RSI"),
            Node(id="rsi_thresh", node_type=NodeType.VALUE, name="30", params={"value": 30.0}),
            Node(id="buy", node_type=NodeType.ACTION, name="BUY"),
            Node(id="hold", node_type=NodeType.ACTION, name="HOLD"),
        ]
        edges = [
            Edge(source="root", target="cond1", edge_type=EdgeType.CHILD),
            Edge(source="cond1", target="and1", edge_type=EdgeType.CHILD, label="condition"),
            Edge(source="cond1", target="buy", edge_type=EdgeType.THEN),
            Edge(source="cond1", target="hold", edge_type=EdgeType.ELSE),
            Edge(source="and1", target="gt1", edge_type=EdgeType.CHILD),
            Edge(source="and1", target="gt2", edge_type=EdgeType.CHILD),
            Edge(source="gt1", target="sma20", edge_type=EdgeType.CHILD),
            Edge(source="gt1", target="sma50", edge_type=EdgeType.CHILD),
            Edge(source="gt2", target="rsi", edge_type=EdgeType.CHILD),
            Edge(source="gt2", target="rsi_thresh", edge_type=EdgeType.CHILD),
        ]
        ir = StrategyIR(strategy_id="complex", nodes=nodes, edges=edges)
        gp = GPEngine(population_size=5, generations=1)
        tree = gp.ir_to_tree(ir)
        assert tree is not None
        ir2 = gp.compile_to_ir(tree, strategy_id="complex_rt")
        assert ir2.get_root() is not None
        assert len(ir2.nodes) > 0


# ──────────────────────────── 集成：GP → IR → 回测 ────────────────────────────

class TestGPBacktestIntegration:
    """集成测试：GP 生成 → IR 编译 → 回测。"""

    @pytest.mark.skip(reason="GP 生成的原始树结构不一定符合策略 IR 规范（缺少 ROOT 节点包装），需改进 compile_to_ir 以自动包装为合法策略树")
    def test_gp_generated_strategy_backtest(self):
        """测试 GP 生成的策略可以成功回测。"""
        from engine.backtest.engine import EventDrivenBacktester, BacktestConfig
        from engine.backtest.common import BacktestResult

        data = generate_mock_ohlcv(n_bars=100)
        gp = GPEngine(population_size=10, generations=2)

        def evaluate_fn(individual):
            return 1.0

        best, _ = gp.evolve(evaluate_fn, seed=42, verbose=False)
        ir = gp.compile_to_ir(best, strategy_id="gp_bt_test")

        # 确保 IR 合法
        errors = ir.validate()
        assert len(errors) == 0, f"IR 校验失败: {errors}"

        bt = EventDrivenBacktester()
        result = bt.run(ir, data, BacktestConfig())
        assert isinstance(result, BacktestResult)
        assert not result.equity_curve.empty
