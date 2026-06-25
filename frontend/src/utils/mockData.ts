import { v4 as uuidv4 } from 'uuid';
import type {
  Strategy,
  BacktestResult,
  Trade,
  PerformanceMetrics,
  StrategyIR,
  DataSource,
  TaskStatus,
  User,
} from '../types';

export function generateUUID(): string {
  return uuidv4();
}

export function deepClone<T>(obj: T): T {
  return JSON.parse(JSON.stringify(obj));
}

export function debounce<T extends (...args: unknown[]) => void>(
  fn: T,
  delay: number
): (...args: Parameters<T>) => void {
  let timer: ReturnType<typeof setTimeout> | null = null;
  return (...args: Parameters<T>) => {
    if (timer) clearTimeout(timer);
    timer = setTimeout(() => fn(...args), delay);
  };
}

export function throttle<T extends (...args: unknown[]) => void>(
  fn: T,
  limit: number
): (...args: Parameters<T>) => void {
  let inThrottle = false;
  return (...args: Parameters<T>) => {
    if (!inThrottle) {
      fn(...args);
      inThrottle = true;
      setTimeout(() => { inThrottle = false; }, limit);
    }
  };
}

export function clamp(value: number, min: number, max: number): number {
  return Math.min(Math.max(value, min), max);
}

export function randomInt(min: number, max: number): number {
  return Math.floor(Math.random() * (max - min + 1)) + min;
}

export function randomFloat(min: number, max: number, digits = 2): number {
  const val = Math.random() * (max - min) + min;
  return Number(val.toFixed(digits));
}

export function randomPick<T>(arr: T[]): T {
  return arr[Math.floor(Math.random() * arr.length)];
}

export function randomDate(start: Date, end: Date): string {
  const time = start.getTime() + Math.random() * (end.getTime() - start.getTime());
  return new Date(time).toISOString().split('T')[0];
}

export function mockUser(): User {
  return {
    id: generateUUID(),
    email: 'user@hermass.com',
    is_active: true,
    created_at: '2024-01-15T08:00:00Z',
  };
}

export function mockStrategies(count = 10): Strategy[] {
  const statuses: Array<'draft' | 'active' | 'archived'> = ['draft', 'active', 'archived'];
  const names = [
    '双均线趋势跟踪', 'RSI超卖反弹', 'MACD金叉策略', '布林带突破',
    '动量反转策略', '成交量加权突破', '多周期共振', '收缩突破策略',
    'ATR波动率过滤', '价值回归策略', '小市值因子', '低波动策略',
    'KDJ超买超卖', 'OBV能量潮', 'DMI趋势强度',
  ];

  return Array.from({ length: count }, (_, i) => {
    const status = randomPick(statuses);
    return {
      id: generateUUID(),
      name: `${randomPick(names)} ${i + 1}`,
      description: '基于技术指标的量化交易策略',
      status,
      created_at: randomDate(new Date('2024-01-01'), new Date('2024-12-31')),
      updated_at: randomDate(new Date('2024-06-01'), new Date('2024-12-31')),
      ir_json: mockStrategyIR(),
    };
  });
}

export function mockStrategyIR(): StrategyIR {
  return {
    id: generateUUID(),
    name: '未命名策略',
    description: '',
    version: 1,
    metadata: {
      author: 'user',
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    },
    settings: {
      main_symbol: '000001.SZ',
      main_timeframe: '1d',
      market_type: 'stock',
    },
    nodes: [],
    edges: [],
    variables: [],
  };
}

export function mockEquityCurve(startDate: string, days = 252): Array<{ date: string; equity: number }> {
  const result: Array<{ date: string; equity: number }> = [];
  let equity = 1000000;
  const start = new Date(startDate);

  for (let i = 0; i < days; i++) {
    const date = new Date(start);
    date.setDate(date.getDate() + i);
    const dayOfWeek = date.getDay();
    if (dayOfWeek === 0 || dayOfWeek === 6) continue;

    const dailyReturn = randomFloat(-0.02, 0.025, 4);
    equity *= (1 + dailyReturn);
    result.push({
      date: date.toISOString().split('T')[0],
      equity: Number(equity.toFixed(2)),
    });
  }
  return result;
}

export function mockTrades(count = 30): Trade[] {
  const directions: Array<'long' | 'short'> = ['long', 'short'];
  const reasons = ['止损', '止盈', '信号反转', '时间到期', '手动平仓'];

  return Array.from({ length: count }, (_, i) => {
    const direction = randomPick(directions);
    const entryPrice = randomFloat(10, 200, 2);
    const pnlPct = randomFloat(-0.08, 0.15, 4);
    const exitPrice = entryPrice * (1 + pnlPct * (direction === 'long' ? 1 : -1));
    const size = randomInt(100, 1000) * 100;
    const pnl = (exitPrice - entryPrice) * size * (direction === 'long' ? 1 : -1);
    const commission = size * entryPrice * 0.0003 + size * exitPrice * 0.0003;

    const entryDate = randomDate(new Date('2024-01-01'), new Date('2024-11-01'));
    const exitDateObj = new Date(entryDate);
    exitDateObj.setDate(exitDateObj.getDate() + randomInt(1, 30));

    return {
      trade_id: `T${String(i + 1).padStart(4, '0')}`,
      entry_date: entryDate,
      exit_date: exitDateObj.toISOString().split('T')[0],
      direction,
      entry_price: entryPrice,
      exit_price: Number(exitPrice.toFixed(2)),
      pnl: Number(pnl.toFixed(2)),
      pnl_pct: Number((pnlPct * 100).toFixed(2)),
      size,
      commission: Number(commission.toFixed(2)),
      reason: randomPick(reasons),
    };
  });
}

