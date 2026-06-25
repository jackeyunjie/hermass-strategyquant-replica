"""
Python 代码生成器——基于 Jinja2 模板。

输入 Strategy IR，输出可在 vectorbt / backtrader / Hermass DSL 中运行的 Python 代码。
"""

from __future__ import annotations

import ast
import inspect
import re
import textwrap
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import jinja2

from ..strategy_builder.strategy_ir import StrategyIR, Node, NodeType, Edge, EdgeType


# ------------------------------------------------------------------
# 自定义异常
# ------------------------------------------------------------------

class CodeGenerationError(Exception):
    """代码生成过程中发生的错误。

    Attributes:
        message: 错误描述信息。
        node_id: 引发错误的节点 ID（可选）。
    """

    def __init__(self, message: str, node_id: Optional[str] = None) -> None:
        self.node_id = node_id
        self.message = message
        super().__init__(f"[Node {node_id}] {message}" if node_id else message)


# ------------------------------------------------------------------
# 模板配置
# ------------------------------------------------------------------

@dataclass
class TemplateConfig:
    """模板配置。

    Attributes:
        template_dir: Jinja2 模板目录路径。
        template_name: 模板文件名，如 'vectorbt_strategy.py.j2'。
        custom_vars: 模板额外变量。
    """
    template_dir: str = "templates"
    template_name: str = "hermass_dsl.py.j2"
    custom_vars: Dict[str, Any] = field(default_factory=dict)


# ------------------------------------------------------------------
# 运算符映射
# ------------------------------------------------------------------

