# 量化策略稳健性测试技术调研报告

> 基于 StrategyQuant Robustness Testing 功能的开源实现方案深度分析  
> 调研日期：2026-06-24  
> 版本：v1.0

---

## 目录

- [1. 执行摘要](#1-执行摘要)
- [2. Monte Carlo 模拟](#2-monte-carlo-模拟)
- [3. Walk-Forward 分析](#3-walk-forward-分析)
- [4. 系统参数排列 (SPP)](#4-系统参数排列-spp)
- [5. 优化轮廓分析](#5-优化轮廓分析)
- [6. 多 OOS 样本外测试](#6-多-oos-样本外测试)
- [7. 过拟合检测指标体系](#7-过拟合检测指标体系)
- [8. 开源实现方案调研](#8-开源实现方案调研)
- [9. 自动化集成方案](#9-自动化集成方案)
- [10. GPU/并行计算加速](#10-gpu并行计算加速)
- [11. 代码量级与模块划分](#11-代码量级与模块划分)
- [12. 参考文献](#12-参考文献)

---

## 1. 执行摘要

StrategyQuant 的 Robustness Testing（稳健性测试）是自动化策略生成流程中的核心质量控制环节，旨在通过系统化的统计检验识别并过滤过拟合策略。本报告针对其六大核心功能模块，深入调研了每项技术的数学原理、开源实现路径以及工程化建议。

**核心发现**：

| 功能模块 | 数学原理 | 计算复杂度 | 推荐开源基础 |
|---------|---------|-----------|-------------|
| Monte Carlo 模拟 | 重采样/随机扰动 | O(N·T) | VectorBT + Numba |
| Walk-Forward 分析 | 滚动优化+OOS验证 | O(W·P·T) | Backtrader + sklearn |
| SPP 系统参数排列 | 全参数空间遍历 | O(∏nᵢ) | VectorBT + Dask |
| 优化轮廓分析 | 分布统计+景观可视化 | O(∏nᵢ) | Plotly + NumPy |
| 多 OOS 测试 | 时间序列交叉验证 | O(K·T) | 自定义框架 |
| 过拟合检测 | 假设检验/贝叶斯推断 | O(M·T) | MLFinLab + SciPy |

**关键技术选型建议**：
- 高性能回测引擎：**VectorBT**（Numba/Rust 加速，向量化回测，支持秒级千策略测试）[^1]
- 参数优化与 WFO：**Backtrader** + **Optuna**（成熟的事件驱动架构，完善的 WFO 模块）[^2]
- 过拟合检测：**MLFinLab**（内置 CPCV、PBO、DSR 实现，直接复用 Marcos López de Prado 的学术成果）[^3]
- 并行计算：**Dask**（分布式任务调度）+ **Numba CUDA**（GPU 核函数）[^4]

---

## 2. Monte Carlo 模拟

### 2.1 数学原理

Monte Carlo 模拟通过引入随机扰动来测试策略对执行变异和数据噪声的鲁棒性。其核心思想是：如果策略的真实优势（edge）是统计显著的，那么在各种合理的随机扰动下，其绩效指标应保持相对稳定。

StrategyQuant 实现了两类 Monte Carlo 测试：

**A. 交易序列操作类（Trades Manipulation）**
基于已完成的回测交易列表，通过随机操作生成替代性权益曲线：

1. **随机化交易顺序（Randomize Trades Order）**  
   将原始交易序列打乱重排，保持单笔交易的盈亏值不变。数学上，这等价于对交易序列进行随机排列（permutation）。若策略权益曲线对交易顺序高度敏感，则存在运气成分。

2. **随机跳过交易（Randomly Skip Trades）**  
   以概率 $p$ 随机跳过每笔交易，模拟实际执行中因网络故障、平台问题或人为暂停导致的漏单。设原始交易序列为 $T = \{t_1, t_2, ..., t_n\}$，模拟后的子序列为 $T' \subseteq T$，其中 $P(t_i \in T') = 1-p$。

3. **MACHR 块随机化（Block Randomization）**  
   将交易序列按时间划分为 $m$ 个块（blocks），在每个块内部随机打乱交易顺序。这保留了局部市场制度（regime）的连续性，同时测试制度内部的交易顺序敏感性。

**B. 重测方法类（Retest Methods）**
每次模拟需要完整重新运行回测，计算复杂度更高：

4. **随机化起始柱（Randomize Starting Bar）**  
   在 $[0, \Delta_{max}]$ 范围内随机选择起始柱偏移量 $\delta$，测试策略对起始点的敏感性。稳健的策略不应因起始时间微小偏移而显著改变绩效。

5. **随机化策略参数（Randomize Strategy Parameters）**  
   对每个参数 $p_i$ 以概率 $q$ 进行扰动：$p_i' = p_i \cdot (1 + \epsilon)$，其中 $\epsilon \sim U[-\alpha, +\alpha]$，$\alpha$ 为最大参数变化百分比。这测试策略参数空间的局部稳定性。

6. **随机化历史数据（Randomize History Data）**  
   对每根 K 线的 OHLC 价格以概率 $r$ 施加基于 ATR 的噪声：$price' = price + ATR \cdot \beta \cdot \mathcal{N}(0,1)$，其中 $\beta$ 为最大价格变化百分比。这是检验策略是否过度拟合特定价格路径的核心方法。

7. **随机化滑点/点差（Randomize Slippage & Spread）**  
   在每次模拟中随机生成交易成本和点差，模拟不同流动性环境。

8. **SWAP 随机化**  
   对持仓过夜策略，在每次模拟中使用一致的随机 SWAP 利率，测试利率环境变化的敏感性。

9. **执行退化模拟（Execution Degradation）**  
   系统性地增加滑点、延迟和佣金，模拟真实交易环境的摩擦成本。

### 2.2 实现方案

```python
"""
Monte Carlo 稳健性测试引擎 — 核心架构
"""
import numpy as np
from numba import njit, prange
from dataclasses import dataclass
from typing import List, Callable, Dict, Tuple
import vectorbt as vbt


@dataclass
class MCSimulationResult:
    """单次 Monte Carlo 模拟结果"""
    net_profit: float
    sharpe_ratio: float
    max_drawdown: float
    profit_factor: float
    win_rate: float
    return_on_dd: float


class MonteCarloEngine:
    """
    Monte Carlo 稳健性测试引擎
    
    支持两种模式：
    1. Trades Manipulation: 基于交易列表的操作（轻量级）
    2. Retest Methods: 需要完整回测的扰动（重量级）
    """
    
    def __init__(self, 
                 backtest_fn: Callable,
                 n_simulations: int = 1000,
                 random_state: int = 42):
        self.backtest_fn = backtest_fn  # 策略回测函数
        self.n_simulations = n_simulations
        self.rng = np.random.RandomState(random_state)
        
    # ========== Trades Manipulation 方法 ==========
    
    def shuffle_trades(self, trades: np.ndarray) -> np.ndarray:
        """随机化交易顺序 — 保持单笔盈亏不变"""
        return self.rng.permutation(trades)
    
    def skip_trades(self, trades: np.ndarray, 
                    skip_prob: float = 0.1) -> np.ndarray:
        """随机跳过交易 — 模拟执行漏单"""
        mask = self.rng.random(len(trades)) > skip_prob
        return trades[mask]
    
    def block_shuffle(self, trades: np.ndarray,
                      n_blocks: int = 10) -> np.ndarray:
        """MACHR 块随机化 — 保留局部制度连续性"""
        block_size = len(trades) // n_blocks
        result = []
        for i in range(n_blocks):
            start = i * block_size
            end = start + block_size if i < n_blocks - 1 else len(trades)
            block = trades[start:end].copy()
            self.rng.shuffle(block)
            result.extend(block)
        return np.array(result)
    
    # ========== Retest Methods 方法 ==========
    
    def perturb_params(self, params: Dict[str, float],
                       perturb_prob: float = 0.3,
                       max_change_pct: float = 0.10) -> Dict[str, float]:
        """随机化策略参数"""
        perturbed = params.copy()
        for key, val in perturbed.items():
            if self.rng.random() < perturb_prob:
                change = self.rng.uniform(-max_change_pct, max_change_pct)
                perturbed[key] = val * (1 + change)
        return perturbed
    
    def perturb_ohlc(self, ohlc: np.ndarray,
                     atr: np.ndarray,
                     prob: float = 0.05,
                     max_change_pct: float = 0.20) -> np.ndarray:
        """随机化历史数据 — 基于 ATR 的噪声注入"""
        perturbed = ohlc.copy()
        for bar_idx in range(len(ohlc)):
            if self.rng.random() < prob:
                noise = atr[bar_idx] * max_change_pct * self.rng.normal()
                # 仅扰动 close，保持 open/high/low 逻辑一致性
                perturbed[bar_idx, 3] += noise  # close
        return perturbed
    
    def run_simulation(self, method: str, 
                       base_data,
                       **kwargs) -> List[MCSimulationResult]:
        """
        运行 Monte Carlo 模拟
        
        返回所有模拟的绩效分布，用于计算百分位数和置信区间
        """
        results = []
        for i in range(self.n_simulations):
            if method == 'shuffle_trades':
                sim_trades = self.shuffle_trades(base_data)
                result = self._trades_to_metrics(sim_trades)
            elif method == 'skip_trades':
                sim_trades = self.skip_trades(base_data, kwargs['skip_prob'])
                result = self._trades_to_metrics(sim_trades)
            elif method == 'randomize_params':
                sim_params = self.perturb_params(base_data, **kwargs)
                result = self.backtest_fn(sim_params)
            elif method == 'randomize_data':
                sim_ohlc = self.perturb_ohlc(base_data, **kwargs)
                result = self.backtest_fn(sim_ohlc)
            else:
                raise ValueError(f"Unknown method: {method}")
            results.append(result)
        return results
    
    def evaluate_robustness(self, results: List[MCSimulationResult],
                            original: MCSimulationResult) -> Dict:
        """
        评估稳健性 — 核心统计指标
        """
        profits = np.array([r.net_profit for r in results])
        sharpes = np.array([r.sharpe_ratio for r in results])
        
        return {
            # 百分位数分析
            'profit_pct5': np.percentile(profits, 5),
            'profit_pct50': np.percentile(profits, 50),
            'profit_pct95': np.percentile(profits, 95),
            
            # 标准差分析（越低越稳健）
            'profit_std': np.std(profits),
            'sharpe_std': np.std(sharpes),
            
            # 盈利模拟比例
            'profitable_pct': np.mean(profits > 0) * 100,
            
            # 最差情况分析
            'worst_drawdown': np.min([r.max_drawdown for r in results]),
            
            # 与原始结果对比
            'profit_ratio_vs_original': np.median(profits) / original.net_profit,
            'sharpe_ratio_vs_original': np.median(sharpes) / original.sharpe_ratio,
        }
```

### 2.3 关键统计判据

| 判据 | 阈值建议 | 说明 |
|------|---------|------|
| 盈利模拟比例 | ≥ 80% | 至少 80% 的模拟保持盈利 |
| 利润中位数/原始利润 | ≥ 0.7 | 中位数表现不低于原始 70% |
| 夏普比率中位数/原始 | ≥ 0.7 | 经风险调整后的稳健性 |
| 5% 分位数利润 | > 0 | 最坏 5% 情况仍盈利 |
| 利润标准差 | < 原始利润 × 0.5 | 变异系数控制 |

---

## 3. Walk-Forward 分析

### 3.1 数学原理

Walk-Forward Optimization（WFO）通过滚动窗口机制将历史数据划分为多个 In-Sample（IS）优化期与 Out-of-Sample（OOS）测试期，模拟策略在实际运行中定期重新优化的场景。

**基本框架**：

设总历史数据长度为 $T$，划分为 $W$ 个窗口。每个窗口 $w$ 包含：
- IS（训练）期：$[t_{w}^{start}, t_{w}^{IS,end}]$，长度 $T_{IS}$
- OOS（测试）期：$[t_{w}^{IS,end}+1, t_{w}^{end}]$，长度 $T_{OOS}$
- 窗口递进量：$\Delta$（每步前进的数据量）

**WFO 效率比（WFER / Walk-Forward Efficiency Ratio）**：

$$
WFER = \frac{\text{Performance}_{OOS}}{\text{Performance}_{IS}}
$$

WFER 是 WFO 分析的核心指标。若 WFER 接近 1.0，说明策略在样本外的表现与样本内一致，参数稳定性高；若 WFER 显著低于 1.0（如 < 0.5），则存在过拟合或市场制度变迁。

**WFO 矩阵（Walk-Forward Matrix）**：

WFO 矩阵是 WFO 的扩展形式，通过系统地改变 $(T_{IS}, T_{OOS}, \Delta)$ 的组合，构建一个三维的稳健性评估景观。矩阵中的每个单元格代表一组特定窗口配置下的 WFER 值。

通过聚类分析（cluster analysis）可以识别：
- **稳定参数区**：WFER  consistently 高的参数组合区域
- **脆弱区**：WFER 波动大或普遍低的区域
- **过拟合区**：仅在极特定窗口配置下表现优异的区域

### 3.2 实现方案

```python
"""
Walk-Forward 分析与矩阵实现
"""
import numpy as np
import pandas as pd
from sklearn.model_selection import TimeSeriesSplit
from typing import Dict, List, Callable, Any
from dataclasses import dataclass
from itertools import product


@dataclass
class WFOWindow:
    """单个 WFO 窗口配置"""
    is_length: int        # IS 期长度（交易日/数据点数）
    oos_length: int       # OOS 期长度
    step: int             # 窗口递进步长
    

@dataclass  
class WFOWindowResult:
    """单个窗口的回测结果"""
    window_idx: int
    train_start: pd.Timestamp
    train_end: pd.Timestamp
    test_start: pd.Timestamp
    test_end: pd.Timestamp
    optimal_params: Dict[str, Any]
    train_performance: Dict[str, float]
    test_performance: Dict[str, float]
    wfer: float


class WalkForwardEngine:
    """
    Walk-Forward 优化引擎
    
    支持：
    1. 标准 WFO（单窗口配置）
    2. WFO 矩阵（多窗口配置聚类分析）
    3. 参数轨迹分析
    """
    
    def __init__(self,
                 strategy_fn: Callable,
                 optimize_fn: Callable,
                 evaluate_fn: Callable,
                 param_grid: Dict[str, List]):
        self.strategy_fn = strategy_fn      # 策略构建函数
        self.optimize_fn = optimize_fn      # 优化函数（返回最优参数）
        self.evaluate_fn = evaluate_fn      # 评估函数（返回绩效指标）
        self.param_grid = param_grid        # 参数搜索空间
        
    def standard_wfo(self, 
                     data: pd.DataFrame,
                     window: WFOWindow,
                     metric: str = 'sharpe_ratio') -> List[WFOWindowResult]:
        """
        标准 Walk-Forward 优化
        
        流程：
        1. 按 step 滑动窗口
        2. 在 IS 期执行参数优化
        3. 用最优参数在 OOS 期回测
        4. 记录 WFER 和参数轨迹
        """
        n = len(data)
        results = []
        window_idx = 0
        
        for start_idx in range(0, n - window.is_length - window.oos_length + 1, window.step):
            is_start = start_idx
            is_end = start_idx + window.is_length
            oos_start = is_end
            oos_end = min(oos_start + window.oos_length, n)
            
            # IS 期优化
            train_data = data.iloc[is_start:is_end]
            optimal_params = self.optimize_fn(
                train_data, self.param_grid, self.evaluate_fn, metric
            )
            
            # IS 期绩效（最优参数）
            train_perf = self.evaluate_fn(train_data, optimal_params)
            
            # OOS 期测试
            test_data = data.iloc[oos_start:oos_end]
            test_perf = self.evaluate_fn(test_data, optimal_params)
            
            # WFER 计算
            wfer = test_perf[metric] / train_perf[metric] if train_perf[metric] != 0 else 0
            
            results.append(WFOWindowResult(
                window_idx=window_idx,
                train_start=train_data.index[0],
                train_end=train_data.index[-1],
                test_start=test_data.index[0],
                test_end=test_data.index[-1],
                optimal_params=optimal_params,
                train_performance=train_perf,
                test_performance=test_perf,
                wfer=wfer
            ))
            window_idx += 1
            
        return results
    
    def wfo_matrix(self, 
                   data: pd.DataFrame,
                   is_lengths: List[int],
                   oos_lengths: List[int],
                   steps: List[int],
                   metric: str = 'sharpe_ratio') -> pd.DataFrame:
        """
        WFO 矩阵 — 系统性地遍历所有窗口配置组合
        
        输出：DataFrame，每行一个 (is_length, oos_length, step) 组合，
              包含平均 WFER、WFER 标准差、参数稳定性评分等
        """
        matrix_results = []
        
        for is_len, oos_len, step in product(is_lengths, oos_lengths, steps):
            if is_len + oos_len > len(data):
                continue
                
            window = WFOWindow(is_length=is_len, oos_length=oos_len, step=step)
            wfo_results = self.standard_wfo(data, window, metric)
            
            # 聚合该窗口配置下的统计量
            wfers = [r.wfer for r in wfo_results]
            param_stability = self._compute_param_stability(wfo_results)
            
            matrix_results.append({
                'is_length': is_len,
                'oos_length': oos_len,
                'step': step,
                'n_windows': len(wfo_results),
                'mean_wfer': np.mean(wfers),
                'std_wfer': np.std(wfers),
                'min_wfer': np.min(wfers),
                'pct_wfer_gt_0_5': np.mean(np.array(wfers) > 0.5),
                'param_stability': param_stability,
                'overall_score': np.mean(wfers) * (1 - np.std(wfers)) * param_stability
            })
            
        return pd.DataFrame(matrix_results)
    
    def _compute_param_stability(self, 
                                  results: List[WFOWindowResult]) -> float:
        """
        参数稳定性评分 — 衡量参数轨迹的平滑程度
        
        思路：计算相邻窗口参数变化的平均幅度，
              变化越小，参数越稳定，评分越高
        """
        if len(results) < 2:
            return 1.0
            
        param_changes = []
        for i in range(1, len(results)):
            prev_params = results[i-1].optimal_params
            curr_params = results[i].optimal_params
            
            # 归一化参数变化
            for key in prev_params:
                if key in curr_params and prev_params[key] != 0:
                    rel_change = abs(curr_params[key] - prev_params[key]) / abs(prev_params[key])
                    param_changes.append(rel_change)
                    
        if not param_changes:
            return 1.0
            
        mean_change = np.mean(param_changes)
        # 稳定性评分：变化越小，评分越高（指数衰减）
        stability = np.exp(-mean_change * 5)
        return stability
```

### 3.3 WFO 矩阵聚类解读

| 景观特征 | 含义 | 决策建议 |
|---------|------|---------|
| 宽阔平坦的高原 | 参数稳定区，多配置均表现良好 | 优先选择该区域中心参数 |
| 尖锐孤立的峰 | 过拟合风险，仅特定配置有效 | 避免使用 |
| 阶梯状分布 | 存在制度转换阈值 | 设置动态参数切换机制 |
| 随机散点 | 策略无真实优势 | 直接放弃 |

---

## 4. 系统参数排列 (SPP)

### 4.1 数学原理

System Parameter Permutation（SPP）由 Dave Walton 提出（Wagner Award 获奖论文），其核心思想是：

> **仅通过策略当前的最优参数无法判断其是否具有真实优势。必须遍历所有参数组合，从完整的优化结果分布中推断策略的真实预期绩效。**

**数学描述**：

设策略有 $k$ 个可优化参数，每个参数 $i$ 的搜索空间为 $S_i = \{v_{i,1}, v_{i,2}, ..., v_{i,n_i}\}$。全参数组合空间大小为：

$$
N_{total} = \prod_{i=1}^{k} n_i
$$

对每个参数组合 $j \in \{1, ..., N_{total}\}$，执行一次完整回测，获得绩效指标向量 $\mathbf{P}_j = (P_{j,1}, P_{j,2}, ..., P_{j,m})$（如净利润、夏普比率、最大回撤等）。

**SPP 核心统计量**：

对每个绩效指标 $l$，构建采样分布 $\{P_{1,l}, P_{2,l}, ..., P_{N_{total},l}\}$，计算：

- **中位数（Median）**：$\tilde{P}_l = \text{median}(\{P_{j,l}\})$ — 被 Walton 视为真实绩效的最合理估计
- **均值（Mean）**：$\bar{P}_l = \frac{1}{N_{total}} \sum_{j} P_{j,l}$
- **标准差（Std）**：$\sigma_l = \sqrt{\frac{1}{N_{total}} \sum_{j} (P_{j,l} - \bar{P}_l)^2}$
- **显著性比例**：$\frac{\#(P_{j,l} > 0)}{N_{total}}$ — 盈利参数组合的比例

**关键洞察**：
如果策略具有真实优势，那么即使在非最优参数下，策略仍应大概率盈利（即盈利参数组合比例显著高于 50%）。如果仅在最优参数附近盈利，则该"优势"很可能是数据挖掘的假象。

### 4.2 实现方案

```python
"""
System Parameter Permutation (SPP) 实现

参考文献：
- Walton, D. "Know your System! – Turning Data Mining from Bias to Benefit"
  (Wagner Award 2012)
"""
import numpy as np
import pandas as pd
from itertools import product
from typing import Dict, List, Callable
from dataclasses import dataclass
from collections import defaultdict


@dataclass
class SPPResult:
    """SPP 分析结果"""
    # 中位数统计量（核心输出）
    median_net_profit: float
    median_sharpe_ratio: float
    median_max_drawdown: float
    median_profit_factor: float
    median_return_on_dd: float
    
    # 分布统计量
    mean_net_profit: float
    std_net_profit: float
    profitable_pct: float          # 盈利组合比例
    sharpe_positive_pct: float     # 夏普为正比例
    
    # 原始分布数据（用于直方图和假设检验）
    distribution: pd.DataFrame
    

class SPPEngine:
    """
    系统参数排列引擎
    
    执行全参数空间遍历，构建采样分布
    """
    
    def __init__(self, 
                 backtest_fn: Callable,
                 param_grid: Dict[str, List]):
        self.backtest_fn = backtest_fn
        self.param_grid = param_grid
        
    def run(self, data, progress_callback=None) -> SPPResult:
        """
        执行 SPP 分析
        
        警告：当参数空间很大时，计算量呈指数增长。
              建议使用随机采样或超立方采样（LHS）作为近似。
        """
        # 生成所有参数组合
        param_names = list(self.param_grid.keys())
        param_values = [self.param_grid[k] for k in param_names]
        all_combinations = list(product(*param_values))
        
        n_total = len(all_combinations)
        results = []
        
        for idx, combo in enumerate(all_combinations):
            params = dict(zip(param_names, combo))
            
            # 执行回测
            perf = self.backtest_fn(data, params)
            
            perf['params'] = params
            results.append(perf)
            
            if progress_callback and idx % 100 == 0:
                progress_callback(idx, n_total)
                
        df = pd.DataFrame(results)
        
        # 计算核心统计量
        net_profits = df['net_profit'].values
        sharpes = df['sharpe_ratio'].values
        drawdowns = df['max_drawdown'].values
        
        return SPPResult(
            median_net_profit=np.median(net_profits),
            median_sharpe_ratio=np.median(sharpes),
            median_max_drawdown=np.median(drawdowns),
            median_profit_factor=np.median(df['profit_factor'].values),
            median_return_on_dd=np.median(df['return_on_dd'].values),
            
            mean_net_profit=np.mean(net_profits),
            std_net_profit=np.std(net_profits),
            profitable_pct=np.mean(net_profits > 0) * 100,
            sharpe_positive_pct=np.mean(sharpes > 0) * 100,
            
            distribution=df
        )
    
    def approximate_with_lhs(self, data, n_samples: int = 1000,
                              random_state: int = 42) -> SPPResult:
        """
        拉丁超立方采样（Latin Hypercube Sampling）近似
        
        当全参数空间过大时，用 LHS 均匀采样代替穷举，
        在保证覆盖性的同时大幅降低计算量。
        """
        from scipy.stats import qmc
        
        param_names = list(self.param_grid.keys())
        n_params = len(param_names)
        
        # 生成 LHS 样本（在 [0,1]^n 均匀分布）
        sampler = qmc.LatinHypercube(d=n_params, seed=random_state)
        samples = sampler.random(n=n_samples)
        
        # 将 [0,1] 映射到实际参数值
        results = []
        for sample in samples:
            params = {}
            for i, name in enumerate(param_names):
                values = self.param_grid[name]
                idx = int(sample[i] * (len(values) - 1))
                params[name] = values[idx]
            
            perf = self.backtest_fn(data, params)
            perf['params'] = params
            results.append(perf)
            
        df = pd.DataFrame(results)
        
        # 计算统计量（与穷举版本相同）
        net_profits = df['net_profit'].values
        sharpes = df['sharpe_ratio'].values
        
        return SPPResult(
            median_net_profit=np.median(net_profits),
            median_sharpe_ratio=np.median(sharpes),
            median_max_drawdown=np.median(df['max_drawdown'].values),
            median_profit_factor=np.median(df['profit_factor'].values),
            median_return_on_dd=np.median(df['return_on_dd'].values),
            mean_net_profit=np.mean(net_profits),
            std_net_profit=np.std(net_profits),
            profitable_pct=np.mean(net_profits > 0) * 100,
            sharpe_positive_pct=np.mean(sharpes > 0) * 100,
            distribution=df
        )
```

### 4.3 SPP 判据

| 判据 | 稳健策略应满足 | 说明 |
|------|--------------|------|
| 盈利组合比例 | > 50%（最好 > 60%） | 多数参数组合都应盈利 |
| 夏普为正比例 | > 50% | 经风险调整后仍有效 |
| 中位数净利润/最优净利润 | > 0.5 | 最优结果不是异常值 |
| 净利润分布均匀性 | 标准差小 | 结果不过度依赖特定参数 |
| 中位数回撤 | 可接受 | 真实回撤预期 |

---

## 5. 优化轮廓分析

### 5.1 数学原理

Optimization Profile（优化轮廓）由 Robert Pardo 提出，是对优化结果分布的系统化评估。StrategyQuant 在每次优化后自动生成优化轮廓，无需额外操作。

**五大评估标准**（Pardo 原文）：

1. **正收益优化运行比例**  
   设总优化运行次数为 $N$，净利润为正的运行次数为 $N^+$，则：
   $$
   R_{positive} = \frac{N^+}{N}
   $$
   稳健策略应满足 $R_{positive} > 0.5$，理想情况下 > 0.7。逻辑：真实优势应体现在广泛的参数空间中。

2. **所有优化运行的平均利润 > 0**
   $$
   \bar{P} = \frac{1}{N} \sum_{i=1}^{N} P_i > 0
   $$
   即使包含亏损运行，整体平均仍应为正。

3. **利润分布尽可能均匀**  
   理想情况下，利润分布应呈现连续形态，不存在"从正跳到负"的突变。可用相邻运行的利润符号变化频率来衡量：
   $$
   S_{uniform} = 1 - \frac{\#(P_i \cdot P_{i+1} < 0)}{N-1}
   $$
   $S_{uniform}$ 越接近 1，分布越均匀。

4. **最优结果不应过度偏离平均**  
   最优净利润 $P_{max}$ 与平均净利润 $\bar{P}$ 的比值应控制在合理范围：
   $$
   \frac{P_{max} - \bar{P}}{\sigma_P} < 1.0
   $$
   即最优结果不应超出平均值 1 个标准差以上。若最优结果远超平均，说明存在"幸运峰值"。

5. **3D 优化景观应呈现"稳定"形态**  
   通过可视化检查：稳健策略的参数景观应呈现宽阔的高原（plateau），而非尖锐的孤立峰（spike）。

### 5.2 实现方案

```python
"""
Optimization Profile 分析器
"""
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from typing import Dict, List


class OptimizationProfileAnalyzer:
    """
    优化轮廓分析器 — 实现 Pardo 五大评估标准
    """
    
    def __init__(self, optimization_results: pd.DataFrame):
        """
        optimization_results: DataFrame，每行一个优化运行，
                             至少包含 'net_profit', 'sharpe_ratio', 'max_drawdown' 列
        """
        self.results = optimization_results
        self.profits = optimization_results['net_profit'].values
        
    def criterion_1_positive_ratio(self) -> Dict:
        """标准1：正收益优化运行比例"""
        n_positive = np.sum(self.profits > 0)
        n_total = len(self.profits)
        ratio = n_positive / n_total
        return {
            'name': '正收益比例',
            'value': ratio,
            'pass_threshold': 0.5,
            'passed': ratio > 0.5,
            'n_positive': n_positive,
            'n_total': n_total
        }
    
    def criterion_2_mean_profit(self) -> Dict:
        """标准2：所有优化运行的平均利润"""
        mean_p = np.mean(self.profits)
        return {
            'name': '平均净利润',
            'value': mean_p,
            'pass_threshold': 0,
            'passed': mean_p > 0
        }
    
    def criterion_3_uniformity(self) -> Dict:
        """标准3：利润分布均匀性"""
        # 排序后检查相邻符号变化
        sorted_profits = np.sort(self.profits)
        sign_changes = np.sum(sorted_profits[:-1] * sorted_profits[1:] < 0)
        uniformity = 1 - (sign_changes / (len(sorted_profits) - 1))
        return {
            'name': '分布均匀性',
            'value': uniformity,
            'pass_threshold': 0.7,
            'passed': uniformity > 0.7,
            'sign_changes': sign_changes
        }
    
    def criterion_4_outlier_check(self) -> Dict:
        """标准4：最优结果不应过度偏离平均"""
        max_p = np.max(self.profits)
        mean_p = np.mean(self.profits)
        std_p = np.std(self.profits)
        z_score = (max_p - mean_p) / std_p if std_p > 0 else 0
        return {
            'name': '最优值偏离度',
            'value': z_score,
            'pass_threshold': 1.0,
            'passed': z_score < 1.0,
            'max_profit': max_p,
            'mean_profit': mean_p
        }
    
    def criterion_5_visual_landscape(self, param1: str, param2: str):
        """标准5：3D 优化景观可视化"""
        fig = go.Figure(data=[
            go.Surface(
                x=self.results[param1].unique(),
                y=self.results[param2].unique(),
                z=self.results.pivot_table(
                    values='net_profit', 
                    index=param2, 
                    columns=param1
                ).values
            )
        ])
        fig.update_layout(
            title='Optimization Landscape',
            scene=dict(
                xaxis_title=param1,
                yaxis_title=param2,
                zaxis_title='Net Profit'
            )
        )
        return fig
    
    def full_analysis(self) -> Dict:
        """完整五大标准分析"""
        return {
            'criterion_1': self.criterion_1_positive_ratio(),
            'criterion_2': self.criterion_2_mean_profit(),
            'criterion_3': self.criterion_3_uniformity(),
            'criterion_4': self.criterion_4_outlier_check(),
            'overall_pass': all([
                self.criterion_1_positive_ratio()['passed'],
                self.criterion_2_mean_profit()['passed'],
                self.criterion_3_uniformity()['passed'],
                self.criterion_4_outlier_check()['passed']
            ])
        }
```

---

## 6. 多 OOS 样本外测试

### 6.1 数学原理

多 OOS 测试是将历史数据划分为多个独立时间段，每个时间段都作为样本外测试期。这与 Walk-Forward 的区别在于：多 OOS 使用**固定的全样本内参数**，而非滚动优化。

**划分策略**：

设总数据为 $D = \{d_1, d_2, ..., d_T\}$，划分为：
- 主 IS 期：$D_{IS} = \{d_1, ..., d_{t_{IS}}\}$（用于策略开发和参数优化）
- 多个 OOS 期：$D_{OOS}^{(k)} = \{d_{t_{IS} + \sum_{i<k} T_i + 1}, ..., d_{t_{IS} + \sum_{i \leq k} T_i}\}$

**IS/OOS 利润因子比**：

$$
\text{Ratio}_{IS/OOS} = \frac{\text{Profit Factor}_{IS}}{\text{Profit Factor}_{OOS}}
$$

StrategyQuant 的实证研究表明，当仅选择稳健性测试值前 1%（99th percentile）的策略时，OOS 结果显著优于随机策略。建议阈值：IS/OOS 利润因子比 > 0.9，且 IS 利润因子 > 1.3。

### 6.2 实现方案

```python
"""
多 OOS 样本外测试引擎
"""
import numpy as np
import pandas as pd
from typing import List, Dict, Tuple, Callable
from dataclasses import dataclass


@dataclass
class OOSPeriod:
    """单个 OOS 测试期"""
    name: str
    start_date: pd.Timestamp
    end_date: pd.Timestamp
    performance: Dict[str, float]
    is_oos_ratio: float


class MultiOOSEngine:
    """
    多 OOS 样本外测试引擎
    
    支持两种划分模式：
    1. 等分模式：将 IS 后的数据等分为 K 段
    2. 制度模式：按市场状态（牛市/熊市/震荡）划分 OOS 期
    """
    
    def __init__(self, backtest_fn: Callable):
        self.backtest_fn = backtest_fn
        
    def equal_split(self, 
                    data: pd.DataFrame,
                    is_ratio: float = 0.7,
                    n_oos_periods: int = 3,
                    params: Dict = None) -> List[OOSPeriod]:
        """等分模式"""
        n = len(data)
        is_end = int(n * is_ratio)
        
        is_data = data.iloc[:is_end]
        oos_data = data.iloc[is_end:]
        
        # IS 期回测（获取基准绩效）
        is_perf = self.backtest_fn(is_data, params)
        
        # 等分 OOS 期
        oos_len = len(oos_data) // n_oos_periods
        results = []
        
        for k in range(n_oos_periods):
            start = k * oos_len
            end = start + oos_len if k < n_oos_periods - 1 else len(oos_data)
            
            period_data = oos_data.iloc[start:end]
            oos_perf = self.backtest_fn(period_data, params)
            
            # 计算 IS/OOS 比
            pf_ratio = oos_perf['profit_factor'] / is_perf['profit_factor'] if is_perf['profit_factor'] > 0 else 0
            
            results.append(OOSPeriod(
                name=f'OOS_{k+1}',
                start_date=period_data.index[0],
                end_date=period_data.index[-1],
                performance=oos_perf,
                is_oos_ratio=pf_ratio
            ))
            
        return results
    
    def regime_based_split(self,
                           data: pd.DataFrame,
                           is_ratio: float = 0.6,
                           regime_detector: Callable = None,
                           params: Dict = None) -> List[OOSPeriod]:
        """
        制度模式 — 按市场状态划分 OOS 期
        
        regime_detector: 函数，接收价格序列，返回 'bull'/'bear'/'neutral' 标签
        """
        if regime_detector is None:
            regime_detector = self._default_regime_detector
            
        n = len(data)
        is_end = int(n * is_ratio)
        is_data = data.iloc[:is_end]
        oos_data = data.iloc[is_end:]
        
        is_perf = self.backtest_fn(is_data, params)
        
        # 检测市场制度
        regimes = regime_detector(oos_data)
        
        results = []
        for regime in ['bull', 'bear', 'neutral']:
            mask = regimes == regime
            if mask.sum() < 30:  # 数据量不足
                continue
                
            period_data = oos_data[mask]
            oos_perf = self.backtest_fn(period_data, params)
            
            pf_ratio = oos_perf['profit_factor'] / is_perf['profit_factor'] if is_perf['profit_factor'] > 0 else 0
            
            results.append(OOSPeriod(
                name=f'OOS_{regime}',
                start_date=period_data.index[0],
                end_date=period_data.index[-1],
                performance=oos_perf,
                is_oos_ratio=pf_ratio
            ))
            
        return results
    
    def _default_regime_detector(self, data: pd.DataFrame) -> pd.Series:
        """默认市场制度检测器 — 基于 200 日移动平均线"""
        close = data['close']
        ma200 = close.rolling(200).mean()
        
        # 计算近期趋势强度
        returns = close.pct_change(20)
        
        regimes = pd.Series('neutral', index=data.index)
        regimes[close > ma200 * 1.05] = 'bull'
        regimes[close < ma200 * 0.95] = 'bear'
        
        return regimes
    
    def evaluate_consistency(self, results: List[OOSPeriod]) -> Dict:
        """
        评估多 OOS 期的一致性
        
        稳健策略应在所有 OOS 期都保持可接受的绩效
        """
        ratios = [r.is_oos_ratio for r in results]
        sharpes = [r.performance['sharpe_ratio'] for r in results]
        
        return {
            'n_periods': len(results),
            'mean_is_oos_ratio': np.mean(ratios),
            'min_is_oos_ratio': np.min(ratios),
            'all_profitable': all(r.performance['net_profit'] > 0 for r in results),
            'all_sharpe_positive': all(s > 0 for s in sharpes),
            'sharpe_consistency': 1 - (np.std(sharpes) / np.mean(sharpes)) if np.mean(sharpes) > 0 else 0,
            'passed': np.mean(ratios) > 0.7 and all(s > 0 for s in sharpes)
        }
```

---

## 7. 过拟合检测指标体系

### 7.1 核心指标

#### 7.1.1 Deflated Sharpe Ratio (DSR) — 缩水夏普比率

**提出者**：Bailey & López de Prado (2014) [^5]

**问题背景**：传统夏普比率存在三大偏差：
1. 选择偏差（Selection Bias）：从多个策略中选出最优者
2. 非正态收益：金融收益具有偏度（Skewness）和峰度（Kurtosis）
3. 有限样本：回测期长度不足以支撑统计推断

**DSR 公式**：

$$
DSR = \hat{SR} \times \frac{\text{Adjustment Factor}}{\text{Multiple Testing Penalty}}
$$

其中：
- $\hat{SR}$：观测到的夏普比率
- Adjustment Factor：基于收益偏度（$S$）和峰度（$K$）的修正因子
- Multiple Testing Penalty：基于试验次数 $N_{trials}$ 和回测期长度 $T$ 的惩罚因子

具体计算：

$$
DSR = \hat{SR} \times \left[1 - \gamma_3 \hat{SR} + \frac{\gamma_4 - 1}{4} \hat{SR}^2\right] \times \sqrt{\frac{T}{V\left[\{r_t\}_{t=1,...,T}\right]}}
$$

其中 $\gamma_3 = S$（偏度），$\gamma_4 = K$（峰度）。

**Multiple Testing 校正**：

当进行 $N$ 次独立试验后选择最优策略时，预期的最大夏普比率为：

$$
E[\max(\hat{SR}_n)] \approx \sqrt{\frac{2 \ln N}{T}}
$$

DSR 通过将此预期值作为基准，对观测夏普进行"缩水"。

#### 7.1.2 Probability of Backtest Overfitting (PBO) — 回测过拟合概率

**提出者**：Bailey et al. (2016) [^6]

**核心思想**：通过组合对称交叉验证（CSCV, Combinatorial Symmetric Cross-Validation）来估计最优 IS 策略在 OOS 中表现不佳的概率。

**CSCV 算法**：

1. 将回测数据划分为 $S$ 个等长块（如 $S=16$）
2. 生成所有 $C(S, S/2)$ 种划分方式，将 $S/2$ 块作为 IS，$S/2$ 块作为 OOS
3. 对每个划分：
   - 在 IS 上优化所有策略，选出最优者 $\hat{\pi}_{IS}^*$
   - 记录 $\hat{\pi}_{IS}^*$ 在 OOS 上的排名 $R_{OOS}$
4. 若 $R_{OOS} > S/2$（即最优 IS 策略在 OOS 中排在中位数之后），则记为一次"过拟合事件"
5. PBO = 过拟合事件次数 / 总划分次数

**PBO 解释**：
- PBO = 0.5：完全随机，策略无真实优势
- PBO < 0.5：策略具有真实优势（概率上）
- PBO > 0.5：严重过拟合，策略表现完全由运气驱动

#### 7.1.3 概率夏普比率（Probabilistic Sharpe Ratio, PSR）

PSR 回答的问题是：给定观测夏普率 $\hat{SR}$ 和参考夏普率 $SR^*$，观测夏普率显著高于参考值的概率是多少？

$$
PSR(\hat{SR}, SR^*) = Z\left[\frac{(\hat{SR} - SR^*)\sqrt{T-1}}{\sqrt{1 - \gamma_3 \hat{SR} + \frac{\gamma_4 - 1}{4} \hat{SR}^2}}\right]
$$

其中 $Z[\cdot]$ 为标准正态 CDF。若 $PSR > 0.95$，则以 95% 置信度认为策略夏普率高于基准。

### 7.2 实现方案

```python
"""
过拟合检测指标体系

基于 Marcos López de Prado 的学术研究实现
"""
import numpy as np
import pandas as pd
from scipy import stats
from itertools import combinations
from typing import List, Dict, Tuple
from dataclasses import dataclass


@dataclass
class OverfittingMetrics:
    """过拟合检测指标集合"""
    # DSR 指标
    observed_sharpe: float
    deflated_sharpe: float
    dsr_significant: bool
    
    # PBO 指标
    pbo: float
    pbo_interpretation: str
    
    # PSR 指标
    psr: float
    psr_threshold: float
    
    # 多重检验校正
    bonferroni_pvalue: float
    bhy_pvalue: float
    
    # 综合评估
    overall_risk: str  # 'low', 'medium', 'high', 'critical'


class OverfittingDetector:
    """
    过拟合检测器
    
    实现：
    - Deflated Sharpe Ratio (Bailey & López de Prado, 2014)
    - Probability of Backtest Overfitting (Bailey et al., 2016)
    - Probabilistic Sharpe Ratio
    - Multiple Testing Corrections (Bonferroni, BHY)
    """
    
    def __init__(self, 
                 returns: np.ndarray,
                 n_trials: int = 100,
                 benchmark_sr: float = 0.0):
        self.returns = returns
        self.n_trials = n_trials
        self.benchmark_sr = benchmark_sr
        self.T = len(returns)
        
        # 收益统计量
        self.mean_return = np.mean(returns)
        self.std_return = np.std(returns, ddof=1)
        self.skewness = stats.skew(returns)
        self.kurtosis = stats.kurtosis(returns) + 3  # 转化为标准峰度（Fisher→Pearson）
        
    def compute_observed_sharpe(self) -> float:
        """计算观测夏普比率（年化）"""
        if self.std_return == 0:
            return 0.0
        return self.mean_return / self.std_return * np.sqrt(252)
    
    def compute_dsr(self, 
                    expected_max_sharpe: float = None) -> Tuple[float, bool]:
        """
        计算 Deflated Sharpe Ratio
        
        expected_max_sharpe: 多重检验下的预期最大夏普率
                            若 None，则基于 n_trials 估计
        """
        sr = self.compute_observed_sharpe()
        
        # 估计预期最大夏普率（多重检验惩罚）
        if expected_max_sharpe is None:
            expected_max_sharpe = np.sqrt(2 * np.log(self.n_trials) / self.T)
        
        # 偏度和峰度修正因子
        gamma3 = self.skewness
        gamma4 = self.kurtosis
        
        adjustment = 1 - gamma3 * sr + (gamma4 - 1) / 4 * sr**2
        
        # 确保 adjustment 为正
        adjustment = max(adjustment, 0.01)
        
        # DSR 计算
        dsr = sr * adjustment - expected_max_sharpe
        
        # 显著性检验：DSR > 0 且统计显著
        # 标准误计算
        se = np.sqrt((1 - gamma3 * sr + (gamma4 - 1) / 4 * sr**2) / (self.T - 1))
        z_score = dsr / se if se > 0 else 0
        significant = z_score > 1.645  # 95% 置信度（单侧）
        
        return dsr, significant
    
    def compute_psr(self, sr_star: float = 0.0) -> float:
        """
        计算 Probabilistic Sharpe Ratio
        
        sr_star: 参考夏普率（通常设为 0 或某个基准策略的夏普率）
        """
        sr = self.compute_observed_sharpe()
        
        gamma3 = self.skewness
        gamma4 = self.kurtosis
        
        # PSR 公式中的分母
        denominator = np.sqrt(1 - gamma3 * sr + (gamma4 - 1) / 4 * sr**2)
        
        if denominator == 0:
            return 0.5
            
        # 标准误
        sigma_sr = denominator / np.sqrt(self.T - 1)
        
        # Z 统计量
        z = (sr - sr_star) / sigma_sr
        
        # PSR = P(SR > sr_star) = 1 - CDF(z)
        psr = 1 - stats.norm.cdf(-z)  # 等价于 stats.norm.cdf(z)
        
        return psr
    
    def compute_pbo(self, 
                    strategy_returns_matrix: np.ndarray,
                    n_splits: int = 16) -> Tuple[float, str]:
        """
        计算 Probability of Backtest Overfitting
        
        strategy_returns_matrix: (T, N) 矩阵，
                               T=时间步数，N=策略数量（候选策略的日收益序列）
        """
        T, N = strategy_returns_matrix.shape
        
        # 将数据划分为 n_splits 块
        block_size = T // n_splits
        blocks = []
        for i in range(n_splits):
            start = i * block_size
            end = start + block_size if i < n_splits - 1 else T
            blocks.append(strategy_returns_matrix[start:end])
            
        n_blocks = len(blocks)
        half = n_blocks // 2
        
        # 生成所有 C(n_blocks, half) 划分
        overfit_count = 0
        total_splits = 0
        
        for is_indices in combinations(range(n_blocks), half):
            oos_indices = [i for i in range(n_blocks) if i not in is_indices]
            
            # 组合 IS 和 OOS 数据
            is_data = np.vstack([blocks[i] for i in is_indices])
            oos_data = np.vstack([blocks[i] for i in oos_indices])
            
            # 计算每个策略的 IS 和 OOS 夏普率
            is_sharpes = []
            oos_sharpes = []
            for j in range(N):
                is_returns = is_data[:, j]
                oos_returns = oos_data[:, j]
                
                is_sr = np.mean(is_returns) / np.std(is_returns) * np.sqrt(252) if np.std(is_returns) > 0 else 0
                oos_sr = np.mean(oos_returns) / np.std(oos_returns) * np.sqrt(252) if np.std(oos_returns) > 0 else 0
                
                is_sharpes.append(is_sr)
                oos_sharpes.append(oos_sr)
            
            # 找出 IS 最优策略在 OOS 中的排名
            best_is_idx = np.argmax(is_sharpes)
            oos_rank = stats.rankdata(oos_sharpes)[best_is_idx]
            
            # 若排名在中位数之后，记为一次过拟合事件
            if oos_rank > N / 2:
                overfit_count += 1
            
            total_splits += 1
            
        pbo = overfit_count / total_splits if total_splits > 0 else 0.5
        
        # 解释
        if pbo < 0.3:
            interpretation = "low overfitting risk"
        elif pbo < 0.5:
            interpretation = "moderate risk"
        elif pbo < 0.7:
            interpretation = "high risk"
        else:
            interpretation = "critical overfitting"
            
        return pbo, interpretation
    
    def multiple_testing_corrections(self, 
                                    p_values: List[float]) -> Dict:
        """
        多重检验校正
        
        实现 Bonferroni 和 Benjamini-Hochberg-Yekutieli (BHY) 方法
        """
        p_values = np.array(p_values)
        m = len(p_values)
        
        # Bonferroni 校正
        bonferroni = np.minimum(p_values * m, 1.0)
        
        # BHY 校正
        sorted_p = np.sort(p_values)[::-1]  # 从大到小排序
        c_m = np.sum(1.0 / np.arange(1, m + 1))  # 归一化常数
        
        bhy = np.zeros(m)
        for i in range(m):
            # 找到对应的原始索引
            idx = np.where(p_values == sorted_p[i])[0][0]
            bhy[idx] = min(sorted_p[i] * m * c_m / (i + 1), 1.0)
            
        return {
            'bonferroni': bonferroni,
            'bhy': bhy,
            'bonferroni_significant': np.any(bonferroni < 0.05),
            'bhy_significant': np.any(bhy < 0.05)
        }
    
    def full_diagnosis(self, 
                       strategy_returns_matrix: np.ndarray = None) -> OverfittingMetrics:
        """完整过拟合诊断"""
        dsr, dsr_sig = self.compute_dsr()
        psr = self.compute_psr()
        
        if strategy_returns_matrix is not None:
            pbo, pbo_interp = self.compute_pbo(strategy_returns_matrix)
        else:
            pbo, pbo_interp = 0.5, "insufficient data (need strategy matrix)"
            
        # 综合风险评估
        risk_score = 0
        if not dsr_sig:
            risk_score += 2
        if psr < 0.95:
            risk_score += 1
        if pbo > 0.5:
            risk_score += 2
            
        risk_map = {0: 'low', 1: 'low', 2: 'medium', 3: 'medium', 
                    4: 'high', 5: 'critical'}
        overall_risk = risk_map.get(risk_score, 'high')
        
        return OverfittingMetrics(
            observed_sharpe=self.compute_observed_sharpe(),
            deflated_sharpe=dsr,
            dsr_significant=dsr_sig,
            pbo=pbo,
            pbo_interpretation=pbo_interp,
            psr=psr,
            psr_threshold=0.95,
            bonferroni_pvalue=0.0,  # 需外部提供 p 值
            bhy_pvalue=0.0,
            overall_risk=overall_risk
        )
```

### 7.3 过拟合检测决策矩阵

| 指标 | 安全阈值 | 警告阈值 | 危险阈值 | 检测能力 |
|------|---------|---------|---------|---------|
| DSR | > 0，且显著 | 接近 0 | < 0 | 多重检验+非正态修正 |
| PBO | < 0.3 | 0.3-0.5 | > 0.5 | 样本外一致性 |
| PSR | > 0.99 | 0.95-0.99 | < 0.95 | 夏普率显著性 |
| IS/OOS 利润比 | > 0.9 | 0.7-0.9 | < 0.7 | 样本外衰减 |
| 参数稳定性 | > 0.8 | 0.5-0.8 | < 0.5 | 参数漂移 |
| 盈利参数比例 | > 60% | 40-60% | < 40% | 参数空间优势 |

---

## 8. 开源实现方案调研

### 8.1 回测框架对比

| 框架 | 架构 | 速度 | 稳健性测试支持 | 适用场景 |
|------|------|------|-------------|---------|
| **VectorBT** | 向量化+Numba | 极快（1000+策略/秒） | 需自建，但底层支持多维数组 | 大规模参数扫描、Monte Carlo |
| **Backtrader** | 事件驱动 | 中等 | 内置 Analyzer 体系，社区 WFO 实现 | 策略开发、WFO、复杂订单逻辑 |
| **bt** | 模块化 | 中等 | 组合回测强，稳健性测试弱 | 投资组合权重优化 |
| **Zipline** | 事件驱动 | 较慢 | 内置 PyFolio 集成，但已不再维护 | 学术研究（Quantopian 遗产） |
| **QSTrader** | 事件驱动 | 中等 | 模块化，需自建 | 机构级需求、定制风控 |
| **PyAlgoTrade** | 事件驱动 | 中等 | 基础 | 简单策略、学习用途 |

### 8.2 关键库选型

```python
# 推荐技术栈（requirements.txt 核心依赖）

# 高性能回测引擎
vectorbt>=0.28.5          # 向量化回测，Numba/Rust 加速
backtrader>=1.9.78        # 事件驱动回测，WFO 支持

# 数值计算与加速
numpy>=1.24.0
pandas>=2.0.0
numba>=0.57.0             # JIT 编译，CPU 加速
cupy-cuda12x>=13.0.0      # GPU 加速（CUDA 12.x）

# 分布式计算
dask>=2024.1.0            # 分布式任务调度
distributed>=2024.1.0     # Dask 分布式集群

# 统计与过拟合检测
scipy>=1.11.0
scikit-learn>=1.3.0       # TimeSeriesSplit, 聚类
statsmodels>=0.14.0       # 统计检验

# 可视化
plotly>=5.18.0            # 3D 优化景观、交互图表
matplotlib>=3.8.0
seaborn>=0.13.0

# 数据
yfinance>=0.2.28          # 数据获取（示例）
pyarrow>=14.0.0           # 高性能数据格式

# 可选：直接复用 MLFinLab 的过拟合检测模块
# mlfinlab>=1.0.0         # 包含 CPCV, PBO, DSR 实现
```

### 8.3 开源 WFO 实现参考

Backtrader 社区提供了成熟的 Walk-Forward 实现 [^2]：

```python
# Backtrader WFO 核心代码模式（基于社区实现）
from sklearn.model_selection import TimeSeriesSplit

def wfa(cerebro, strategy, opt_param, split, datafeeds, 
        analyzer_max, var_maximize, opt_p_vals, minimize=False):
    """
    Backtrader Walk-Forward Analysis 实现
    
    关键步骤：
    1. TimeSeriesSplit 生成滚动窗口
    2. 在 train 期执行 cerebro.optstrategy() 参数优化
    3. 在 test 期使用最优参数执行 cerebro.addstrategy()
    4. 计算 WFER = test_perf / train_perf
    """
    walk_forward_results = []
    
    for train, test in split:
        trainer, tester = deepcopy(cerebro), deepcopy(cerebro)
        
        # TRAINING: 参数优化
        trainer.optstrategy(strategy, **{opt_param: opt_p_vals})
        for s, df in datafeeds.items():
            data = bt.feeds.PandasData(dataname=df.iloc[train], name=s)
            trainer.adddata(data)
        res = trainer.run()
        
        # 提取最优参数
        res_df = DataFrame({
            getattr(r[0].params, opt_param): 
            dict(getattr(r[0].analyzers, analyzer_max).get_analysis())
            for r in res
        }).T.loc[:, var_maximize].sort_values(ascending=minimize)
        opt_res, opt_val = res_df.index[0], res_df[0]
        
        # TESTING: OOS 验证
        tester.addstrategy(strategy, **{opt_param: opt_res})
        for s, df in datafeeds.items():
            data = bt.feeds.PandasData(dataname=df.iloc[test], name=s)
            tester.adddata(data)
        res = tester.run()
        test_val = getattr(res[0].analyzers, analyzer_max).get_analysis()[var_maximize]
        
        # WFER
        wfer = test_val / opt_val if opt_val != 0 else np.nan
        
        walk_forward_results.append({
            'opt_param': opt_res,
            'train_perf': opt_val,
            'test_perf': test_val,
            'WFER': wfer
        })
    
    return walk_forward_results
```

---

## 9. 自动化集成方案

### 9.1 流水线架构

```
┌─────────────────────────────────────────────────────────────┐
│                  策略生成流水线（Strategy Generation）              │
├─────────────────────────────────────────────────────────────┤
│  Step 1: 策略生成（遗传算法/随机生成/模板扩展）                    │
│     ↓                                                       │
│  Step 2: 初筛过滤（交易次数、基础盈亏比、最低夏普率）              │
│     ↓                                                       │
│  ┌─────────────────────────────────────────────────────┐   │
│  │           稳健性测试层（Robustness Testing）           │   │
│  │  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐  │   │
│  │  │ Monte   │  │ 多市场  │  │ Walk-   │  │ 多 OOS  │  │   │
│  │  │ Carlo   │  │ 测试    │  │ Forward │  │ 测试    │  │   │
│  │  │ 模拟    │  │         │  │ 分析    │  │         │  │   │
│  │  └─────────┘  └─────────┘  └─────────┘  └─────────┘  │   │
│  │     ↓              ↓            ↓            ↓          │   │
│  │  ┌─────────────────────────────────────────────────┐  │   │
│  │  │  过拟合检测层（DSR / PBO / PSR / 参数稳定性）     │  │   │
│  │  └─────────────────────────────────────────────────┘  │   │
│  │     ↓                                                 │   │
│  │  ┌─────────────────────────────────────────────────┐  │   │
│  │  │  SPP + 优化轮廓分析（参数空间遍历+分布评估）      │  │   │
│  │  └─────────────────────────────────────────────────┘  │   │
│  └─────────────────────────────────────────────────────┘   │
│     ↓                                                       │
│  Step 3: 高级过滤（稳健性测试通过阈值 + 过拟合指标阈值）        │
│     ↓                                                       │
│  Step 4: 保存入库（通过全部测试的策略进入候选池）               │
│     ↓                                                       │
│  Step 5: 实盘模拟（Paper Trading 验证）                       │
└─────────────────────────────────────────────────────────────┘
```

### 9.2 配置驱动的稳健性测试引擎

```python
"""
配置驱动的稳健性测试流水线
"""
from dataclasses import dataclass, field
from typing import List, Dict, Optional
import yaml


@dataclass
class RobustnessConfig:
    """稳健性测试配置"""
    
    # Monte Carlo 配置
    mc_n_simulations: int = 1000
    mc_methods: List[str] = field(default_factory=lambda: [
        'shuffle_trades', 'skip_trades', 'randomize_params', 'randomize_data'
    ])
    mc_skip_prob: float = 0.1
    mc_param_perturb_pct: float = 0.10
    mc_data_perturb_pct: float = 0.20
    
    # Walk-Forward 配置
    wfo_is_lengths: List[int] = field(default_factory=lambda: [500, 1000, 1500])
    wfo_oos_lengths: List[int] = field(default_factory=lambda: [100, 200, 300])
    wfo_steps: List[int] = field(default_factory=lambda: [50, 100])
    wfo_metric: str = 'sharpe_ratio'
    wfo_min_wfer: float = 0.5
    
    # SPP 配置
    spp_use_lhs: bool = True
    spp_n_samples: int = 1000
    spp_min_profitable_pct: float = 60.0
    
    # 优化轮廓配置
    optprofile_min_positive_ratio: float = 0.5
    optprofile_min_uniformity: float = 0.7
    optprofile_max_zscore: float = 1.0
    
    # 多 OOS 配置
    multi_oos_n_periods: int = 3
    multi_oos_min_ratio: float = 0.7
    
    # 过拟合检测配置
    overfitting_n_trials: int = 100
    overfitting_dsr_min: float = 0.0
    overfitting_pbo_max: float = 0.5
    overfitting_psr_min: float = 0.95
    
    # 并行配置
    parallel_backend: str = 'dask'  # 'dask', 'multiprocessing', 'gpu'
    n_workers: int = 8


class RobustnessPipeline:
    """
    配置驱动的稳健性测试流水线
    
    将 StrategyQuant 的所有稳健性测试功能整合为可配置、可扩展的流水线
    """
    
    def __init__(self, config: RobustnessConfig):
        self.config = config
        self.mc_engine = MonteCarloEngine(n_simulations=config.mc_n_simulations)
        self.wfo_engine = WalkForwardEngine(strategy_fn=None, optimize_fn=None, 
                                           evaluate_fn=None, param_grid={})
        self.spp_engine = SPPEngine(backtest_fn=None, param_grid={})
        self.oos_engine = MultiOOSEngine(backtest_fn=None)
        self.detector = OverfittingDetector(returns=np.array([]), 
                                           n_trials=config.overfitting_n_trials)
        
    def run(self, strategy, data, param_grid) -> Dict:
        """
        执行完整稳健性测试流水线
        
        返回：包含所有测试结果的详细报告，以及综合 PASS/FAIL 判定
        """
        report = {}
        
        # 1. Monte Carlo 测试
        report['monte_carlo'] = self._run_monte_carlo(strategy, data)
        
        # 2. Walk-Forward 分析
        report['walk_forward'] = self._run_wfo(data, param_grid)
        
        # 3. SPP 系统参数排列
        report['spp'] = self._run_spp(data, param_grid)
        
        # 4. 优化轮廓分析
        report['opt_profile'] = self._run_opt_profile(data, param_grid)
        
        # 5. 多 OOS 测试
        report['multi_oos'] = self._run_multi_oos(strategy, data)
        
        # 6. 过拟合检测
        report['overfitting'] = self._run_overfitting_detection(strategy, data)
        
        # 7. 综合判定
        report['overall'] = self._evaluate_overall(report)
        
        return report
    
    def _run_monte_carlo(self, strategy, data):
        """Monte Carlo 测试"""
        results = {}
        for method in self.config.mc_methods:
            sim_results = self.mc_engine.run_simulation(method, data)
            robustness = self.mc_engine.evaluate_robustness(sim_results, 
                                                            original=None)
            results[method] = robustness
        return results
    
    def _run_wfo(self, data, param_grid):
        """Walk-Forward 分析（含矩阵）"""
        matrix = self.wfo_engine.wfo_matrix(
            data,
            is_lengths=self.config.wfo_is_lengths,
            oos_lengths=self.config.wfo_oos_lengths,
            steps=self.config.wfo_steps,
            metric=self.config.wfo_metric
        )
        # 筛选满足 min_wfer 的配置
        valid = matrix[matrix['mean_wfer'] > self.config.wfo_min_wfer]
        return {
            'matrix': matrix,
            'valid_configs': valid,
            'best_config': valid.iloc[0] if len(valid) > 0 else None
        }
    
    def _run_spp(self, data, param_grid):
        """SPP 系统参数排列"""
        if self.config.spp_use_lhs:
            result = self.spp_engine.approximate_with_lhs(
                data, n_samples=self.config.spp_n_samples
            )
        else:
            result = self.spp_engine.run(data)
        
        passed = result.profitable_pct > self.config.spp_min_profitable_pct
        return {'result': result, 'passed': passed}
    
    def _run_opt_profile(self, data, param_grid):
        """优化轮廓分析"""
        # 先执行优化获取所有运行结果
        optimization_results = self._run_full_optimization(data, param_grid)
        analyzer = OptimizationProfileAnalyzer(optimization_results)
        analysis = analyzer.full_analysis()
        return analysis
    
    def _run_multi_oos(self, strategy, data):
        """多 OOS 测试"""
        results = self.oos_engine.equal_split(data, 
                                              n_oos_periods=self.config.multi_oos_n_periods)
        consistency = self.oos_engine.evaluate_consistency(results)
        return {'periods': results, 'consistency': consistency}
    
    def _run_overfitting_detection(self, strategy, data):
        """过拟合检测"""
        returns = self._get_strategy_returns(strategy, data)
        self.detector.returns = returns
        
        diagnosis = self.detector.full_diagnosis()
        return {
            'dsr': diagnosis.deflated_sharpe,
            'dsr_significant': diagnosis.dsr_significant,
            'psr': diagnosis.psr,
            'pbo': diagnosis.pbo,
            'overall_risk': diagnosis.overall_risk,
            'passed': diagnosis.overall_risk in ['low', 'medium']
        }
    
    def _evaluate_overall(self, report: Dict) -> Dict:
        """
        综合判定
        
        策略必须通过所有关键测试才能被判定为稳健
        """
        checks = {
            'mc_passed': all(
                r['profitable_pct'] > 80 for r in report['monte_carlo'].values()
            ),
            'wfo_passed': report['walk_forward']['best_config'] is not None,
            'spp_passed': report['spp']['passed'],
            'opt_profile_passed': report['opt_profile']['overall_pass'],
            'oos_passed': report['multi_oos']['consistency']['passed'],
            'overfitting_passed': report['overfitting']['passed']
        }
        
        return {
            'checks': checks,
            'overall_passed': all(checks.values()),
            'failed_checks': [k for k, v in checks.items() if not v]
        }
```

### 9.3 与现有流水线（Hermass）的集成建议

基于用户上下文中的 [[Hermass]] 多周期共振与收缩突破假设验证流水线，稳健性测试层应插入到策略生成与实盘模拟之间：

```
现有流水线（5 模块）：
  数据获取 → 特征工程 → 信号生成 → 回测验证 → 报告输出

增强后流水线（7 模块）：
  数据获取 → 特征工程 → 信号生成 → 回测验证 → 
  【稳健性测试层】 → 过拟合过滤 → 实盘模拟 → 报告输出

稳健性测试层内部：
  ├─ 快速通道（Monte Carlo + 多 OOS）→ 用于大批量策略初筛
  └─ 深度通道（WFO + SPP + 优化轮廓 + 过拟合检测）→ 用于精选策略终审
```

**集成要点**：
- 快速通道计算量小（O(N·T)），适合对遗传算法每代生成的数千策略进行快速过滤
- 深度通道计算量大（O(W·P·T) + O(∏nᵢ)），仅对通过快速通道的 Top 策略执行
- 使用 Dask 将两类测试分布式调度到不同 worker 集群，避免资源竞争

---

## 10. GPU/并行计算加速

### 10.1 加速策略分析

| 计算任务 | 计算特征 | 推荐加速方案 | 预期加速比 |
|---------|---------|------------|----------|
| 参数网格回测 |  embarrassingly parallel | Dask multiprocessing | 8-16x（8 核） |
| Monte Carlo 模拟 | 随机数生成+独立模拟 | Numba CUDA / CuPy | 50-100x（Tesla V100） |
| 技术指标计算 | 向量化滑动窗口 | Numba JIT + 并行 | 10-50x |
| WFO 矩阵 | 多窗口配置独立 | Dask distributed | 线性扩展 |
| SPP 参数空间 | 全组合独立 | GPU kernel（Numba CUDA） | 100-1000x |
| 优化景观可视化 | 3D 表面渲染 | 预处理并行+Plotly 前端 | 10x |

### 10.2 Numba CUDA 实现 Monte Carlo 加速

```python
"""
Numba CUDA 加速 Monte Carlo 模拟

关键优化点：
1. 将历史数据预加载到 GPU device memory
2. 每个 CUDA thread 负责一个独立模拟
3. 使用 shared memory 缓存频繁访问的数据
"""
from numba import cuda
import numpy as np
import math


@cuda.jit
def mc_skip_trades_kernel(trades, n_trades, skip_prob, seed, 
                           n_simulations, results):
    """
    CUDA kernel: 并行执行 Monte Carlo 跳过交易模拟
    
    trades: 原始交易盈亏数组 (device)
    n_trades: 交易数量
    skip_prob: 跳过概率
    seed: 随机种子基值
    n_simulations: 总模拟次数
    results: 输出数组 (n_simulations,)
    """
    idx = cuda.grid(1)
    if idx >= n_simulations:
        return
    
    # 每个线程的独立随机状态（简单线性同余生成器）
    state = seed + idx * 12345
    
    total_profit = 0.0
    for i in range(n_trades):
        # 生成伪随机数
        state = (state * 1103515245 + 12345) & 0x7fffffff
        rand_val = state / 0x7fffffff
        
        # 以概率 skip_prob 跳过交易
        if rand_val > skip_prob:
            total_profit += trades[i]
    
    results[idx] = total_profit


def run_mc_gpu(trades: np.ndarray, 
               skip_prob: float = 0.1,
               n_simulations: int = 10000) -> np.ndarray:
    """GPU 加速 Monte Carlo 模拟入口"""
    
    # 分配 device memory
    d_trades = cuda.to_device(trades)
    d_results = cuda.device_array(n_simulations, dtype=np.float32)
    
    # 配置 CUDA grid
    threads_per_block = 256
    blocks_per_grid = (n_simulations + threads_per_block - 1) // threads_per_block
    
    # 启动 kernel
    mc_skip_trades_kernel[blocks_per_grid, threads_per_block](
        d_trades, len(trades), skip_prob, 
        np.random.randint(0, 2**31), n_simulations, d_results
    )
    
    # 复制结果回 host
    return d_results.copy_to_host()


# 性能对比（示例）
# CPU（单线程）: 10,000 模拟 × 1,000 交易 ≈ 5 秒
# GPU（Tesla V100）: 10,000 模拟 × 1,000 交易 ≈ 0.05 秒（100x 加速）
```

### 10.3 Dask 分布式 WFO 矩阵

```python
"""
Dask 分布式 Walk-Forward 矩阵计算
"""
import dask
from dask.distributed import Client


def distributed_wfo_matrix(data, wfo_engine, config):
    """
    使用 Dask 分布式计算 WFO 矩阵
    
    每个窗口配置作为独立 task，在 cluster 中并行执行
    """
    client = Client(n_workers=config.n_workers)
    
    tasks = []
    for is_len in config.wfo_is_lengths:
        for oos_len in config.wfo_oos_lengths:
            for step in config.wfo_steps:
                # 将每个配置包装为 Dask delayed task
                task = dask.delayed(wfo_engine.standard_wfo)(
                    data, 
                    WFOWindow(is_len, oos_len, step),
                    config.wfo_metric
                )
                tasks.append((is_len, oos_len, step, task))
    
    # 并行执行所有 task
    results = dask.compute(*[t[3] for t in tasks])
    
    # 聚合结果
    matrix_results = []
    for (is_len, oos_len, step, _), wfo_result in zip(tasks, results):
        wfers = [r.wfer for r in wfo_result]
        matrix_results.append({
            'is_length': is_len,
            'oos_length': oos_len,
            'step': step,
            'mean_wfer': np.mean(wfers),
            'std_wfer': np.std(wfers)
        })
    
    client.close()
    return pd.DataFrame(matrix_results)
```

### 10.4 性能预估

假设测试环境：8 核 CPU + NVIDIA RTX 4090 / Tesla V100

| 测试模块 | 单策略 CPU 耗时 | GPU/并行 耗时 | 1000 策略总耗时 |
|---------|--------------|-------------|--------------|
| Monte Carlo (1000 sim) | 30s | 0.5s (GPU) | 8 min |
| Walk-Forward 矩阵 (9 configs) | 180s | 25s (Dask 8核) | 7 min |
| SPP (1000 LHS samples) | 300s | 5s (GPU) | 8 min |
| 优化轮廓 | 300s | 40s (Dask 8核) | 11 min |
| 多 OOS (3 periods) | 15s | 2s | 0.5 min |
| 过拟合检测 (DSR/PBO) | 10s | 1s (GPU) | 0.5 min |
| **合计** | **~14 min** | **~1.5 min** | **~35 min** |

---

## 11. 代码量级与模块划分

### 11.1 模块结构建议

```
hermass_robustness/                 # 稳健性测试模块（总代码量 ~8,000-12,000 行）
├── __init__.py
├── core/                           # 核心抽象层 (~1,500 行)
│   ├── base.py                    # 基类：RobustnessTest, SimulationResult
│   ├── config.py                  # 配置管理：RobustnessConfig
│   ├── metrics.py                 # 绩效指标计算（Sharpe, Drawdown, PF 等）
│   └── exceptions.py            # 自定义异常
├── monte_carlo/                   # Monte Carlo 模块 (~1,800 行)
│   ├── engine.py                  # MonteCarloEngine（主引擎）
│   ├── perturbations.py           # 各类扰动实现（交易/参数/数据/滑点）
│   ├── statistics.py              # 稳健性统计评估
│   └── cuda_kernels.py            # Numba CUDA 加速 kernel
├── walk_forward/                  # Walk-Forward 模块 (~2,000 行)
│   ├── engine.py                  # WalkForwardEngine
│   ├── matrix.py                  # WFO 矩阵计算与聚类
│   ├── window.py                  # 窗口管理（滑动/扩展/固定）
│   ├── regime_detector.py         # 市场制度检测器
│   └── visualization.py           # WFO 结果可视化
├── spp/                           # 系统参数排列模块 (~1,200 行)
│   ├── engine.py                  # SPPEngine
│   ├── sampling.py                # LHS / 随机采样 / 自适应采样
│   ├── statistics.py              # SPP 统计量计算
│   └── optimizer.py               # 参数空间优化器（减少计算量）
├── opt_profile/                   # 优化轮廓模块 (~800 行)
│   ├── analyzer.py                # OptimizationProfileAnalyzer
│   ├── criteria.py                # Pardo 五大标准实现
│   └── landscape.py               # 3D 景观可视化
├── multi_oos/                     # 多 OOS 模块 (~600 行)
│   ├── engine.py                  # MultiOOSEngine
│   ├── splitters.py               # 数据分割策略（等分/制度/波动率）
│   └── consistency.py             # 一致性评估
├── overfitting/                   # 过拟合检测模块 (~2,000 行)
│   ├── dsr.py                     # Deflated Sharpe Ratio
│   ├── pbo.py                     # Probability of Backtest Overfitting + CSCV
│   ├── psr.py                     # Probabilistic Sharpe Ratio
│   ├── multiple_testing.py        # Bonferroni, BHY, Holm 校正
│   ├── cpcv.py                    # Combinatorial Purged Cross-Validation
│   └── detector.py                # OverfittingDetector（统一接口）
├── integration/                   # 集成层 (~1,500 行)
│   ├── pipeline.py                # RobustnessPipeline（主流水线）
│   ├── adapters.py                # Backtrader/VectorBT 适配器
│   ├── filters.py                 # 策略过滤规则
│   └── report_generator.py        # HTML/Markdown 报告生成
├── parallel/                      # 并行计算层 (~1,000 行)
│   ├── dask_backend.py            # Dask 分布式后端
│   ├── multiprocessing_backend.py # 多进程后端
│   ├── cuda_backend.py            # Numba CUDA 后端
│   └── scheduler.py               # 任务调度器
└── tests/                         # 测试 (~2,000 行)
    ├── test_monte_carlo.py
    ├── test_walk_forward.py
    ├── test_spp.py
    ├── test_overfitting.py
    └── test_integration.py
```

### 11.2 代码量级估算

| 模块 | 行数范围 | 复杂度 | 开发周期（估算） |
|------|---------|--------|----------------|
| 核心抽象层 | 1,500 | 中 | 1-2 周 |
| Monte Carlo | 1,800 | 高 | 2-3 周 |
| Walk-Forward | 2,000 | 高 | 2-3 周 |
| SPP | 1,200 | 中 | 1-2 周 |
| 优化轮廓 | 800 | 低 | 1 周 |
| 多 OOS | 600 | 低 | 3-5 天 |
| 过拟合检测 | 2,000 | 高 | 2-3 周 |
| 集成层 | 1,500 | 中 | 1-2 周 |
| 并行计算 | 1,000 | 高 | 2 周 |
| 测试 | 2,000 | - | 持续 |
| **总计** | **~14,000** | - | **~12-16 周** |

### 11.3 优先级建议

**Phase 1（MVP，4-6 周）**：
- Monte Carlo（交易序列操作 + 参数扰动）
- 多 OOS 测试（等分模式）
- DSR + PSR 过拟合检测
- 基础流水线集成

**Phase 2（增强，4-6 周）**：
- Walk-Forward 分析（标准 + 矩阵）
- SPP（含 LHS 近似）
- 优化轮廓分析
- PBO + CSCV 实现

**Phase 3（优化，2-4 周）**：
- Numba CUDA 加速
- Dask 分布式支持
- 高级可视化
- 性能调优

---

## 12. 参考文献

[^1]: VectorBT Documentation. "VectorBT: Backtesting library on steroids." https://vectorbt.dev/

[^2]: PyQuantNews. "Mastering Trading with Backtrader: Effective Backtesting." https://www.pyquantnews.com/free-python-resources/mastering-trading-with-backtrader-effective-backtesting

[^3]: Quant67. "Walk-forward 与 Purged CV：时间序列正确切分." https://quant67.com/post/quant/21-walkforward-cv/21-walkforward-cv.html

[^4]: CSDN. "高频回测性能瓶颈突破：Python多进程+向量化加速实战技巧揭秘." https://blog.csdn.net/Instrustar/article/details/153403686

[^5]: Bailey, D.H., & López de Prado, M. (2014). "The Deflated Sharpe Ratio: Correcting for Selection Bias, Backtest Overfitting, and Non-Normality." Journal of Portfolio Management.

[^6]: Bailey, D.H., et al. (2016). "The Probability of Backtest Overfitting." Journal of Computational Finance.

[^7]: StrategyQuant. "Types of robustness tests in SQX." https://strategyquant.com/doc/strategyquant/types-of-robustness-tests-in-sqx/

[^8]: StrategyQuant. "Optimization Profile and System Parameter Permutation in StrategyQuant." https://strategyquant.com/doc/strategyquant/optimization-profile-system-parameter-permutation-strategyquant/

[^9]: Walton, D. "Know your System! – Turning Data Mining from Bias to Benefit." Wagner Award 2012. https://bettersystemtrader.com/system-parameter-permutation-a-better-alternative/

[^10]: Pardo, R. "Pardo Strategy Robustness Evaluation." https://www.pardo.space/consulting/pardo-strategy-robustness-evaluation

[^11]: BacktestBase. "Monte Carlo Stress Testing for TradingView Backtests." https://www.backtestbase.com/education/monte-carlo-stress-testing

[^12]: StrategyQuant. "New Robustness Tests on the StrategyQuant Codebase: 5 Monte Carlo Methods." https://strategyquant.com/blog/new-robustness-tests-on-the-strategyquant-codebase/

[^13]: Witzany, J. (2017). "A Bayesian Approach to Backtest Overfitting." http://quantitative.cz/wp-content/uploads/2018/09/a-bayesian-approach-to-backtest-overfitting-jiri-witzany-2017.pdf

[^14]: Backtesting in Financial Machine Learning Comprehensive Assessment. https://gauss.vaniercollege.qc.ca/~iti/proj/2021/DS_backtesting.pdf

[^15]: Numba CUDA Documentation. "CuPy and Numba on the GPU." https://carpentries-incubator.github.io/gpu-speedups/

[^16]: gQuant. "GPU-accelerated examples for quantitative analysts." https://ichi.pro/pt/gquant-exemplos-acelerados-por-gpu-para-tarefas-de-analistas-quantitativos-153304097884866

[^17]: CSDN. "量化CTA策略开发的进阶之路：高级统计学方法的深度剖析与Python实践." https://blog.csdn.net/zhangyunchou2015/article/details/147378616

[^18]: Guorn. "如何检验股票量化策略的有效性和过拟合程度." https://guorn.com/forum/post/p.18036.323861242009255

[^19]: StrategyQuant. "Analysis of selected robustness tests in StrategyQuant X on Forex." https://strategyquant.com/blog/analysis-of-selected-robustness-tests-in-strategyquant-x-on-forex/

[^20]: Smart Trading Software. "Retesting process - StrategyQuant X." https://smarttradingsoftware.com/en/back-test/ai-strategy-builder-retest-process/

---

> 报告完成。本调研覆盖 StrategyQuant 六大稳健性测试功能的数学原理、开源实现路径、过拟合检测指标体系、GPU/并行加速方案以及模块化的代码架构建议。所有技术方案均基于当前主流开源生态（VectorBT/Backtrader/Numba/Dask），可直接用于 Hermass 等自动化策略生成平台的稳健性测试层建设。
