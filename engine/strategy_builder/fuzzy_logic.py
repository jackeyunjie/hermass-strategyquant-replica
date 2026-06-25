"""Fuzzy Logic strategy generation.

This module creates deterministic fuzzy-rule strategies that can be translated
to the frontend graph IR and to the engine StrategyIR used by code generation.
"""

from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Literal, Optional, Tuple

from .strategy_ir import Edge, EdgeType, Node, NodeType, StrategyConfig, StrategyIR


MembershipShape = Literal["triangular", "trapezoid"]


@dataclass
class MembershipFunction:
    label: str
    shape: MembershipShape
    points: List[float]

    def degree(self, value: float) -> float:
        if self.shape == "triangular":
            left, center, right = self.points
            if value <= left or value >= right:
                return 0.0
            if value == center:
                return 1.0
            if value < center:
                return (value - left) / max(center - left, 1e-12)
            return (right - value) / max(right - center, 1e-12)

        left, shoulder_l, shoulder_r, right = self.points
        if value <= left or value >= right:
            return 0.0
        if shoulder_l <= value <= shoulder_r:
            return 1.0
        if value < shoulder_l:
            return (value - left) / max(shoulder_l - left, 1e-12)
        return (right - value) / max(right - shoulder_r, 1e-12)


@dataclass
class FuzzyVariable:
    name: str
    source: str
    universe: Tuple[float, float]
    memberships: List[MembershipFunction]


@dataclass
class FuzzyClause:
    variable: str
    membership: str
    weight: float = 1.0


@dataclass
class FuzzyRule:
    name: str
    clauses: List[FuzzyClause]
    action: Literal["buy", "sell", "hold"]
    threshold: float = 0.55