class OperatorMap:
    """IR 运算符到 Python 表达式的映射表。"""

    # 逻辑运算符
    LOGICAL = {
        "AND": "and",
        "OR": "or",
        "NOT": "not",
    }

    # 比较运算符
    COMPARISON = {
        "GT": ">",
        "LT": "<",
        "GTE": ">=",
        "LTE": "<=",
        "EQ": "==",
        "NE": "!=",
    }

    # 算术运算符
    ARITHMETIC = {
        "ADD": "+",
        "SUB": "-",
        "MUL": "*",
        "DIV": "/",
        "MOD": "%",
        "POW": "**",
    }

    # 指标到库函数映射 (vectorbt 风格)
    VBT_INDICATOR = {
        "SMA": "vbt.MA.run(close, window={period}).ma",
        "EMA": "vbt.MA.run(close, window={period}, ewm=True).ma",
        "WMA": "ta.trend.wma_indicator(close, window={period})",
        "RSI": "vbt.RSI.run(close, window={period}).rsi",
        "MACD": "vbt.MACD.run(close, fast={fast}, slow={slow}, signal={signal})",
        "BBANDS": "vbt.BBANDS.run(close, window={period}, std={std})",
        "ATR": "ta.volatility.average_true_range(high, low, close, window={period})",
        "ADX": "ta.trend.adx(high, low, close, window={period})",
        "CCI": "ta.trend.cci(high, low, close, window={period})",
        "STOCH": "ta.momentum.stoch(high, low, close, window={period}, smooth_window={smooth})",
        "MOM": "ta.momentum.roc(close, window={period})",
        "WILLR": "ta.momentum.williams_r(high, low, close, lbp={period})",
        "MFI": "ta.volume.money_flow_index(high, low, close, volume, window={period})",
        "OBV": "ta.volume.on_balance_volume(close, volume)",
        "VWAP": (
            "ta.volume.volume_weighted_average_price("
            "high, low, close, volume, window={period})"
        ),
    }

    # 指标到库函数映射 (backtrader 风格)
    BT_INDICATOR = {
        "SMA": "bt.indicators.SimpleMovingAverage(self.data.close, period={period})",
        "EMA": "bt.indicators.ExponentialMovingAverage(self.data.close, period={period})",
        "WMA": "bt.indicators.WeightedMovingAverage(self.data.close, period={period})",
        "RSI": "bt.indicators.RelativeStrengthIndex(period={period})",
        "MACD": (
            "bt.indicators.MACD(self.data.close, "
            "period_me1={fast}, period_me2={slow}, period_signal={signal})"
        ),
        "BBANDS": "bt.indicators.BollingerBands(self.data.close, period={period}, devfactor={std})",
        "ATR": "bt.indicators.ATR(self.data, period={period})",
        "ADX": "bt.indicators.AverageDirectionalMovementIndex(self.data, period={period})",
        "CCI": "bt.indicators.CommodityChannelIndex(self.data, period={period})",
        "STOCH": "bt.indicators.Stochastic(self.data, period={period}, period_dfast={smooth})",
        "MOM": "bt.indicators.Momentum(self.data.close, period={period})",
        "WILLR": "bt.indicators.WilliamsR(self.data, period={period})",
        "MFI": "bt.indicators.MoneyFlowIndex(self.data, period={period})",
        "OBV": "bt.indicators.OnBalanceVolume(self.data)",
    }

    # 指标到库函数映射 (纯 pandas / ta 风格)
    TA_INDICATOR = {
        "SMA": "ta.trend.sma_indicator(close, window={period})",
        "EMA": "ta.trend.ema_indicator(close, window={period})",
        "WMA": "ta.trend.wma_indicator(close, window={period})",
        "RSI": "ta.momentum.rsi(close, window={period})",
        "MACD": (
            "ta.trend.macd(close, "
            "window_fast={fast}, window_slow={slow}, window_sign={signal})"
        ),
        "BBANDS": "ta.volatility.bollinger_hband(close, window={period}, window_dev={std})",
        "ATR": "ta.volatility.average_true_range(high, low, close, window={period})",
        "ADX": "ta.trend.adx(high, low, close, window={period})",
        "CCI": "ta.trend.cci(high, low, close, window={period})",
        "STOCH": "ta.momentum.stoch(high, low, close, window={period}, smooth_window={smooth})",
        "MOM": "ta.momentum.roc(close, window={period})",
        "WILLR": "ta.momentum.williams_r(high, low, close, lbp={period})",
        "MFI": "ta.volume.money_flow_index(high, low, close, volume, window={period})",
        "OBV": "ta.volume.on_balance_volume(close, volume)",
        "VWAP": (
            "ta.volume.volume_weighted_average_price("
            "high, low, close, volume, window={period})"
        ),
    }

    @classmethod
    def get_indicator_expr(
        cls, template_type: str, indicator_name: str,
        params: Dict[str, Any]
    ) -> str:
        """获取指标表达式字符串。

        Args:
            template_type: 模板类型，'vectorbt', 'backtrader', 'hermass_dsl'。
            indicator_name: 指标名称。
            params: 指标参数字典。

        Returns:
            str: 格式化后的指标调用表达式。
        """
        indicator_name = indicator_name.upper().replace("IND_", "")
        mapping = cls.VBT_INDICATOR if template_type == "vectorbt" else (
            cls.BT_INDICATOR if template_type == "backtrader" else cls.TA_INDICATOR
        )
        template = mapping.get(indicator_name, "None")
        try:
            return template.format(**params)
        except KeyError:
            # 参数缺失时使用默认值
            defaults = {"period": 14, "fast": 12, "slow": 26, "signal": 9, "std": 2, "smooth": 3}
            merged = {**defaults, **params}
            return template.format(**merged)

    @classmethod
    def get_operator_expr(cls, op_name: str, operands: List[str]) -> str:
        """获取运算符表达式。

        Args:
            op_name: 运算符名称，如 'AND', 'GT', 'ADD'。
            operands: 操作数列表。

        Returns:
            str: 格式化后的运算符表达式。
        """
        op_name = op_name.upper()

        # 一元运算符
        if op_name == "NOT" and len(operands) >= 1:
            return f"not ({operands[0]})"

        # 二元运算符
        op = (
            cls.LOGICAL.get(op_name)
            or cls.COMPARISON.get(op_name)
            or cls.ARITHMETIC.get(op_name)
        )
        if op and len(operands) >= 2:
            return f"({operands[0]}) {op} ({operands[1]})"

        return f"# TODO: 未定义运算符 {op_name}({', '.join(operands)})"