export function mockPerformanceMetrics(): PerformanceMetrics {
  const trades = mockTrades(50);
  const wins = trades.filter((t) => t.pnl > 0);
  const losses = trades.filter((t) => t.pnl <= 0);
  const netProfit = trades.reduce((sum, t) => sum + t.pnl - t.commission, 0);
  const totalReturn = (netProfit / 1000000) * 100;
  const winRate = wins.length / trades.length;
  const avgWin = wins.length > 0 ? wins.reduce((s, t) => s + t.pnl, 0) / wins.length : 0;
  const avgLoss = losses.length > 0 ? Math.abs(losses.reduce((s, t) => s + t.pnl, 0) / losses.length) : 1;
  const profitFactor = avgWin * wins.length / (avgLoss * losses.length || 1);

  return {
    net_profit: Number(netProfit.toFixed(2)),
    total_return_pct: Number(totalReturn.toFixed(2)),
    sharpe_ratio: Number(randomFloat(0.5, 2.5, 3).toFixed(3)),
    sortino_ratio: Number(randomFloat(0.8, 3.0, 3).toFixed(3)),
    max_drawdown_pct: Number(randomFloat(-0.25, -0.05, 2).toFixed(2)),
    max_drawdown_duration: randomInt(5, 60),
    win_rate: Number((winRate * 100).toFixed(2)),
    profit_factor: Number(profitFactor.toFixed(3)),
    avg_win: Number(avgWin.toFixed(2)),
    avg_loss: Number(avgLoss.toFixed(2)),
    total_trades: trades.length,
    return_on_drawdown: Number(randomFloat(1.0, 5.0, 2).toFixed(2)),
    calmar_ratio: Number(randomFloat(0.3, 2.0, 3).toFixed(3)),
    expectancy: Number(((winRate * avgWin - (1 - winRate) * avgLoss) / avgLoss).toFixed(3)),
  };
}

export function mockBacktestResult(): BacktestResult {
  const equityCurve = mockEquityCurve('2024-01-01', 252);
  const trades = mockTrades(40);
  return {
    run_id: generateUUID(),
    strategy_id: generateUUID(),
    strategy_name: '双均线趋势跟踪',
    period: {
      start_date: '2024-01-01',
      end_date: '2024-12-31',
      total_bars: 252,
    },
    equity_curve: equityCurve.map((e) => ({ ...e, drawdown: 0 })),
    trades,
    metrics: mockPerformanceMetrics(),
  };
}

export function mockDataSources(count = 8): DataSource[] {
  const timeframes = ['1d', '1h', '30m', '15m'];
  const symbols = ['000001.SZ', '000002.SZ', '600519.SH', '600036.SH', '000858.SZ', '002415.SZ', '300750.SZ', '601318.SH'];

  return Array.from({ length: count }, (_, i) => {
    const symbol = symbols[i % symbols.length];
    const timeframe = randomPick(timeframes);
    const start = randomDate(new Date('2020-01-01'), new Date('2022-01-01'));
    const end = randomDate(new Date('2023-01-01'), new Date('2024-12-31'));
    const days = Math.floor((new Date(end).getTime() - new Date(start).getTime()) / (1000 * 60 * 60 * 24));
    const recordCount = timeframe === '1d' ? days : days * (timeframe === '1h' ? 4 : 8);

    return {
      id: generateUUID(),
      symbol,
      timeframe,
      start_date: start,
      end_date: end,
      record_count: recordCount,
      status: 'downloaded',
      updated_at: randomDate(new Date('2024-06-01'), new Date('2024-12-31')),
    };
  });
}

export function mockTaskStatus(): TaskStatus {
  const statuses: Array<'pending' | 'running' | 'completed' | 'failed'> = ['pending', 'running', 'completed', 'failed'];
  const status = randomPick(statuses);
  return {
    task_id: generateUUID(),
    status,
    progress: status === 'completed' ? 100 : status === 'failed' ? randomInt(0, 80) : randomInt(10, 90),
    message: '回测任务执行中...',
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  };
}

export function mockTaskList(count = 5): TaskStatus[] {
  return Array.from({ length: count }, () => mockTaskStatus());
}

export function mockCorrelationMatrix(size = 5): number[][] {
  const matrix: number[][] = [];
  for (let i = 0; i < size; i++) {
    matrix[i] = [];
    for (let j = 0; j < size; j++) {
      if (i === j) matrix[i][j] = 1;
      else if (j < i) matrix[i][j] = matrix[j][i];
      else matrix[i][j] = randomFloat(-0.5, 0.9, 2);
    }
  }
  return matrix;
}
