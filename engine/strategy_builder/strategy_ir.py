"""
策略中间表示（Strategy IR）——策略的统一数据结构。

支持序列化/反序列化，用于引擎内部传递、持久化存储与跨模块通信。
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional, Literal, Set, Tuple
from enum import Enum
from collections import defaultdict


class NodeType(str, Enum):
    """策略树节点类型。"""
    INDICATOR = "indicator"           # 技术指标节点
    OPERATOR = "operator"             # 逻辑/比较运算符
    VALUE = "value"                   # 常数/参数值
    CONDITION = "condition"           # 条件判断（IF/THEN/ELSE）
    ACTION = "action"                 # 交易动作（买入/卖出/空仓）
    ROOT = "root"                     # 根节点


class EdgeType(str, Enum):
    """策略树边类型。"""
    CHILD = "child"                   # 子节点关系
    THEN = "then"                     # 条件成立分支
    ELSE = "else"                     # 条件不成立分支
    PARAM = "param"                   # 参数绑定


@dataclass
class Node:
    """策略 IR 中的单个节点。

    Attributes:
        id: 全局唯一节点标识符。
        node_type: 节点类型。
        name: 节点名称，如指标名或运算符名。
        params: 节点参数，如指标周期、阈值等。
        meta: 扩展元数据，供代码生成器使用。
    """
    id: str
    node_type: NodeType
    name: str
    params: Dict[str, Any] = field(default_factory=dict)
    meta: Dict[str, Any] = field(default_factory=dict)

    def __hash__(self) -> int:
        return hash(self.id)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Node):
            return NotImplemented
        return self.id == other.id


@dataclass
class Edge:
    """策略 IR 中的节点连接边。

    Attributes:
        source: 源节点 ID。
        target: 目标节点 ID。
        edge_type: 边类型。
        label: 可选标签，用于区分同类型多分支。
    """
    source: str
    target: str
    edge_type: EdgeType = EdgeType.CHILD
    label: Optional[str] = None


@dataclass
class StrategyConfig:
    """策略运行时配置。

    Attributes:
        timeframe: 时间周期，如 '1d', '1m', '15m'。
        market: 市场代码，如 'CN', 'US'。
        slippage: 滑点（以价格百分比表示）。
        commission_rate: 佣金费率（双边合计）。
        initial_capital: 初始资金。
        position_sizing: 仓位管理模型，如 'fixed', 'percent'。
        max_positions: 最大同时持仓数。
    """
    timeframe: str = "1d"
    market: Literal["CN", "US", "HK"] = "CN"
    slippage: float = 0.001
    commission_rate: float = 0.0003
    initial_capital: float = 1_000_000.0
    position_sizing: Literal["fixed", "percent", "risk_parity"] = "percent"
    max_positions: int = 10


class StrategyBuilderError(Exception):
    """策略构建器异常。"""
    pass


@dataclass(eq=False)
class StrategyIR:
    """策略中间表示（Strategy Intermediate Representation）。

    作为引擎内部统一数据结构，串联 GP 构建、回测、优化、
    代码生成等模块。

    Attributes:
        version: IR 版本号，用于向前兼容。
        strategy_id: 策略唯一标识符。
        name: 策略名称。
        description: 策略描述。
        nodes: 策略树节点列表。
        edges: 策略树边列表。
        variables: 策略变量映射（如参数、常量）。
        config: 策略运行时配置。
    """
    version: str = "1.0"
    strategy_id: str = ""
    name: str = ""
    description: str = ""
    nodes: List[Node] = field(default_factory=list)
    edges: List[Edge] = field(default_factory=list)
    variables: Dict[str, Any] = field(default_factory=dict)
    config: StrategyConfig = field(default_factory=StrategyConfig)

    # ------------------------------------------------------------------
    # 序列化 / 反序列化
    # ------------------------------------------------------------------
    def to_dict(self) -> Dict[str, Any]:
        """将 StrategyIR 转换为字典，便于 JSON 序列化。"""
        return asdict(self)

    def to_json(self, indent: int = 2) -> str:
        """序列化为 JSON 字符串。"""
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False, default=str)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> StrategyIR:
        """从字典反序列化。"""
        nodes = [Node(**n) for n in data.get("nodes", [])]
        edges = [Edge(**e) for e in data.get("edges", [])]
        config = StrategyConfig(**data.get("config", {}))
        return cls(
            version=data.get("version", "1.0"),
            strategy_id=data.get("strategy_id", ""),
            name=data.get("name", ""),
            description=data.get("description", ""),
            nodes=nodes,
            edges=edges,
            variables=data.get("variables", {}),
            config=config,
        )

    @classmethod
    def from_json(cls, json_str: str) -> StrategyIR:
        """从 JSON 字符串反序列化。"""
        return cls.from_dict(json.loads(json_str))

    # ------------------------------------------------------------------
    # 简化版序列化（不含循环引用）
    # ------------------------------------------------------------------
    def to_simple_dict(self) -> Dict[str, Any]:
        """生成简化版字典，不包含循环引用，便于哈希和去重。

        与 to_dict 的区别：将 nodes 和 edges 按规范顺序排序，
        去除 meta 中可能包含的不可序列化对象，并扁平化表示。
        """
        sorted_nodes = sorted(
            self.nodes,
            key=lambda n: (n.node_type.value, n.name, n.id)
        )
        sorted_edges = sorted(
            self.edges,
            key=lambda e: (e.source, e.target, e.edge_type.value)
        )
        return {
            "version": self.version,
            "strategy_id": self.strategy_id,
            "name": self.name,
            "description": self.description,
            "nodes": [
                {
                    "id": n.id,
                    "node_type": n.node_type.value,
                    "name": n.name,
                    "params": dict(sorted(n.params.items())),
                    "meta": {},  # 简化版去除 meta 避免不可序列化对象
                }
                for n in sorted_nodes
            ],
            "edges": [
                {
                    "source": e.source,
                    "target": e.target,
                    "edge_type": e.edge_type.value,
                    "label": e.label,
                }
                for e in sorted_edges
            ],
            "variables": dict(sorted(self.variables.items())),
            "config": {
                "timeframe": self.config.timeframe,
                "market": self.config.market,
                "slippage": self.config.slippage,
                "commission_rate": self.config.commission_rate,
                "initial_capital": self.config.initial_capital,
                "position_sizing": self.config.position_sizing,
                "max_positions": self.config.max_positions,
            },
        }

    @classmethod
    def from_simple_dict(cls, data: Dict[str, Any]) -> StrategyIR:
        """从简化版字典反序列化。

        Args:
            data: 简化版字典（由 to_simple_dict 生成）。

        Returns:
            StrategyIR: 恢复后的策略 IR 实例。
        """
        nodes = [
            Node(
                id=n["id"],
                node_type=NodeType(n["node_type"]),
                name=n["name"],
                params=n.get("params", {}),
            )
            for n in data.get("nodes", [])
        ]
        edges = [
            Edge(
                source=e["source"],
                target=e["target"],
                edge_type=EdgeType(e["edge_type"]),
                label=e.get("label"),
            )
            for e in data.get("edges", [])
        ]
        config = StrategyConfig(**data.get("config", {}))
        return cls(
            version=data.get("version", "1.0"),
            strategy_id=data.get("strategy_id", ""),
            name=data.get("name", ""),
            description=data.get("description", ""),
            nodes=nodes,
            edges=edges,
            variables=data.get("variables", {}),
            config=config,
        )

    # ------------------------------------------------------------------
    # 便捷方法
    # ------------------------------------------------------------------
    def find_node(self, node_id: str) -> Optional[Node]:
        """按 ID 查找节点。"""
        for node in self.nodes:
            if node.id == node_id:
                return node
        return None

    def children_of(self, node_id: str) -> List[Node]:
        """获取某节点的直接子节点。"""
        child_ids = {e.target for e in self.edges if e.source == node_id}
        return [n for n in self.nodes if n.id in child_ids]

    def parents_of(self, node_id: str) -> List[Node]:
        """获取某节点的直接父节点。"""
        parent_ids = {e.source for e in self.edges if e.target == node_id}
        return [n for n in self.nodes if n.id in parent_ids]

    def add_edge(self, source: str, target: str, edge_type: EdgeType = EdgeType.CHILD,
                 label: Optional[str] = None) -> None:
        """添加一条边。"""
        self.edges.append(Edge(source=source, target=target, edge_type=edge_type, label=label))

    def get_root(self) -> Optional[Node]:
        """获取根节点（假设仅有一个 root 类型节点）。"""
        for node in self.nodes:
            if node.node_type == NodeType.ROOT:
                return node
        return None

    # ------------------------------------------------------------------
    # 节点查询方法
    # ------------------------------------------------------------------
    def get_entry_nodes(self) -> List[Node]:
        """返回所有入场条件节点。

        入场节点定义为：类型为 CONDITION 或 ACTION 且 name 为 BUY 的节点。
        """
        return [
            n for n in self.nodes
            if (n.node_type in (NodeType.CONDITION, NodeType.ACTION) and n.name == "BUY")
        ]

    def get_exit_nodes(self) -> List[Node]:
        """返回所有出场条件节点。

        出场节点定义为：类型为 ACTION 且 name 为 SELL 的节点。
        """
        return [
            n for n in self.nodes
            if n.node_type == NodeType.ACTION and n.name == "SELL"
        ]

    def get_indicator_nodes(self) -> List[Node]:
        """返回所有 INDICATOR 类型节点（用于后续指标注册）。"""
        return [n for n in self.nodes if n.node_type == NodeType.INDICATOR]

    # ------------------------------------------------------------------
    # 节点操作方法
    # ------------------------------------------------------------------
    def rename_nodes(self, rename_map: Dict[str, str]) -> None:
        """批量重命名节点。

        Args:
            rename_map: 映射字典，key 为旧节点 ID，value 为新节点 ID。

        Raises:
            StrategyBuilderError: 如果新 ID 已存在或旧 ID 不存在。
        """
        existing_ids = {n.id for n in self.nodes}
        for old_id, new_id in rename_map.items():
            if old_id not in existing_ids:
                raise StrategyBuilderError(f"重命名失败: 节点 '{old_id}' 不存在")
            if new_id in existing_ids and new_id != old_id:
                raise StrategyBuilderError(f"重命名失败: 新 ID '{new_id}' 已存在")

        # 更新节点 ID
        for node in self.nodes:
            if node.id in rename_map:
                node.id = rename_map[node.id]
        # 更新边引用
        for edge in self.edges:
            if edge.source in rename_map:
                edge.source = rename_map[edge.source]
            if edge.target in rename_map:
                edge.target = rename_map[edge.target]

    def replace_node(self, old_node_id: str, new_node: Node) -> None:
        """替换某个节点，保持连接关系不变。

        Args:
            old_node_id: 要替换的节点 ID。
            new_node: 新节点实例。

        Raises:
            StrategyBuilderError: 如果旧节点不存在。
        """
        old_node = self.find_node(old_node_id)
        if old_node is None:
            raise StrategyBuilderError(f"替换失败: 节点 '{old_node_id}' 不存在")

        # 保留新节点的 ID 为旧节点 ID（确保连接关系不变），
        # 或更新所有边引用为新节点 ID
        if new_node.id != old_node_id:
            # 更新所有指向 old_node_id 的边
            for edge in self.edges:
                if edge.source == old_node_id:
                    edge.source = new_node.id
                if edge.target == old_node_id:
                    edge.target = new_node.id

        # 替换节点列表中的节点
        for i, node in enumerate(self.nodes):
            if node.id == old_node_id:
                self.nodes[i] = new_node
                break

    def remove_node(self, node_id: str) -> None:
        """删除某个节点，自动断开边连接。

        Args:
            node_id: 要删除的节点 ID。

        Raises:
            StrategyBuilderError: 如果节点不存在或是 ROOT 节点。
        """
        node = self.find_node(node_id)
        if node is None:
            raise StrategyBuilderError(f"删除失败: 节点 '{node_id}' 不存在")
        if node.node_type == NodeType.ROOT:
            raise StrategyBuilderError("不能删除 ROOT 节点")

        # 删除与该节点相关的所有边
        self.edges = [
            e for e in self.edges
            if e.source != node_id and e.target != node_id
        ]
        # 删除节点
        self.nodes = [n for n in self.nodes if n.id != node_id]

    def add_indicator_node(
        self,
        indicator_name: str,
        params: Optional[Dict[str, Any]] = None,
        parent_id: Optional[str] = None,
        edge_type: EdgeType = EdgeType.CHILD,
    ) -> Node:
        """便捷方法：添加一个指标节点，自动连接到适当父节点。

        Args:
            indicator_name: 指标名称，如 "SMA", "RSI"。
            params: 指标参数，如 {"period": 20}。
            parent_id: 父节点 ID，None 则自动连接到 ROOT 节点。
            edge_type: 边类型。

        Returns:
            Node: 创建的指标节点。

        Raises:
            StrategyBuilderError: 如果 parent_id 不存在且没有 ROOT 节点。
        """
        import uuid
        node_id = f"ind_{indicator_name}_{uuid.uuid4().hex[:8]}"
        node = Node(
            id=node_id,
            node_type=NodeType.INDICATOR,
            name=indicator_name,
            params=params or {},
        )
        self.nodes.append(node)

        target_parent = parent_id
        if target_parent is None:
            root = self.get_root()
            if root is None:
                raise StrategyBuilderError("没有 ROOT 节点，无法自动连接指标")
            target_parent = root.id
        else:
            if self.find_node(target_parent) is None:
                raise StrategyBuilderError(f"父节点 '{target_parent}' 不存在")

        self.add_edge(target_parent, node_id, edge_type=edge_type)
        return node

    # ------------------------------------------------------------------
    # 表达式转换
    # ------------------------------------------------------------------
    def to_expression(self, node_id: Optional[str] = None) -> str:
        """将策略树转换为可读的人类表达式（字符串）。

        例如: "IF(SMA(20) > SMA(50), BUY, HOLD)"

        Args:
            node_id: 起始节点 ID，None 则从 ROOT 节点开始。

        Returns:
            str: 人类可读的表达式字符串。
        """
        if node_id is None:
            root = self.get_root()
            if root is None:
                return "EMPTY_STRATEGY"
            node_id = root.id

        node = self.find_node(node_id)
        if node is None:
            return "UNKNOWN"

        children = self.children_of(node_id)
        # 按边类型排序子节点：THEN 在前，ELSE 在后，CHILD 保持原序
        child_edges = [e for e in self.edges if e.source == node_id]
        child_edges.sort(key=lambda e: (
            0 if e.edge_type == EdgeType.THEN else
            1 if e.edge_type == EdgeType.ELSE else
            2
        ))
        sorted_children = []
        for e in child_edges:
            child = self.find_node(e.target)
            if child:
                sorted_children.append(child)

        if node.node_type == NodeType.ROOT:
            if sorted_children:
                return self.to_expression(sorted_children[0].id)
            return "EMPTY"

        if node.node_type == NodeType.ACTION:
            return node.name

        if node.node_type == NodeType.VALUE:
            val = node.params.get("value", node.name)
            return str(val)

        if node.node_type == NodeType.INDICATOR:
            params_str = ",".join(f"{k}={v}" for k, v in sorted(node.params.items()))
            if params_str:
                return f"{node.name}({params_str})"
            return node.name

        if node.node_type == NodeType.OPERATOR:
            if node.name in ("AND", "OR"):
                if len(sorted_children) >= 2:
                    parts = [self.to_expression(c.id) for c in sorted_children]
                    op = "&&" if node.name == "AND" else "||"
                    return f"({f' {op} '.join(parts)})"
                elif len(sorted_children) == 1:
                    return self.to_expression(sorted_children[0].id)
                return node.name
            elif node.name == "NOT":
                if sorted_children:
                    return f"!({self.to_expression(sorted_children[0].id)})"
                return f"{node.name}()"
            elif node.name in ("GT", "LT", "EQ"):
                if len(sorted_children) >= 2:
                    op_map = {"GT": ">", "LT": "<", "EQ": "=="}
                    op = op_map.get(node.name, node.name)
                    left = self.to_expression(sorted_children[0].id)
                    right = self.to_expression(sorted_children[1].id)
                    return f"({left} {op} {right})"
                return f"{node.name}(?)"
            elif node.name in ("ADD", "SUB", "MUL", "DIV"):
                if len(sorted_children) >= 2:
                    op_map = {"ADD": "+", "SUB": "-", "MUL": "*", "DIV": "/"}
                    op = op_map.get(node.name, node.name)
                    parts = [self.to_expression(c.id) for c in sorted_children]
                    return f"({f' {op} '.join(parts)})"
                return f"{node.name}(?)"
            else:
                parts = [self.to_expression(c.id) for c in sorted_children]
                return f"{node.name}({', '.join(parts)})"

        if node.node_type == NodeType.CONDITION:
            # IF-THEN-ELSE 结构
            if len(sorted_children) >= 3:
                cond = self.to_expression(sorted_children[0].id)
                then_br = self.to_expression(sorted_children[1].id)
                else_br = self.to_expression(sorted_children[2].id)
                return f"IF({cond}, {then_br}, {else_br})"
            elif len(sorted_children) == 2:
                cond = self.to_expression(sorted_children[0].id)
                then_br = self.to_expression(sorted_children[1].id)
                return f"IF({cond}, {then_br}, HOLD)"
            elif len(sorted_children) == 1:
                return self.to_expression(sorted_children[0].id)
            return f"{node.name}(?)"

        return f"{node.name}[{node.node_type.value}]"

    # ------------------------------------------------------------------
    # 增强校验
    # ------------------------------------------------------------------
    def validate(self) -> List[str]:
        """增强校验，返回错误信息列表。空列表表示通过。

        校验项包括：
        - 基础字段检查
        - 边端点有效性
        - 循环依赖检测（DFS 判断图是否为 DAG）
        - 类型一致性
        - ROOT 节点必须有 CONDITION 或 ACTION 子节点
        - 没有孤立节点
        """
        errors: List[str] = []

        # 1. 基础字段检查
        if not self.strategy_id:
            errors.append("strategy_id 不能为空")
        root = self.get_root()
        if root is None:
            errors.append("缺少 ROOT 节点")

        # 2. 检查所有边的端点是否存在于 nodes 中
        node_ids = {n.id for n in self.nodes}
        for e in self.edges:
            if e.source not in node_ids:
                errors.append(f"边引用了不存在的源节点: {e.source}")
            if e.target not in node_ids:
                errors.append(f"边引用了不存在的目标节点: {e.target}")

        # 3. 循环依赖检测（DFS 判断图是否为 DAG）
        if self._has_cycle():
            errors.append("策略树存在循环依赖，必须是有向无环图(DAG)")

        # 4. 类型一致性检查
        errors.extend(self._check_type_consistency())

        # 5. ROOT 节点必须有 CONDITION 或 ACTION 子节点
        if root is not None:
            root_children = self.children_of(root.id)
            has_valid_child = any(
                c.node_type in (NodeType.CONDITION, NodeType.ACTION)
                for c in root_children
            )
            if not has_valid_child and root_children:
                errors.append("ROOT 节点必须至少有一个 CONDITION 或 ACTION 子节点")

        # 6. 检查孤立节点（没有入边/出边的非 ROOT 节点）
        nodes_with_incoming = {e.target for e in self.edges}
        nodes_with_outgoing = {e.source for e in self.edges}
        for node in self.nodes:
            if node.node_type == NodeType.ROOT:
                continue
            has_in = node.id in nodes_with_incoming
            has_out = node.id in nodes_with_outgoing
            if not has_in and not has_out:
                errors.append(f"孤立节点(无连接): {node.id} ({node.name})")
            elif not has_in:
                # 没有父节点的非 ROOT 节点可能是异常（除非是独立指标定义）
                if node.node_type not in (NodeType.INDICATOR, NodeType.VALUE):
                    errors.append(f"节点无父节点连接: {node.id} ({node.name})")

        return errors

    def _has_cycle(self) -> bool:
        """使用 DFS 检测图中是否存在环。

        Returns:
            bool: 存在环返回 True，否则 False。
        """
        # 构建邻接表
        adj: Dict[str, List[str]] = defaultdict(list)
        for edge in self.edges:
            adj[edge.source].append(edge.target)

        WHITE, GRAY, BLACK = 0, 1, 2
        color: Dict[str, int] = {n.id: WHITE for n in self.nodes}

        def dfs(node_id: str) -> bool:
            color[node_id] = GRAY
            for neighbor in adj[node_id]:
                if neighbor not in color:
                    continue  # 跳过不存在的节点（已在 validate 中检查）
                if color[neighbor] == GRAY:
                    return True  # 发现回边，存在环
                if color[neighbor] == WHITE and dfs(neighbor):
                    return True
            color[node_id] = BLACK
            return False

        for node in self.nodes:
            if color[node.id] == WHITE:
                if dfs(node.id):
                    return True
        return False

    def _check_type_consistency(self) -> List[str]:
        """检查类型一致性。

        - INDICATOR 节点只能输出 float（其子节点应为 VALUE/PARAM 类型）
        - OPERATOR 输入类型匹配
        """
        errors: List[str] = []
        for node in self.nodes:
            if node.node_type == NodeType.INDICATOR:
                children = self.children_of(node.id)
                for child in children:
                    # 指标节点的子节点应为参数（VALUE 或 PARAM 边）
                    edge = next(
                        (e for e in self.edges if e.source == node.id and e.target == child.id),
                        None
                    )
                    if edge and edge.edge_type != EdgeType.PARAM:
                        # 允许 CHILD 类型连接，但参数类型更好
                        pass

            if node.node_type == NodeType.OPERATOR:
                if node.name in ("AND", "OR"):
                    children = self.children_of(node.id)
                    for child in children:
                        if child.node_type == NodeType.VALUE:
                            val = child.params.get("value", child.name)
                            try:
                                float(val)
                                errors.append(
                                    f"逻辑运算符 '{node.name}' 的输入应为布尔类型，"
                                    f"但节点 '{child.id}' 是数值"
                                )
                            except (ValueError, TypeError):
                                pass

        return errors

    # ------------------------------------------------------------------
    # 等值和哈希（用于策略去重）
    # ------------------------------------------------------------------
    def __eq__(self, other: object) -> bool:
        """基于简化字典判断两个 StrategyIR 是否相等。"""
        if not isinstance(other, StrategyIR):
            return NotImplemented
        return self.to_simple_dict() == other.to_simple_dict()

    def __hash__(self) -> int:
        """基于简化字典生成哈希值。"""
        return hash(json.dumps(self.to_simple_dict(), sort_keys=True, default=str))

    # ------------------------------------------------------------------
    # 复杂度估计
    # ------------------------------------------------------------------
    def estimate_complexity(self) -> int:
        """估计策略复杂度（节点数 + 深度 + 边数）。

        复杂度公式: 节点数 + 最大深度 + 边数

        Returns:
            int: 策略复杂度得分（越高越复杂）。
        """
        node_count = len(self.nodes)
        edge_count = len(self.edges)
        max_depth = self._compute_max_depth()
        return node_count + max_depth + edge_count

    def _compute_max_depth(
        self,
        node_id: Optional[str] = None,
        visited: Optional[Set[str]] = None,
    ) -> int:
        """计算从指定节点到叶子节点的最大深度。

        Args:
            node_id: 起始节点 ID，None 则从 ROOT 开始。
            visited: 已访问节点集合（防止循环）。

        Returns:
            int: 最大深度（叶子节点深度为 0）。
        """
        if visited is None:
            visited = set()
        if node_id is None:
            root = self.get_root()
            if root is None:
                return 0
            node_id = root.id

        if node_id in visited:
            return 0  # 防止循环
        visited.add(node_id)

        children = self.children_of(node_id)
        if not children:
            return 0

        max_child_depth = 0
        for child in children:
            if child.id in visited:
                continue
            depth = self._compute_max_depth(child.id, visited.copy())
            max_child_depth = max(max_child_depth, depth)

        return 1 + max_child_depth

    # ------------------------------------------------------------------
    # 辅助：拓扑排序
    # ------------------------------------------------------------------
    def topological_sort(self) -> List[str]:
        """对策略树节点进行拓扑排序（Kahn 算法）。

        Returns:
            List[str]: 按拓扑顺序排列的节点 ID 列表。
        """
        in_degree: Dict[str, int] = {n.id: 0 for n in self.nodes}
        adj: Dict[str, List[str]] = defaultdict(list)
        for edge in self.edges:
            adj[edge.source].append(edge.target)
            in_degree[edge.target] += 1

        queue = [n_id for n_id, deg in in_degree.items() if deg == 0]
        result: List[str] = []

        while queue:
            current = queue.pop(0)
            result.append(current)
            for neighbor in adj[current]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        return result

    # ------------------------------------------------------------------
    # 辅助：子树提取
    # ------------------------------------------------------------------
    def extract_subtree(self, node_id: str) -> StrategyIR:
        """提取以指定节点为根的子树，返回独立的 StrategyIR。

        Args:
            node_id: 子树根节点 ID。

        Returns:
            StrategyIR: 包含子树节点和边的独立 IR 实例。
        """
        included_ids: Set[str] = set()

        def collect(node_id: str) -> None:
            if node_id in included_ids:
                return
            included_ids.add(node_id)
            children = self.children_of(node_id)
            for child in children:
                collect(child.id)

        collect(node_id)

        nodes = [n for n in self.nodes if n.id in included_ids]
        edges = [e for e in self.edges if e.source in included_ids and e.target in included_ids]

        return StrategyIR(
            strategy_id=f"subtree_{node_id}",
            name=f"Subtree({node_id})",
            nodes=nodes,
            edges=edges,
            config=self.config,
        )