# ------------------------------------------------------------------
# 代码格式化
# ------------------------------------------------------------------

class CodeFormatter:
    """代码格式化器——提供 Black 风格或基本缩进格式化。"""

    @staticmethod
    def format_code(code: str, use_black: bool = True) -> str:
        """格式化 Python 代码。

        Args:
            code: 原始代码字符串。
            use_black: 是否尝试使用 black 库格式化。

        Returns:
            str: 格式化后的代码。
        """
        if use_black:
            try:
                import black
                return black.format_str(code, mode=black.Mode(line_length=100))
            except ImportError:
                pass
            except Exception:
                pass

        # 基本缩进格式化（当 black 不可用时）
        return CodeFormatter._basic_indent(code)

    @staticmethod
    def _basic_indent(code: str) -> str:
        """基本缩进格式化——模板已保证正确缩进，仅做简单清理。"""
        # 模板本身已正确缩进，不做额外处理以避免破坏 docstring 等结构
        lines = code.splitlines()
        result = [line.rstrip() for line in lines]
        return "\n".join(result)

    @staticmethod
    def _basic_indent_legacy(code: str) -> str:
        """基本缩进格式化——确保 Python 代码的缩进正确。

        Args:
            code: 原始代码字符串。

        Returns:
            str: 格式化后的代码。
        """
        lines = code.splitlines()
        result: List[str] = []
        indent_level = 0
        indent_str = "    "

        for line in lines:
            stripped = line.strip()

            # 跳过空行
            if not stripped:
                result.append("")
                continue

            # 处理缩进减少
            if (stripped.startswith("elif ") or stripped.startswith("else:")
                    or stripped.startswith("except ") or stripped.startswith("finally:")):
                indent_level = max(0, indent_level - 1)

            # 添加适当缩进（跳过注释和 docstring 的自动缩进）
            if stripped.startswith("#") or stripped.startswith('"""') or stripped.startswith("'''"):
                result.append(indent_str * indent_level + stripped)
            else:
                result.append(indent_str * indent_level + stripped)

            # 处理缩进增加
            if stripped.endswith(":") and not stripped.startswith("#"):
                indent_level += 1
            elif stripped in ("pass", "continue", "break", "return"):
                # 单行语句后不改变缩进
                pass
            elif stripped.startswith("return ") and not stripped.endswith(","):
                pass

        return "\n".join(result)


# ------------------------------------------------------------------
# Python 代码生成器
# ------------------------------------------------------------------

