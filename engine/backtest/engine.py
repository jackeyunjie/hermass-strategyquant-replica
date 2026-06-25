"""
回测引擎核心——事件驱动回测框架。

设计为无状态纯函数：输入 StrategyIR + 行情数据，输出 BacktestResult。
支持日线/分钟线数据，适配 A 股 T+1、涨跌停、停牌、除权规则。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from datetime import datetime

import pandas as pd

from ..strategy_builder.strategy_ir import StrategyIR, Node, NodeType, EdgeType
from .common import (
    SignalType,
    TradeRecord,
    BacktestConfig,
    BacktestResult,
    BacktestError,
)
from .rules import (
    RuleChain,
    T1Rule,
    LimitUpDownRule,
    SuspensionRule,
    RightsAdjustmentRule,
)
from .metrics import PerformanceMetrics


class EventDrivenBacktester:
    """事件驱动回测引擎。

    采用逐 K 线事件循环处理：
    1. 接收新行情事件（Bar）。
    2. 根据策略 IR 计算信号。
    3. 应用 A 股交易规则链。
    4. 执行订单、更新持仓、记录资金。
    5. 最终输出 BacktestResult。

    设计为无状态纯函数：每次调用 run() 都是独立的，不保留内部状态。
    """

    def __init__(self, rule_chain: Optional[RuleChain] = None) -> None:
        """初始化回测引擎。

        Args:
            rule_chain: 交易规则链，默认使用 A 股标准规则。
        """
        if rule_chain is None:
            self.rule_chain = RuleChain(
                rules=[
                    T1Rule(),
                    LimitUpDownRule(),
                    SuspensionRule(),
                    RightsAdjustmentRule(),
                ]
            )
        else:
            self.rule_chain = rule_chain

        # 提取除权除息规则引用，以便每 bar 独立调用（不依赖订单）
        self._rights_rule: Optional[RightsAdjustmentRule] = None
        for rule in self.rule_chain.rules:
            if isinstance(rule, RightsAdjustmentRule):
                self._rights_rule = rule
                break

    def run(
        self,
        strategy_ir: StrategyIR,
        data: pd.DataFrame,
        config: Optional[BacktestConfig] = None,
    ) -> BacktestResult:
        """执行回测。

        逐 Bar 处理顺序：
        1. 计算信号（基于当前 bar 数据，防未来函数）。
        2. 应用规则链。
        3. 执行订单（A 股手数取整）。
        4. 更新持仓/市值。
        5. 记录资金曲线。

        Args:
            strategy_ir: 策略中间表示。
            data: 行情数据 DataFrame，要求包含 columns：
                  [open, high, low, close, volume, symbol, timestamp, ...]
                  且必须包含 A 股规则所需的辅助列：
                  [limit_up, limit_down, is_suspended, adjustment_factor]
            config: 回测配置，未提供则使用默认。

        Returns:
            BacktestResult: 包含资金曲线、交易记录、绩效指标。
        """
        if data is None or data.empty:
            raise BacktestError("Input data is empty or None.")

        cfg = config or BacktestConfig()
        df = data.copy().sort_values("timestamp").reset_index(drop=True)

        cash = cfg.initial_capital
        equity = cfg.initial_capital
        positions: Dict[str, Dict[str, Any]] = {}
        trades: List[TradeRecord] = []
        equity_records: List[Dict[str, Any]] = []
        trade_counter = 0

        for _, bar in df.iterrows():
            ts = bar["timestamp"]
            if isinstance(ts, str):
                ts = pd.to_datetime(ts)
            symbol = str(bar.get("symbol", "UNKNOWN"))
            close_price = float(bar["close"])

            # 除权除息需每 bar 检查（不依赖订单）
            if self._rights_rule is not None:
                self._rights_rule.check(
                    order={"action": "hold", "symbol": symbol, "price": close_price},
                    bar=bar,
                    positions=positions,
                    cash=cash,
                    config=cfg,
                )

            # 1. 策略信号生成（从 IR 递归解析）
            signal = self._evaluate_strategy_ir(strategy_ir, bar, positions)

            # 2. 构建候选订单
            order: Optional[Dict[str, Any]] = None
            if signal == SignalType.BUY:
                order = {
                    "action": "buy",
                    "symbol": symbol,
                    "price": close_price,
                }
            elif signal == SignalType.SELL and symbol in positions:
                order = {
                    "action": "sell",
                    "symbol": symbol,
                    "price": close_price,
                }

            # 3. 应用规则链
            if order is not None:
                order = self.rule_chain.apply(
                    order=order,
                    bar=bar,
                    positions=positions,
                    cash=cash,
                    config=cfg,
                )

            # 4. 执行订单
            if order is not None and order.get("action") in ("buy", "sell"):
                action = order["action"]
                exec_price = float(order.get("price", close_price))

                # 滑点：买入加价，卖出降价
                slippage_amount = exec_price * cfg.slippage
                if action == "buy":
                    exec_price += slippage_amount
                else:
                    exec_price -= slippage_amount

                # 仓位计算（A 股手数取整）
                if cfg.position_sizing == "fixed_value":
                    max_invest = cash * (1 - cfg.cash_reserve_ratio)
                    shares = int(max_invest / exec_price / 100) * 100
                elif cfg.position_sizing == "percent":
                    target_value = equity * 0.1
                    shares = int(target_value / exec_price / 100) * 100
                else:
                    shares = 100

                if action == "buy":
                    if shares <= 0:
                        order = None
                    else:
                        amount = exec_price * shares
                        commission = amount * cfg.commission_rate
                        total_slippage = slippage_amount * shares
                        total_cost = amount + commission + total_slippage
                        if cash >= total_cost:
                            cash -= total_cost
                            if symbol in positions:
                                pos = positions[symbol]
                                old_shares = pos["shares"]
                                old_cost = pos["entry_price"] * old_shares
                                new_cost = (
                                    old_cost + amount + commission + total_slippage
                                )
                                new_shares = old_shares + shares
                                positions[symbol] = {
                                    "shares": new_shares,
                                    "entry_price": new_cost / new_shares,
                                    "entry_time": ts,
                                    "last_buy_date": ts,
                                }
                            else:
                                positions[symbol] = {
                                    "shares": shares,
                                    "entry_price": exec_price,
                                    "entry_time": ts,
                                    "last_buy_date": ts,
                                }
                            trade_counter += 1
                            trades.append(
                                TradeRecord(
                                    trade_id=f"T{trade_counter:05d}",
                                    timestamp=ts,
                                    symbol=symbol,
                                    signal=SignalType.BUY,
                                    price=exec_price,
                                    shares=shares,
                                    commission=commission,
                                    slippage=total_slippage,
                                    reason=order.get("reason", "signal"),
                                )
                            )
                        else:
                            order = None
                elif action == "sell":
                    pos = positions.get(symbol)
                    if pos and pos["shares"] > 0:
                        sell_shares = pos["shares"]
                        sell_amount = exec_price * sell_shares
                        commission = sell_amount * cfg.commission_rate
                        # 印花税：A 股卖出单边 0.05%
                        stamp_tax = sell_amount * 0.0005
                        total_slippage = slippage_amount * sell_shares
                        total_costs = commission + stamp_tax + total_slippage
                        cash += sell_amount - total_costs
                        del positions[symbol]

                        trade_counter += 1
                        trades.append(
                            TradeRecord(
                                trade_id=f"T{trade_counter:05d}",
                                timestamp=ts,
                                symbol=symbol,
                                signal=SignalType.SELL,
                                price=exec_price,
                                shares=sell_shares,
                                commission=commission,
                                slippage=total_slippage,
                                reason=order.get("reason", "signal"),
                            )
                        )
                    else:
                        order = None

            # 5. 更新市值与资金曲线
            market_value = 0.0
            for sym, pos in positions.items():
                # MVP：单资产，使用当前 bar 收盘价估算市值
                # 多资产场景需根据 symbol 匹配对应价格
                market_value += pos["shares"] * close_price
            equity = cash + market_value

            equity_records.append(
                {
                    "timestamp": ts,
                    "equity": equity,
                    "cash": cash,
                    "market_value": market_value,
                }
            )

        # 6. 计算绩效指标
        equity_curve = pd.DataFrame(equity_records)
        if equity_curve.empty:
            equity_curve = pd.DataFrame(
                columns=["timestamp", "equity", "cash", "market_value"]
            )

        metrics = PerformanceMetrics.from_equity_curve(equity_curve, trades)

        return BacktestResult(
            equity_curve=equity_curve,
            trades=trades,
            metrics=metrics,
            strategy_ir=strategy_ir,
            config=cfg,
        )

    def _evaluate_strategy_ir(
        self,
        strategy_ir: StrategyIR,
        bar: pd.Series,
        positions: Dict[str, Dict[str, Any]],
    ) -> SignalType:
        """根据 StrategyIR 和当前行情 bar 计算交易信号。

        递归解析策略树，支持节点类型：
        - INDICATOR：从 bar 的 IND_{name} 列读取指标值
        - VALUE：常数
        - OPERATOR：AND, OR, NOT, GT, LT, EQ, GTE, LTE, NEQ
        - CONDITION：IF-THEN-ELSE（支持 EdgeType 区分分支）
        - ACTION：BUY, SELL, HOLD

        Args:
            strategy_ir: 策略中间表示。
            bar: 当前 K 线数据。
            positions: 当前持仓状态。

        Returns:
            SignalType: 交易信号。
        """
        if strategy_ir is None:
            return SignalType.HOLD

        root = strategy_ir.get_root()
        if root is None:
            return SignalType.HOLD

        def _get_children(node_id: str) -> List[Node]:
            """获取某节点的所有直接子节点（CHILD 边类型）。"""
            child_ids = {
                e.target
                for e in strategy_ir.edges
                if e.source == node_id and e.edge_type == EdgeType.CHILD
            }
            # 兼容未明确标注 edge_type 的边
            child_ids.update(
                e.target
                for e in strategy_ir.edges
                if e.source == node_id
                and e.edge_type not in (EdgeType.THEN, EdgeType.ELSE, EdgeType.PARAM)
            )
            return [n for n in strategy_ir.nodes if n.id in child_ids]

        def _get_child_by_edge_type(
            node_id: str, edge_type: EdgeType
        ) -> Optional[Node]:
            """按指定边类型获取子节点。"""
            for e in strategy_ir.edges:
                if e.source == node_id and e.edge_type == edge_type:
                    return strategy_ir.find_node(e.target)
            return None

        def _eval_node(node: Node) -> Any:
            """递归求值策略树节点。

            Args:
                node: 当前节点。

            Returns:
                Any: 节点求值结果（布尔值、数值或字符串）。
            """
            if node is None:
                return SignalType.HOLD

            if node.node_type == NodeType.ROOT:
                children = _get_children(node.id)
                if not children:
                    return SignalType.HOLD
                return _eval_node(children[0])

            elif node.node_type == NodeType.INDICATOR:
                col_name = f"IND_{node.name}"
                val = bar.get(col_name)
                if val is None or pd.isna(val):
                    val = bar.get(node.name, 0.0)
                return float(val)

            elif node.node_type == NodeType.VALUE:
                return float(node.params.get("value", 0.0))

            elif node.node_type == NodeType.OPERATOR:
                op_name = node.name.upper()
                children = _get_children(node.id)

                if op_name == "NOT":
                    if len(children) < 1:
                        return False
                    return not bool(_eval_node(children[0]))

                if len(children) < 2:
                    return False

                left = _eval_node(children[0])
                right = _eval_node(children[1])

                if op_name in ("GT", "GREATER_THAN"):
                    return left > right
                elif op_name in ("LT", "LESS_THAN"):
                    return left < right
                elif op_name in ("EQ", "EQUAL", "EQUALS"):
                    return left == right
                elif op_name in ("GTE", "GE", "GREATER_THAN_OR_EQUAL"):
                    return left >= right
                elif op_name in ("LTE", "LE", "LESS_THAN_OR_EQUAL"):
                    return left <= right
                elif op_name in ("AND",):
                    return bool(left) and bool(right)
                elif op_name in ("OR",):
                    return bool(left) or bool(right)
                elif op_name in ("NEQ", "NOT_EQUAL", "NOT_EQUALS"):
                    return left != right
                else:
                    return False

            elif node.node_type == NodeType.CONDITION:
                # IF-THEN-ELSE 结构
                cond_node = _get_child_by_edge_type(node.id, EdgeType.CHILD)
                then_node = _get_child_by_edge_type(node.id, EdgeType.THEN)
                else_node = _get_child_by_edge_type(node.id, EdgeType.ELSE)

                # 若边类型未明确标注，回退到按顺序解析
                if cond_node is None:
                    all_children = [
                        n
                        for n in strategy_ir.nodes
                        if any(
                            e.source == node.id and e.target == n.id
                            for e in strategy_ir.edges
                        )
                    ]
                    if len(all_children) < 3:
                        return SignalType.HOLD
                    cond_node = all_children[0]
                    then_node = all_children[1]
                    else_node = all_children[2]

                condition = bool(_eval_node(cond_node))
                if condition:
                    return _eval_node(then_node) if then_node else SignalType.HOLD
                else:
                    return _eval_node(else_node) if else_node else SignalType.HOLD

            elif node.node_type == NodeType.ACTION:
                action_name = node.name.upper()
                if action_name == "BUY":
                    return "BUY"
                elif action_name == "SELL":
                    return "SELL"
                else:
                    return "HOLD"

            else:
                return SignalType.HOLD

        result = _eval_node(root)
        if result == "BUY":
            return SignalType.BUY
        elif result == "SELL":
            return SignalType.SELL
        else:
            return SignalType.HOLD
