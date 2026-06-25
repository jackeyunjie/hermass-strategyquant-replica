import { type Node, type Edge } from 'reactflow';

// ─────────────────── Auth ───────────────────
export interface User {
  id: string;
  email: string;
  is_active: boolean;
  created_at: string;
}

export interface LoginCredentials {
  email: string;
  password: string;
}

export interface RegisterCredentials {
  email: string;
  password: string;
  confirmPassword: string;
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
}

// ─────────────────── Strategy Nodes ───────────────────
export interface StrategyNode {
  id: string;
  type: string;
  position: { x: number; y: number };
  data: Record<string, unknown>;
}

export interface StrategyEdge {
  id: string;
  source: string;
  sourceHandle: string;
  target: string;
  targetHandle: string;
}

export interface NodePort {
  id: string;
  label: string;
  type: 'number' | 'boolean' | 'series' | 'trade' | 'any';
  required: boolean;
  direction: 'input' | 'output';
}

export interface NodeDefinition {
  type: string;
  label: string;
  category: string;
  icon: string;
  color: string;
  inputs: NodePort[];
  outputs: NodePort[];
  defaultData: Record<string, unknown>;
}

export type NodeType =
  | 'priceDataNode'
  | 'indicatorNode'
  | 'comparatorNode'
  | 'logicalNode'
  | 'mathNode'
  | 'entryRuleNode'
  | 'exitRuleNode'
  | 'stopLossNode'
  | 'takeProfitNode'
  | 'positionSizeNode'
  | 'filterNode'
  | 'orderNode'
  | 'variableNode'
  | 'conditionalNode'
  | 'signalNode'
  | 'subchartNode'
  | 'customFunctionNode';

// ─────────────────── Strategy IR ───────────────────
export interface StrategyIR {
  id: string;
  name: string;
  description: string;
  version: number;
  metadata: {
    author: string;
    created_at: string;
    updated_at: string;
  };
  settings: {
    main_symbol: string;
    main_timeframe: string;
    market_type: string;
  };
  nodes: StrategyNode[];
  edges: StrategyEdge[];
  variables: Array<{ name: string; type: string; expression: string }>;
}

export interface Strategy {
  id: string;
  name: string;
  description: string;
  status: 'draft' | 'active' | 'archived';
  created_at: string;
  updated_at: string;
  ir_json: StrategyIR;
}

export interface StrategyTemplate {
  id: string;
  name: string;
  description: string;
  category: string;
  ir_json: StrategyIR;
  is_builtin: boolean;
  created_at: string;
}

// ─────────────────── Backtest ───────────────────
export interface BacktestConfig {
  strategy_id: string;
  symbol: string;
  start_date: string;
  end_date: string;
  timeframe: '1d' | '1h' | '30m' | '15m' | '5m' | '1m';
  initial_capital: number;
  commission: number;
  slippage: number;
}

export interface BacktestResult {
  run_id: string;
  strategy_id: string;
  strategy_name: string;
  period: {
    start_date: string;
    end_date: string;
    total_bars: number;
  };
  equity_curve: Array<{ date: string; equity: number; drawdown: number }>;
  trades: Trade[];
  metrics: PerformanceMetrics;
}

export interface Trade {
  trade_id: string;
  entry_date: string;
  exit_date: string;
  direction: 'long' | 'short';
  entry_price: number;
  exit_price: number;
  pnl: number;
  pnl_pct: number;
  size: number;
  commission: number;
  reason: string;
}

export interface PerformanceMetrics {
  net_profit: number;
  total_return_pct: number;
  sharpe_ratio: number;
  sortino_ratio: number;
  max_drawdown_pct: number;
  max_drawdown_duration: number;
  win_rate: number;
  profit_factor: number;
  avg_win: number;
  avg_loss: number;
  total_trades: number;
  return_on_drawdown: number;
  calmar_ratio: number;
  expectancy: number;
}

// ─────────────────── Results AI ───────────────────
export interface ResultsAIInsight {
  title: string;
  severity: 'high' | 'medium' | 'low';
  evidence: string;
  recommendation: string;
}