class PythonGenerator:
    """Python 代码生成器。

    将 StrategyIR 转换为 Python 可运行代码，通过 Jinja2 模板渲染实现。
    支持 vectorbt、backtrader、Hermass DSL 三种输出模式。

    Attributes:
        env: Jinja2 环境，用于加载和渲染模板。
    """

    def __init__(self, template_dir: Optional[str] = None) -> None:
        """
        Args:
            template_dir: 模板目录路径，默认使用模块同级目录。
        """
        if template_dir is None:
            import os
            template_dir = os.path.join(os.path.dirname(__file__), "templates")

        self.env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(template_dir),
            trim_blocks=True,
            lstrip_blocks=True,
        )

        # 注册自定义过滤器
        self.env.filters["to_snake_case"] = self._to_snake_case
        self.env.filters["to_class_name"] = self._to_class_name

        self._template_type = "hermass_dsl"

    def _to_snake_case(self, name: str) -> str:
        """将名称转换为 snake_case。"""
        s = re.sub(r"[\-\s]+", "_", name)
        s = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", s)
        s = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s)
        return s.lower().strip("_")

    def _to_class_name(self, name: str) -> str:
        """将名称转换为 ClassName 格式。"""
        s = re.sub(r"[\-\s]+", "_", name)
        parts = s.split("_")
        return "".join(p.capitalize() for p in parts if p)

    def generate(
        self,
        strategy_ir: StrategyIR,
        config: TemplateConfig,
    ) -> str:
        """生成 Python 代码。

        Args:
            strategy_ir: 策略中间表示。
            config: 模板配置。

        Returns:
            str: 生成的 Python 代码字符串。

        Raises:
            CodeGenerationError: 如果 IR 验证失败或生成过程中出错。
            jinja2.TemplateNotFound: 如果模板文件不存在。
        """
        # 验证 IR 完整性
        self.validate_ir(strategy_ir)

        # 确定模板类型并映射到完整文件名
        template_name = config.template_name.lower()
        if "vectorbt" in template_name:
            self._template_type = "vectorbt"
            template_file = "vectorbt_strategy.py.j2"
        elif "backtrader" in template_name:
            self._template_type = "backtrader"
            template_file = "backtrader_strategy.py.j2"
        elif "hermass" in template_name or template_name.endswith(".j2"):
            self._template_type = "hermass_dsl"
            template_file = "hermass_dsl.py.j2"
        else:
            raise CodeGenerationError(f"未知模板名称: {config.template_name}")

        template = self.env.get_template(template_file)

        # 将 IR 转换为模板友好的数据结构
        context = self._ir_to_template_context(strategy_ir)
        context.update(config.custom_vars)
        context["now"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        context["template_type"] = self._template_type

        code = template.render(**context)

        # 代码格式化
        return CodeFormatter.format_code(code, use_black=False)

    def preview(
        self,
        strategy_ir: StrategyIR,
        config: TemplateConfig,
    ) -> str:
        """生成代码预览（不写入文件）。

        Args:
            strategy_ir: 策略中间表示。
            config: 模板配置。

        Returns:
            str: 生成的代码预览字符串（包含行号）。
        """
        code = self.generate(strategy_ir, config)
        lines = code.splitlines()
        numbered = [f"{i+1:4d} | {line}" for i, line in enumerate(lines)]
        return "\n".join(numbered)

    def generate_to_file(
        self,
        strategy_ir: StrategyIR,
        config: TemplateConfig,
        output_path: str,
    ) -> Path:
        """生成代码并写入文件。

        Args:
            strategy_ir: 策略中间表示。
            config: 模板配置。
            output_path: 输出文件路径。

        Returns:
            Path: 写入的文件路径。
        """
        code = self.generate(strategy_ir, config)
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(code, encoding="utf-8")
        return path

    def validate_ir(self, strategy_ir: StrategyIR) -> List[str]:
        """验证 IR 是否可生成代码（类型检查、节点完整性）。

        Args:
            strategy_ir: 策略中间表示。

        Returns:
            List[str]: 验证错误列表，空列表表示通过验证。

        Raises:
            CodeGenerationError: 如果验证发现致命错误（如缺少根节点）。
        """
        errors: List[str] = []

        # 1. 基础结构验证
        if not strategy_ir.strategy_id:
            errors.append("strategy_id 不能为空")
        if not strategy_ir.name:
            errors.append("策略名称 (name) 不能为空")

        root = strategy_ir.get_root()
        if root is None:
            errors.append("缺少 ROOT 节点")
        else:
            # 根节点必须有子节点
            children = strategy_ir.children_of(root.id)
            if not children:
                errors.append("ROOT 节点没有子节点，策略为空")

        # 2. 节点完整性验证
        node_ids = {n.id for n in strategy_ir.nodes}
        for edge in strategy_ir.edges:
            if edge.source not in node_ids:
                errors.append(f"边引用了不存在的源节点: {edge.source}")
            if edge.target not in node_ids:
                errors.append(f"边引用了不存在的目标节点: {edge.target}")

        # 3. 节点类型验证
        valid_node_types = {t.value for t in NodeType}
        for node in strategy_ir.nodes:
            if node.node_type.value not in valid_node_types:
                errors.append(f"节点 {node.id} 类型无效: {node.node_type}")

            # 指标节点必须有名称
            if node.node_type == NodeType.INDICATOR and not node.name:
                errors.append(f"指标节点 {node.id} 缺少名称")

            # 运算符节点必须有合法的运算符名称
            if node.node_type == NodeType.OPERATOR:
                all_ops = (
            set(OperatorMap.LOGICAL)
            | set(OperatorMap.COMPARISON)
            | set(OperatorMap.ARITHMETIC)
        )
                if node.name.upper() not in all_ops:
                    errors.append(f"节点 {node.id} 使用了未定义的运算符: {node.name}")

            # 动作节点必须是 BUY / SELL / HOLD
            if node.node_type == NodeType.ACTION:
                if node.name.upper() not in ("BUY", "SELL", "HOLD"):
                    errors.append(
                    f"动作节点 {node.id} 名称无效: "
                    f"{node.name}（应为 BUY/SELL/HOLD）"
                )

        # 4. 条件节点验证——必须有 THEN 和 ELSE 分支
        for node in strategy_ir.nodes:
            if node.node_type == NodeType.CONDITION:
                then_edges = [
                    e for e in strategy_ir.edges
                    if e.source == node.id and e.edge_type == EdgeType.THEN
                ]
                else_edges = [
                    e for e in strategy_ir.edges
                    if e.source == node.id and e.edge_type == EdgeType.ELSE
                ]
                if not then_edges:
                    errors.append(f"条件节点 {node.id} 缺少 THEN 分支")
                if not else_edges:
                    errors.append(f"条件节点 {node.id} 缺少 ELSE 分支")

        # 5. 配置验证
        cfg = strategy_ir.config
        if cfg.commission_rate < 0 or cfg.commission_rate > 1:
            errors.append(f"commission_rate 必须在 [0, 1] 范围内: {cfg.commission_rate}")
        if cfg.slippage < 0 or cfg.slippage > 1:
            errors.append(f"slippage 必须在 [0, 1] 范围内: {cfg.slippage}")
        if cfg.initial_capital <= 0:
            errors.append(f"initial_capital 必须大于 0: {cfg.initial_capital}")
        if cfg.max_positions < 1:
            errors.append(f"max_positions 必须至少为 1: {cfg.max_positions}")

        if errors:
            return errors

        return []

    def _ir_to_template_context(self, strategy_ir: StrategyIR) -> Dict[str, Any]:
        """将 StrategyIR 转换为模板渲染上下文。

        生成包含以下字段的上下文：
        - strategy_name, strategy_id, description
        - config: 运行时配置
        - nodes: 节点列表（含类型、名称、参数）
        - edges: 边列表
        - entry_conditions: 买入条件表达式列表
        - exit_conditions: 卖出条件表达式列表
        - indicators: 使用的指标列表
        - indicator_expressions: 指标到代码表达式的映射
        """
        nodes = []
        for node in strategy_ir.nodes:
            nodes.append({
                "id": node.id,
                "type": node.node_type.value,
                "name": node.name,
                "params": node.params,
                "meta": node.meta,
            })

        edges = []
        for edge in strategy_ir.edges:
            edges.append({
                "source": edge.source,
                "target": edge.target,
                "type": edge.edge_type.value,
                "label": edge.label,
            })

        # 提取使用的指标
        indicators = []
        indicator_expressions: Dict[str, str] = {}
        for node in strategy_ir.nodes:
            if node.node_type == NodeType.INDICATOR:
                ind_name = node.name.upper().replace("IND_", "")
                indicators.append(ind_name)
                expr = OperatorMap.get_indicator_expr(
                    self._template_type, ind_name, node.params
                )
                indicator_expressions[node.id] = {
                    "name": ind_name,
                    "expr": expr,
                    "params": node.params,
                    "var_name": f"ind_{node.id}",
                }

        # 解析买卖条件
        entry_conditions, exit_conditions = self._parse_conditions(strategy_ir)

        # 构建完整的策略树结构（供模板使用）
        strategy_tree = self._build_strategy_tree(strategy_ir)

        return {
            "strategy_name": strategy_ir.name,
            "strategy_id": strategy_ir.strategy_id,
            "description": strategy_ir.description,
            "version": strategy_ir.version,
            "config": {
                "timeframe": strategy_ir.config.timeframe,
                "market": strategy_ir.config.market,
                "slippage": strategy_ir.config.slippage,
                "commission_rate": strategy_ir.config.commission_rate,
                "initial_capital": strategy_ir.config.initial_capital,
                "position_sizing": strategy_ir.config.position_sizing,
                "max_positions": strategy_ir.config.max_positions,
            },
            "nodes": nodes,
            "edges": edges,
            "indicators": list(set(indicators)),
            "indicator_expressions": indicator_expressions,
            "entry_conditions": entry_conditions,
            "exit_conditions": exit_conditions,
            "strategy_tree": strategy_tree,
            "variables": strategy_ir.variables,
        }

    def _build_strategy_tree(self, strategy_ir: StrategyIR) -> Dict[str, Any]:
        """将 IR 构建为嵌套的策略树结构，便于模板递归渲染。

        Args:
            strategy_ir: 策略中间表示。

        Returns:
            Dict: 嵌套字典表示的策略树。
        """
        root = strategy_ir.get_root()
        if root is None:
            return {}
        return self._build_subtree(strategy_ir, root)

    def _build_subtree(self, strategy_ir: StrategyIR, node: Node) -> Dict[str, Any]:
        """递归构建子树。

        Args:
            strategy_ir: 策略中间表示。
            node: 当前节点。

        Returns:
            Dict: 包含节点信息和子节点的字典。
        """
        subtree = {
            "id": node.id,
            "type": node.node_type.value,
            "name": node.name,
            "params": node.params,
            "meta": node.meta,
            "children": [],
        }

        # 获取所有出边
        out_edges = [e for e in strategy_ir.edges if e.source == node.id]

        # 按边类型分组
        child_edges = [e for e in out_edges if e.edge_type == EdgeType.CHILD]
        then_edges = [e for e in out_edges if e.edge_type == EdgeType.THEN]
        else_edges = [e for e in out_edges if e.edge_type == EdgeType.ELSE]
        param_edges = [e for e in out_edges if e.edge_type == EdgeType.PARAM]

        # 处理 THEN / ELSE 分支（条件节点）
        if then_edges:
            then_node = strategy_ir.find_node(then_edges[0].target)
            if then_node:
                subtree["then_branch"] = self._build_subtree(strategy_ir, then_node)
        if else_edges:
            else_node = strategy_ir.find_node(else_edges[0].target)
            if else_node:
                subtree["else_branch"] = self._build_subtree(strategy_ir, else_node)

        # 处理普通子节点
        for edge in child_edges:
            child_node = strategy_ir.find_node(edge.target)
            if child_node:
                subtree["children"].append(self._build_subtree(strategy_ir, child_node))

        # 处理参数绑定
        for edge in param_edges:
            param_node = strategy_ir.find_node(edge.target)
            if param_node and param_node.node_type == NodeType.VALUE:
                subtree["params"][edge.label or param_node.name] = param_node.params.get("value")

        return subtree

    def _parse_conditions(self, strategy_ir: StrategyIR) -> Tuple[List[str], List[str]]:
        """从策略 IR 解析买入/卖出条件表达式。

        遍历策略树，识别 ACTION 节点，并回溯生成对应的条件表达式。

        Returns:
            (entry_conditions, exit_conditions): 条件字符串列表。
        """
        entry_conditions: List[str] = []
        exit_conditions: List[str] = []

        # 遍历所有 ACTION 节点
        for node in strategy_ir.nodes:
            if node.node_type != NodeType.ACTION:
                continue

            # 回溯找到该 ACTION 节点的条件路径
            condition_expr = self._trace_condition_path(strategy_ir, node)

            if node.name.upper() == "BUY":
                entry_conditions.append(condition_expr)
            elif node.name.upper() == "SELL":
                exit_conditions.append(condition_expr)

        # 如果没有明确条件，添加默认占位符
        if not entry_conditions:
            entry_conditions.append("True")
        if not exit_conditions:
            exit_conditions.append("True")

        return entry_conditions, exit_conditions

    def _trace_condition_path(self, strategy_ir: StrategyIR, action_node: Node) -> str:
        """回溯从根节点到 ACTION 节点的条件路径，生成表达式。

        Args:
            strategy_ir: 策略中间表示。
            action_node: 目标动作节点。

        Returns:
            str: 条件表达式字符串。
        """
        # 找到所有到达该 action_node 的路径
        paths = self._find_all_paths(strategy_ir, action_node.id)
        if not paths:
            return "True"

        # 选择最短路径生成表达式
        path = min(paths, key=len)
        expressions: List[str] = []

        for i, node_id in enumerate(path[:-1]):
            node = strategy_ir.find_node(node_id)
            if node is None:
                continue

            next_node_id = path[i + 1]
            next_node = strategy_ir.find_node(next_node_id)
            if next_node is None:
                continue

            # 处理条件节点
            if node.node_type == NodeType.CONDITION:
                # 判断走的是 THEN 还是 ELSE 分支
                then_edges = [
                    e for e in strategy_ir.edges
                    if e.source == node.id and e.edge_type == EdgeType.THEN
                ]
                else_edges = [
                    e for e in strategy_ir.edges
                    if e.source == node.id and e.edge_type == EdgeType.ELSE
                ]

                then_targets = {e.target for e in then_edges}
                else_targets = {e.target for e in else_edges}

                cond_expr = self._build_node_expression(strategy_ir, node)
                if next_node_id in then_targets:
                    expressions.append(cond_expr)
                elif next_node_id in else_targets:
                    expressions.append(f"not ({cond_expr})")

            # 处理运算符节点
            elif node.node_type == NodeType.OPERATOR:
                expr = self._build_node_expression(strategy_ir, node)
                expressions.append(expr)

        # 合并所有表达式
        if expressions:
            return " and ".join(f"({e})" for e in expressions if e)

        return "True"

    def _find_all_paths(self, strategy_ir: StrategyIR, target_id: str) -> List[List[str]]:
        """查找从根节点到目标节点的所有路径。

        Args:
            strategy_ir: 策略中间表示。
            target_id: 目标节点 ID。

        Returns:
            List[List[str]]: 所有路径列表（每个路径是节点 ID 列表）。
        """
        root = strategy_ir.get_root()
        if root is None:
            return []

        paths: List[List[str]] = []
        visited = set()

        def dfs(current_id: str, path: List[str]) -> None:
            if current_id == target_id:
                paths.append(path + [current_id])
                return
            if current_id in visited:
                return
            visited.add(current_id)

            out_edges = [e for e in strategy_ir.edges if e.source == current_id]
            for edge in out_edges:
                if edge.target not in visited:
                    dfs(edge.target, path + [current_id])

            visited.remove(current_id)

        dfs(root.id, [])
        return paths

    def _build_node_expression(self, strategy_ir: StrategyIR, node: Node) -> str:
        """将单个节点转换为 Python 表达式。

        Args:
            strategy_ir: 策略中间表示。
            node: 当前节点。

        Returns:
            str: Python 表达式字符串。
        """
        if node.node_type == NodeType.INDICATOR:
            # 指标节点 -> 变量引用或函数调用
            ind_name = node.name.upper().replace("IND_", "")
            expr = OperatorMap.get_indicator_expr(self._template_type, ind_name, node.params)
            return f"({expr})"

        elif node.node_type == NodeType.OPERATOR:
            # 获取子节点作为操作数
            child_nodes = strategy_ir.children_of(node.id)
            operands = [self._build_node_expression(strategy_ir, child) for child in child_nodes]
            return OperatorMap.get_operator_expr(node.name, operands)

        elif node.node_type == NodeType.VALUE:
            # 值节点 -> 直接返回值
            val = node.params.get("value", node.meta.get("value", "0"))
            if isinstance(val, str):
                return f"'{val}'"
            return str(val)

        elif node.node_type == NodeType.CONDITION:
            # 条件节点 -> 子节点的布尔表达式
            child_nodes = strategy_ir.children_of(node.id)
            if child_nodes:
                return self._build_node_expression(strategy_ir, child_nodes[0])
            return "True"

        elif node.node_type == NodeType.ACTION:
            return f"action_{node.name.lower()}"

        elif node.node_type == NodeType.ROOT:
            return "root"

        return f"# 未知节点类型: {node.node_type.value}"
