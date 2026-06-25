"""
策略改进器——自动改进策略的某部分。

支持入场、出场、过滤、止损、指标参数 5 个组件的定向改进，
以及多组件迭代优化。每次改进只改变一个组件，保持策略核心逻辑不变。
"""

from __future__ import annotations

import copy
import random
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from ..backtest.engine import BacktestResult, EventDrivenBacktester
from ..strategy_builder.strategy_ir import Node, NodeType, StrategyIR


class ImprovementError(Exception):
    """策略改进错误。"""
    pass


# 可用的指标替换池（用于入场/出场条件改进）
_INDICATOR_POOL: List[str] = [
    "MA", "EMA", "SMA", "RSI", "MACD", "BBANDS",
    "ATR", "CCI", "MOM", "WILLR", "STOCH", "ADX",
]

# 比较运算符池
_OPERATOR_POOL: List[str] = ["GT", "LT", "EQ", "GE", "LE"]

# 止损相关节点名模式
_STOPLOSS_PATTERNS: List[str] = ["stop", "loss", "atr", "trailing", "sl"]


class StrategyImprover:
    """策略改进器。

    实现 5 种定向改进操作（入场、出场、过滤、止损、指标参数），
    以及多组件迭代优化。改进逻辑：定位可改进组件 → 随机变异 → 回测评估 → 保留更好结果。

    Attributes:
        target_metric: 用于评估改进效果的指标（如 'sharpe_ratio'）。
        max_candidates: 每次改进尝试的候选变异数量。
        random_seed: 随机种子。
    """

    def __init__(
        self,
        target_metric: str = "sharpe_ratio",
        max_candidates: int = 5,
        n_iterations: int = 1,
        random_seed: Optional[int] = None,
    ) -> None:
        self.target_metric = target_metric
        self.max_candidates = max_candidates
        self.n_iterations = n_iterations
        if random_seed is not None:
            random.seed(random_seed)
            np.random.seed(random_seed)

    # ------------------------------------------------------------------
    # 评估器统一封装
    # ------------------------------------------------------------------
    def _evaluate(
        self,
        strategy_ir: StrategyIR,
        data: pd.DataFrame,
        evaluator: Optional[Callable[[StrategyIR, pd.DataFrame], Any]] = None,
    ) -> float:
        """统一评估接口。

        若 evaluator 返回 BacktestResult，则提取 target_metric；
        若返回数值，则直接使用。
        """
        if evaluator is None:
            result = EventDrivenBacktester().run(strategy_ir, data)
            return float(result.metrics.get(self.target_metric, 0.0))

        score = evaluator(strategy_ir, data)
        if isinstance(score, BacktestResult):
            return float(score.metrics.get(self.target_metric, 0.0))
        return float(score)

    # ------------------------------------------------------------------
    # 1. 入场条件改进
    # ------------------------------------------------------------------
    def improve_entry(
        self,
        strategy_ir: StrategyIR,
        data: pd.DataFrame,
        evaluator: Optional[Callable[[StrategyIR, pd.DataFrame], Any]] = None,
    ) -> Tuple[StrategyIR, Dict[str, Any]]:
        """仅改进入场条件，保留出场和核心逻辑不变。

        改进策略：
        - 替换入场指标（如 MA -> EMA）
        - 微调入场阈值
        - 翻转比较运算符（GT <-> LT）

        Args:
            strategy_ir: 原始策略 IR。
            data: 回测行情数据。
            evaluator: 评估回调，(IR, data) -> score / BacktestResult。

        Returns:
            (improved_ir, log): 改进后的 IR 和改进日志。
        """
        base_score = self._evaluate(strategy_ir, data, evaluator)
        best_ir = copy.deepcopy(strategy_ir)
        best_score = base_score
        best_log: Dict[str, Any] = {
            "operation": "improve_entry",
            "original_score": base_score,
            "new_score": base_score,
            "improvement_delta": 0.0,
            "description": "未找到可改进的入场节点",
            "changed_nodes": [],
        }

        # 定位入场相关节点（通往 BUY 的路径）
        entry_nodes = self._collect_entry_nodes(strategy_ir)
        if not entry_nodes:
            return best_ir

        candidates = self._generate_condition_candidates(
            strategy_ir, entry_nodes, "entry"
        )

        for cand_ir, changed_nodes, desc in candidates:
            try:
                score = self._evaluate(cand_ir, data, evaluator)
                if score > best_score:
                    best_score = score
                    best_ir = cand_ir
                    best_log["new_score"] = score
                    best_log["improvement_delta"] = score - base_score
                    best_log["description"] = desc
                    best_log["changed_nodes"] = changed_nodes
            except Exception:
                continue

        return best_ir

    # ------------------------------------------------------------------
    # 2. 出场条件改进
    # ------------------------------------------------------------------
    def improve_exit(
        self,
        strategy_ir: StrategyIR,
        data: pd.DataFrame,
        evaluator: Optional[Callable[[StrategyIR, pd.DataFrame], Any]] = None,
    ) -> Tuple[StrategyIR, Dict[str, Any]]:
        """仅改进出场条件，保留入场和核心逻辑不变。

        改进策略：
        - 替换出场指标
        - 微调出场阈值
        - 添加/移除出场条件

        Args:
            strategy_ir: 原始策略 IR。
            data: 回测行情数据。
            evaluator: 评估回调。

        Returns:
            (improved_ir, log): 改进后的 IR 和改进日志。
        """
        base_score = self._evaluate(strategy_ir, data, evaluator)
        best_ir = copy.deepcopy(strategy_ir)
        best_score = base_score
        best_log: Dict[str, Any] = {
            "operation": "improve_exit",
            "original_score": base_score,
            "new_score": base_score,
            "improvement_delta": 0.0,
            "description": "未找到可改进的出场节点",
            "changed_nodes": [],
        }

        exit_nodes = self._collect_exit_nodes(strategy_ir)
        if not exit_nodes:
            return best_ir

        candidates = self._generate_condition_candidates(
            strategy_ir, exit_nodes, "exit"
        )

        for cand_ir, changed_nodes, desc in candidates:
            try:
                score = self._evaluate(cand_ir, data, evaluator)
                if score > best_score:
                    best_score = score
                    best_ir = cand_ir
                    best_log["new_score"] = score
                    best_log["improvement_delta"] = score - base_score
                    best_log["description"] = desc
                    best_log["changed_nodes"] = changed_nodes
            except Exception:
                continue

        return best_ir

    # ------------------------------------------------------------------
    # 3. 过滤条件改进
    # ------------------------------------------------------------------
    def improve_filters(
        self,
        strategy_ir: StrategyIR,
        data: pd.DataFrame,
        evaluator: Optional[Callable[[StrategyIR, pd.DataFrame], Any]] = None,
    ) -> Tuple[StrategyIR, Dict[str, Any]]:
        """改进过滤条件（增加或删除指标过滤器）。

        改进策略：
        - 在入场条件上增加 AND 过滤器（如 RSI < 70）
        - 删除冗余的 AND 子条件

        Args:
            strategy_ir: 原始策略 IR。
            data: 回测行情数据。
            evaluator: 评估回调。

        Returns:
            (improved_ir, log): 改进后的 IR 和改进日志。
        """
        base_score = self._evaluate(strategy_ir, data, evaluator)
        best_ir = copy.deepcopy(strategy_ir)
        best_score = base_score
        best_log: Dict[str, Any] = {
            "operation": "improve_filters",
            "original_score": base_score,
            "new_score": base_score,
            "improvement_delta": 0.0,
            "description": "未找到可改进的过滤节点",
            "changed_nodes": [],
        }

        # 查找所有 AND 条件节点
        and_nodes = [
            n for n in strategy_ir.nodes
            if n.node_type == NodeType.OPERATOR and n.name == "AND"
        ]
        if not and_nodes:
            return best_ir

        candidates: List[Tuple[StrategyIR, List[str], str]] = []

        # 候选 1：删除一个 AND 子节点（简化过滤）
        for and_node in and_nodes:
            children = self._children_of(strategy_ir, and_node.id)
            if len(children) > 2:
                for child in children:
                    # 尝试删除该子节点，保持树有效
                    cand = self._remove_subtree(copy.deepcopy(strategy_ir), and_node.id, child.id)
                    if cand is not None:
                        candidates.append((cand, [and_node.id, child.id], f"删除 AND 子条件 {child.name}"))

        # 候选 2：添加一个简单过滤条件到 AND
        for and_node in and_nodes:
            cand = self._add_filter_to_and(copy.deepcopy(strategy_ir), and_node.id)
            if cand is not None:
                new_node_id = f"filter_{and_node.id}_{random.randint(1000,9999)}"
                candidates.append((cand, [and_node.id, new_node_id], f"添加 AND 过滤条件"))

        for cand_ir, changed_nodes, desc in candidates[: self.max_candidates]:
            try:
                score = self._evaluate(cand_ir, data, evaluator)
                if score > best_score:
                    best_score = score
                    best_ir = cand_ir
                    best_log["new_score"] = score
                    best_log["improvement_delta"] = score - base_score
                    best_log["description"] = desc
                    best_log["changed_nodes"] = changed_nodes
            except Exception:
                continue

        return best_ir

    # ------------------------------------------------------------------
    # 4. 止损条件改进
    # ------------------------------------------------------------------
    def improve_stoploss(
        self,
        strategy_ir: StrategyIR,
        data: pd.DataFrame,
        evaluator: Optional[Callable[[StrategyIR, pd.DataFrame], Any]] = None,
    ) -> Tuple[StrategyIR, Dict[str, Any]]:
        """改进止损条件（如 ATR 倍数调整）。

        查找名称包含 stop/loss/atr 等关键词的节点，
        对其数值参数进行 ±20% / ±40% 扰动。

        Args:
            strategy_ir: 原始策略 IR。
            data: 回测行情数据。
            evaluator: 评估回调。

        Returns:
            (improved_ir, log): 改进后的 IR 和改进日志。
        """
        base_score = self._evaluate(strategy_ir, data, evaluator)
        best_ir = copy.deepcopy(strategy_ir)
        best_score = base_score
        best_log: Dict[str, Any] = {
            "operation": "improve_stoploss",
            "original_score": base_score,
            "new_score": base_score,
            "improvement_delta": 0.0,
            "description": "未找到止损相关节点",
            "changed_nodes": [],
        }

        # 查找止损相关节点
        sl_nodes = self._find_stoploss_nodes(strategy_ir)
        if not sl_nodes:
            return best_ir

        candidates: List[Tuple[StrategyIR, List[str], str]] = []

        for node in sl_nodes:
            for key, value in node.params.items():
                if isinstance(value, (int, float)) and abs(float(value)) > 1e-12:
                    for factor in [0.8, 1.0, 1.2, 1.5]:
                        cand = copy.deepcopy(strategy_ir)
                        cand_node = cand.find_node(node.id)
                        if cand_node is None:
                            continue
                        new_val = float(value) * factor
                        if isinstance(value, int):
                            new_val = max(1, int(round(new_val)))
                        cand_node.params[key] = new_val
                        candidates.append((
                            cand,
                            [node.id],
                            f"调整止损节点 {node.name}.{key} = {value} -> {new_val}",
                        ))

        for cand_ir, changed_nodes, desc in candidates[: self.max_candidates]:
            try:
                score = self._evaluate(cand_ir, data, evaluator)
                if score > best_score:
                    best_score = score
                    best_ir = cand_ir
                    best_log["new_score"] = score
                    best_log["improvement_delta"] = score - base_score
                    best_log["description"] = desc
                    best_log["changed_nodes"] = changed_nodes
            except Exception:
                continue

        return best_ir

    # ------------------------------------------------------------------
    # 5. 指标参数改进
    # ------------------------------------------------------------------
    def improve_indicator_params(
        self,
        strategy_ir: StrategyIR,
        data: pd.DataFrame,
        evaluator: Optional[Callable[[StrategyIR, pd.DataFrame], Any]] = None,
    ) -> Tuple[StrategyIR, Dict[str, Any]]:
        """改进指标参数（如 MA 周期优化）。

        对 INDICATOR 节点的 period / lookback / window 等参数
        进行小规模网格搜索，保留最优结果。

        Args:
            strategy_ir: 原始策略 IR。
            data: 回测行情数据。
            evaluator: 评估回调。

        Returns:
            (improved_ir, log): 改进后的 IR 和改进日志。
        """
        base_score = self._evaluate(strategy_ir, data, evaluator)
        best_ir = copy.deepcopy(strategy_ir)
        best_score = base_score
        best_log: Dict[str, Any] = {
            "operation": "improve_indicator_params",
            "original_score": base_score,
            "new_score": base_score,
            "improvement_delta": 0.0,
            "description": "未找到可改进的指标参数",
            "changed_nodes": [],
        }

        # 收集所有 INDICATOR 节点及其周期参数
        indicator_params: List[Tuple[str, str, int]] = []
        for node in strategy_ir.nodes:
            if node.node_type == NodeType.INDICATOR:
                for key in ("period", "lookback", "window", "timeperiod"):
                    if key in node.params and isinstance(node.params[key], int):
                        indicator_params.append((node.id, key, node.params[key]))

        if not indicator_params:
            return best_ir

        # 对每个参数尝试附近值
        candidates: List[Tuple[StrategyIR, List[str], str]] = []
        for node_id, key, orig_val in indicator_params:
            for new_val in [
                max(1, orig_val - 5),
                max(1, orig_val - 2),
                orig_val + 2,
                orig_val + 5,
            ]:
                if new_val == orig_val:
                    continue
                cand = copy.deepcopy(strategy_ir)
                cand_node = cand.find_node(node_id)
                if cand_node is not None:
                    cand_node.params[key] = new_val
                    candidates.append((
                        cand,
                        [node_id],
                        f"调整指标 {node_id}.{key} = {orig_val} -> {new_val}",
                    ))

        for cand_ir, changed_nodes, desc in candidates[: self.max_candidates]:
            try:
                score = self._evaluate(cand_ir, data, evaluator)
                if score > best_score:
                    best_score = score
                    best_ir = cand_ir
                    best_log["new_score"] = score
                    best_log["improvement_delta"] = score - base_score
                    best_log["description"] = desc
                    best_log["changed_nodes"] = changed_nodes
            except Exception:
                continue

        return best_ir

    # ------------------------------------------------------------------
    # 6. 多组件迭代改进
    # ------------------------------------------------------------------
    def improve(
        self,
        strategy_ir: StrategyIR,
        data: pd.DataFrame,
        evaluator: Optional[Callable[[StrategyIR, pd.DataFrame], Any]] = None,
        n_iterations: int = 10,
    ) -> Tuple[StrategyIR, List[Dict[str, Any]]]:
        """多组件迭代优化。

        每次迭代随机选择一个改进方向（入场/出场/过滤/止损/指标参数），
        应用改进并评估，若性能提升则保留，否则回滚。

        Args:
            strategy_ir: 原始策略 IR。
            data: 回测行情数据。
            evaluator: 评估回调。
            n_iterations: 迭代次数。

        Returns:
            (improved_ir, logs): 改进后的 IR 和迭代日志列表。
        """
        best_ir = copy.deepcopy(strategy_ir)
        best_score = self._evaluate(best_ir, data, evaluator)
        logs: List[Dict[str, Any]] = []

        operations = [
            self.improve_entry,
            self.improve_exit,
            self.improve_filters,
            self.improve_stoploss,
            self.improve_indicator_params,
        ]

        for i in range(n_iterations):
            op = random.choice(operations)
            try:
                new_ir, log = op(best_ir, data, evaluator)
                new_score = log.get("new_score", best_score)

                log["iteration"] = i + 1
                log["accepted"] = new_score > best_score
                logs.append(log)

                if new_score > best_score:
                    best_ir = new_ir
                    best_score = new_score
            except Exception as exc:
                logs.append({
                    "iteration": i + 1,
                    "operation": op.__name__,
                    "accepted": False,
                    "error": str(exc),
                })

        return best_ir

    # ------------------------------------------------------------------
    # 辅助：节点定位与树操作
    # ------------------------------------------------------------------
    def _collect_entry_nodes(self, strategy_ir: StrategyIR) -> List[Node]:
        """收集通往 BUY 动作的所有节点。"""
        buy_actions = [
            n for n in strategy_ir.nodes
            if n.node_type == NodeType.ACTION and n.name == "BUY"
        ]
        return self._collect_path_nodes(strategy_ir, buy_actions)

    def _collect_exit_nodes(self, strategy_ir: StrategyIR) -> List[Node]:
        """收集通往 SELL 动作的所有节点。"""
        sell_actions = [
            n for n in strategy_ir.nodes
            if n.node_type == NodeType.ACTION and n.name == "SELL"
        ]
        return self._collect_path_nodes(strategy_ir, sell_actions)

    def _collect_path_nodes(
        self, strategy_ir: StrategyIR, target_nodes: List[Node]
    ) -> List[Node]:
        """收集从根到目标节点的路径上的所有节点。"""
        path_nodes: set = set()
        for target in target_nodes:
            current_id = target.id
            path_nodes.add(target)
            while True:
                parent = self._parent_of(strategy_ir, current_id)
                if parent is None:
                    break
                path_nodes.add(parent)
                current_id = parent.id
        return list(path_nodes)

    def _parent_of(self, strategy_ir: StrategyIR, node_id: str) -> Optional[Node]:
        """获取节点的直接父节点。"""
        for edge in strategy_ir.edges:
            if edge.target == node_id:
                return strategy_ir.find_node(edge.source)
        return None

    def _children_of(self, strategy_ir: StrategyIR, node_id: str) -> List[Node]:
        """获取节点的直接子节点。"""
        child_ids = {e.target for e in strategy_ir.edges if e.source == node_id}
        return [n for n in strategy_ir.nodes if n.id in child_ids]

    def _find_stoploss_nodes(self, strategy_ir: StrategyIR) -> List[Node]:
        """查找止损相关的节点（名称匹配模式）。"""
        nodes = []
        for n in strategy_ir.nodes:
            name_lower = n.name.lower()
            if any(pat in name_lower for pat in _STOPLOSS_PATTERNS):
                nodes.append(n)
        return nodes

    # ------------------------------------------------------------------
    # 辅助：候选生成
    # ------------------------------------------------------------------
    def _generate_condition_candidates(
        self,
        strategy_ir: StrategyIR,
        relevant_nodes: List[Node],
        context: str,
    ) -> List[Tuple[StrategyIR, List[str], str]]:
        """为条件节点生成变异候选。"""
        candidates: List[Tuple[StrategyIR, List[str], str]] = []
        seen = set()

        for node in relevant_nodes:
            if node.id in seen:
                continue
            seen.add(node.id)

            # 变异 1：替换指标
            if node.node_type == NodeType.INDICATOR and node.name in _INDICATOR_POOL:
                alt = random.choice([i for i in _INDICATOR_POOL if i != node.name])
                cand = copy.deepcopy(strategy_ir)
                n = cand.find_node(node.id)
                if n is not None:
                    n.name = alt
                    candidates.append((cand, [node.id], f"替换指标 {node.name} -> {alt} ({context})"))

            # 变异 2：微调阈值 VALUE
            if node.node_type == NodeType.VALUE:
                for key, val in node.params.items():
                    if isinstance(val, (int, float)) and abs(float(val)) > 1e-12:
                        for factor in [0.8, 1.2]:
                            cand = copy.deepcopy(strategy_ir)
                            n = cand.find_node(node.id)
                            if n is not None:
                                new_val = float(val) * factor
                                if isinstance(val, int):
                                    new_val = int(round(new_val))
                                n.params[key] = new_val
                                candidates.append((
                                    cand,
                                    [node.id],
                                    f"微调阈值 {key} = {val} -> {new_val} ({context})",
                                ))

            # 变异 3：翻转比较运算符
            if node.node_type == NodeType.OPERATOR and node.name in ("GT", "LT"):
                new_op = "LT" if node.name == "GT" else "GT"
                cand = copy.deepcopy(strategy_ir)
                n = cand.find_node(node.id)
                if n is not None:
                    n.name = new_op
                    candidates.append((cand, [node.id], f"翻转运算符 {node.name} -> {new_op} ({context})"))

        # 限制候选数量
        if len(candidates) > self.max_candidates:
            candidates = random.sample(candidates, self.max_candidates)

        return candidates

    # ------------------------------------------------------------------
    # 辅助：树编辑操作
    # ------------------------------------------------------------------
    def _remove_subtree(
        self, strategy_ir: StrategyIR, parent_id: str, child_id: str
    ) -> Optional[StrategyIR]:
        """从 parent_id 的子节点中移除 child_id，保持树有效。

        若 parent 是 AND 节点且移除后只剩 1 个子节点，
        则将该子节点直接连接到 parent 的 parent 上。
        """
        ir = strategy_ir
        edges_to_remove = [
            i for i, e in enumerate(ir.edges)
            if e.source == parent_id and e.target == child_id
        ]
        if not edges_to_remove:
            return None

        # 安全移除：仅移除边，不删除节点（避免破坏其他引用）
        for idx in sorted(edges_to_remove, reverse=True):
            ir.edges.pop(idx)

        # 若 AND 节点只剩一个子节点，尝试简化
        parent = ir.find_node(parent_id)
        if parent is not None and parent.name == "AND":
            remaining_children = self._children_of(ir, parent_id)
            if len(remaining_children) == 1:
                # 将 parent 替换为其唯一子节点
                # 找到 parent 的 parent
                grandparent = self._parent_of(ir, parent_id)
                if grandparent is not None:
                    # 将 grandparent -> parent 替换为 grandparent -> child
                    for e in ir.edges:
                        if e.source == grandparent.id and e.target == parent_id:
                            e.target = remaining_children[0].id
                    # 移除 parent 节点和边
                    ir.nodes = [n for n in ir.nodes if n.id != parent_id]
                    ir.edges = [
                        e for e in ir.edges
                        if e.source != parent_id and e.target != parent_id
                    ]
        return ir

    def _add_filter_to_and(
        self, strategy_ir: StrategyIR, and_node_id: str
    ) -> Optional[StrategyIR]:
        """在 AND 节点下添加一个简单过滤条件。

        添加的子树结构：
            INDICATOR (RSI) -> OPERATOR (LT) -> VALUE (70)
        作为 AND 的新子节点。
        """
        ir = strategy_ir
        and_node = ir.find_node(and_node_id)
        if and_node is None or and_node.name != "AND":
            return None

        # 生成新节点
        suffix = f"_{random.randint(10000, 99999)}"
        ind_node = Node(
            id=f"filter_ind{suffix}",
            node_type=NodeType.INDICATOR,
            name=random.choice(["RSI", "CCI", "ADX"]),
            params={"period": random.choice([10, 14, 20])},
        )
        val_node = Node(
            id=f"filter_val{suffix}",
            node_type=NodeType.VALUE,
            name="threshold",
            params={"value": random.choice([30, 50, 70])},
        )
        op_node = Node(
            id=f"filter_op{suffix}",
            node_type=NodeType.OPERATOR,
            name=random.choice(["GT", "LT"]),
        )

        ir.nodes.extend([ind_node, val_node, op_node])
        ir.add_edge(op_node.id, ind_node.id)
        ir.add_edge(op_node.id, val_node.id)
        ir.add_edge(and_node_id, op_node.id)

        return ir