@dataclass
class FuzzyStrategySpec:
    name: str
    description: str
    variables: List[FuzzyVariable]
    rules: List[FuzzyRule]
    buy_threshold: float = 0.62
    sell_threshold: float = 0.58

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class FuzzyStrategyGenerator:
    """Build fuzzy momentum/reversal strategy templates."""

    def generate(
        self,
        *,
        template: Literal["momentum", "reversal", "balanced"] = "balanced",
        name: Optional[str] = None,
        buy_threshold: float = 0.62,
        sell_threshold: float = 0.58,
    ) -> FuzzyStrategySpec:
        variables = self._default_variables()
        if template == "momentum":
            rules = [
                FuzzyRule("趋势强 + 成交活跃", [
                    FuzzyClause("trend_strength", "strong", 0.45),
                    FuzzyClause("volume_pressure", "high", 0.30),
                    FuzzyClause("risk_heat", "calm", 0.25),
                ], "buy", buy_threshold),
                FuzzyRule("趋势转弱", [
                    FuzzyClause("trend_strength", "weak", 0.55),
                    FuzzyClause("risk_heat", "hot", 0.45),
                ], "sell", sell_threshold),
            ]
        elif template == "reversal":
            rules = [
                FuzzyRule("超卖反弹", [
                    FuzzyClause("reversal_pressure", "oversold", 0.45),
                    FuzzyClause("volume_pressure", "normal", 0.25),
                    FuzzyClause("risk_heat", "calm", 0.30),
                ], "buy", buy_threshold),
                FuzzyRule("反弹过热", [
                    FuzzyClause("reversal_pressure", "overbought", 0.60),
                    FuzzyClause("risk_heat", "hot", 0.40),
                ], "sell", sell_threshold),
            ]
        else:
            rules = [
                FuzzyRule("趋势确认买入", [
                    FuzzyClause("trend_strength", "strong", 0.40),
                    FuzzyClause("volume_pressure", "high", 0.25),
                    FuzzyClause("risk_heat", "calm", 0.20),
                    FuzzyClause("reversal_pressure", "neutral", 0.15),
                ], "buy", buy_threshold),
                FuzzyRule("超卖低风险买入", [
                    FuzzyClause("reversal_pressure", "oversold", 0.45),
                    FuzzyClause("risk_heat", "calm", 0.35),
                    FuzzyClause("volume_pressure", "normal", 0.20),
                ], "buy", buy_threshold),
                FuzzyRule("过热卖出", [
                    FuzzyClause("reversal_pressure", "overbought", 0.45),
                    FuzzyClause("risk_heat", "hot", 0.35),
                    FuzzyClause("trend_strength", "weak", 0.20),
                ], "sell", sell_threshold),
            ]

        return FuzzyStrategySpec(
            name=name or f"Fuzzy {template.title()} Strategy",
            description="基于模糊隶属度评分的非二元策略生成模板",
            variables=variables,
            rules=rules,
            buy_threshold=buy_threshold,
            sell_threshold=sell_threshold,
        )

    def to_strategy_ir(self, spec: FuzzyStrategySpec) -> StrategyIR:
        strategy_id = str(uuid.uuid4())
        root_id = "root"
        nodes = [
            Node(root_id, NodeType.ROOT, spec.name, meta={"engine": "fuzzy_logic"}),
        ]
        edges: List[Edge] = []

        for variable in spec.variables:
            node_id = f"var_{variable.name}"
            nodes.append(Node(
                node_id,
                NodeType.INDICATOR,
                variable.source,
                params={
                    "universe": list(variable.universe),
                    "memberships": [asdict(m) for m in variable.memberships],
                },
                meta={"fuzzy_variable": variable.name},
            ))
            edges.append(Edge(root_id, node_id, EdgeType.CHILD))

        for idx, rule in enumerate(spec.rules, start=1):
            rule_id = f"rule_{idx}"
            nodes.append(Node(
                rule_id,
                NodeType.CONDITION,
                rule.name,
                params={
                    "action": rule.action,
                    "threshold": rule.threshold,
                    "clauses": [asdict(c) for c in rule.clauses],
                },
                meta={"logic": "weighted_fuzzy_and"},
            ))
            edges.append(Edge(root_id, rule_id, EdgeType.CHILD))

        nodes.append(Node(
            "action_buy",
            NodeType.ACTION,
            "BUY",
            params={"threshold": spec.buy_threshold},
        ))
        nodes.append(Node(
            "action_sell",
            NodeType.ACTION,
            "SELL",
            params={"threshold": spec.sell_threshold},
        ))
        edges.append(Edge(root_id, "action_buy", EdgeType.THEN, "buy"))
        edges.append(Edge(root_id, "action_sell", EdgeType.ELSE, "sell"))

        return StrategyIR(
            strategy_id=strategy_id,
            name=spec.name,
            description=spec.description,
            nodes=nodes,
            edges=edges,
            variables={"fuzzy_spec": spec.to_dict()},
            config=StrategyConfig(position_sizing="percent"),
        )

    def to_frontend_graph(self, spec: FuzzyStrategySpec) -> Dict[str, Any]:
        nodes: List[Dict[str, Any]] = []
        edges: List[Dict[str, Any]] = []

        x_by_col = [0, 260, 560, 840]
        for i, variable in enumerate(spec.variables):
            node_id = f"fuzzy-var-{variable.name}"
            nodes.append({
                "id": node_id,
                "type": "indicatorNode",
                "position": {"x": x_by_col[0], "y": 80 + i * 130},
                "data": {
                    "label": f"模糊变量: {variable.name}",
                    "indicator": variable.source,
                    "fuzzy": asdict(variable),
                },
            })

        for i, rule in enumerate(spec.rules):
            rule_id = f"fuzzy-rule-{i + 1}"
            nodes.append({
                "id": rule_id,
                "type": "customFunctionNode",
                "position": {"x": x_by_col[1], "y": 80 + i * 150},
                "data": {
                    "label": rule.name,
                    "function": "weighted_fuzzy_rule",
                    "rule": asdict(rule),
                },
            })
            for clause in rule.clauses:
                source = f"fuzzy-var-{clause.variable}"
                edges.append({
                    "id": f"edge-{source}-{rule_id}-{clause.membership}",
                    "source": source,
                    "sourceHandle": "value",
                    "target": rule_id,
                    "targetHandle": "input",
                })

        entry_id = "fuzzy-entry"
        exit_id = "fuzzy-exit"
        nodes.extend([
            {
                "id": entry_id,
                "type": "entryRuleNode",
                "position": {"x": x_by_col[2], "y": 110},
                "data": {"label": "模糊买入评分", "threshold": spec.buy_threshold},
            },
            {
                "id": exit_id,
                "type": "exitRuleNode",
                "position": {"x": x_by_col[2], "y": 300},
                "data": {"label": "模糊卖出评分", "threshold": spec.sell_threshold},
            },
            {
                "id": "fuzzy-position",
                "type": "positionSizeNode",
                "position": {"x": x_by_col[3], "y": 200},
                "data": {"label": "按置信度调仓", "sizing": "confidence_scaled"},
            },
        ])

        for rule in spec.rules:
            rule_id = f"fuzzy-rule-{spec.rules.index(rule) + 1}"
            target = entry_id if rule.action == "buy" else exit_id
            edges.append({
                "id": f"edge-{rule_id}-{target}",
                "source": rule_id,
                "sourceHandle": "output",
                "target": target,
                "targetHandle": "condition",
            })
        edges.append({
            "id": "edge-fuzzy-entry-position",
            "source": entry_id,
            "sourceHandle": "signal",
            "target": "fuzzy-position",
            "targetHandle": "signal",
        })

        return {"nodes": nodes, "edges": edges, "fuzzy_spec": spec.to_dict()}

    def _default_variables(self) -> List[FuzzyVariable]:
        return [
            FuzzyVariable("trend_strength", "ADX", (0, 60), [
                MembershipFunction("weak", "trapezoid", [0, 0, 15, 25]),
                MembershipFunction("medium", "triangular", [18, 30, 42]),
                MembershipFunction("strong", "trapezoid", [35, 45, 60, 60]),
            ]),
            FuzzyVariable("volume_pressure", "volume_ratio_20", (0, 4), [
                MembershipFunction("low", "trapezoid", [0, 0, 0.7, 1.0]),
                MembershipFunction("normal", "triangular", [0.8, 1.1, 1.6]),
                MembershipFunction("high", "trapezoid", [1.4, 2.0, 4.0, 4.0]),
            ]),
            FuzzyVariable("risk_heat", "ATR_pct", (0, 0.12), [
                MembershipFunction("calm", "trapezoid", [0, 0, 0.018, 0.035]),
                MembershipFunction("normal", "triangular", [0.025, 0.05, 0.075]),
                MembershipFunction("hot", "trapezoid", [0.065, 0.09, 0.12, 0.12]),
            ]),
            FuzzyVariable("reversal_pressure", "RSI", (0, 100), [
                MembershipFunction("oversold", "trapezoid", [0, 0, 25, 35]),
                MembershipFunction("neutral", "triangular", [30, 50, 70]),
                MembershipFunction("overbought", "trapezoid", [65, 75, 100, 100]),
            ]),
        ]