export interface ResultsAIReport {
  summary: string;
  regime: string;
  quality_score: number;
  risk_score: number;
  opportunity_score: number;
  insights: ResultsAIInsight[];
  suggested_actions: string[];
  prompt_context: Record<string, unknown>;
}

// ─────────────────── Fuzzy Logic ───────────────────
export interface FuzzyStrategyResponse {
  strategy_ir: Record<string, unknown>;
  frontend_graph: {
    nodes: StrategyNode[];
    edges: StrategyEdge[];
    fuzzy_spec: Record<string, unknown>;
  };
  fuzzy_spec: Record<string, unknown>;
}

// ─────────────────── Indicator Marketplace ───────────────────
export interface MarketplaceIndicator {
  id: string;
  name: string;
  display_name: string;
  description: string;
  category: string;
  formula: string;
  author: string;
  rating: number;
  downloads: number;
  tags: string[];
  status: string;
}

// ─────────────────── Portfolio ───────────────────
export interface Portfolio {
  id: string;
  name: string;
  description: string;
  strategies: Array<{
    strategy_id: string;
    weight: number;
  }>;
  created_at: string;
  updated_at: string;
}

export interface PortfolioResult {
  portfolio_id: string;
  equity_curve: Array<{ date: string; equity: number }>;
  metrics: PerformanceMetrics;
  correlation_matrix: number[][];
  strategy_labels: string[];
}

// ─────────────────── Data ───────────────────
export interface DataSource {
  id: string;
  symbol: string;
  timeframe: string;
  start_date: string;
  end_date: string;
  record_count: number;
  status: 'downloaded' | 'pending' | 'error';
  updated_at: string;
}

export interface DataDownloadRequest {
  symbols: string[];
  start_date: string;
  end_date: string;
  timeframe: string;
}

export interface OHLCVData {
  timestamp: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

// ─────────────────── Settings ───────────────────
export interface Settings {
  general: {
    language: 'zh-CN' | 'en-US';
    theme: 'light' | 'dark';
  };
  account: {
    email: string;
  };
  dataSource: {
    tushare_token: string;
  };
  engine: {
    population_size: number;
    generations: number;
    crossover_rate: number;
    mutation_rate: number;
  };
}

// ─────────────────── Task ───────────────────
export interface TaskStatus {
  task_id: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  progress: number;
  message: string;
  result?: unknown;
  error?: string;
  created_at: string;
  updated_at: string;
}

// ─────────────────── Monte Carlo / Walk Forward ───────────────────
export interface MonteCarloResult {
  n_simulations: number;
  profitable_pct: number;
  profit_median: number;
  profit_pct5: number;
  profit_pct95: number;
  profit_std: number;
  sharpe_median: number;
  sharpe_std: number;
  worst_drawdown: number;
  pass: boolean;
}

export interface WalkForwardResult {
  windows: Array<{
    window_idx: number;
    is_start: string;
    is_end: string;
    oos_start: string;
    oos_end: string;
    wfer: number;
    is_sharpe: number;
    oos_sharpe: number;
  }>;
  avg_wfer: number;
  pass: boolean;
}

// ─────────────────── API ───────────────────
export interface ApiResponse<T> {
  success: boolean;
  data: T;
  message?: string;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

// ─────────────────── ReactFlow Extended ───────────────────
export interface CustomNodeData extends Record<string, unknown> {
  label: string;
  nodeType: NodeType;
  inputs: NodePort[];
  outputs: NodePort[];
  parameters?: Record<string, unknown>;
}

export type CustomNode = Node<CustomNodeData>;
export type CustomEdge = Edge;

// ─────────────────── Menu Items ───────────────────
export interface MenuItem {
  key: string;
  label: string;
  icon: string;
  path: string;
  children?: MenuItem[];
}

// ─────────────────── Notification ───────────────────
export interface Notification {
  id: string;
  title: string;
  message: string;
  type: 'info' | 'success' | 'warning' | 'error';
  read: boolean;
  created_at: string;
}
