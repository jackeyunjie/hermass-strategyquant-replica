import { create } from 'zustand';
import type { StrategyIR, BacktestResult, TaskStatus, User } from '../types';

interface AppState {
  // Auth
  user: User | null;
  token: string | null;
  isAuthenticated: boolean;
  setAuth: (token: string, user: User) => void;
  clearAuth: () => void;

  // Current Strategy
  currentStrategy: StrategyIR | null;
  setCurrentStrategy: (strategy: StrategyIR | null) => void;
  updateStrategy: (partial: Partial<StrategyIR>) => void;

  // Backtest Results
  backtestResults: BacktestResult[];
  setBacktestResults: (results: BacktestResult[]) => void;
  addBacktestResult: (result: BacktestResult) => void;
  selectedBacktest: BacktestResult | null;
  setSelectedBacktest: (result: BacktestResult | null) => void;

  // Tasks
  tasks: TaskStatus[];
  setTasks: (tasks: TaskStatus[]) => void;
  updateTask: (taskId: string, update: Partial<TaskStatus>) => void;

  // UI State
  activePage: string;
  setActivePage: (page: string) => void;
  sidebarCollapsed: boolean;
  setSidebarCollapsed: (collapsed: boolean) => void;
}

export const useAppStore = create<AppState>((set) => ({
  user: null,
  token: null,
  isAuthenticated: false,
  setAuth: (token, user) => set({ token, user, isAuthenticated: true }),
  clearAuth: () => set({ token: null, user: null, isAuthenticated: false }),

  currentStrategy: null,
  setCurrentStrategy: (strategy) => set({ currentStrategy: strategy }),
  updateStrategy: (partial) =>
    set((state) => ({
      currentStrategy: state.currentStrategy
        ? { ...state.currentStrategy, ...partial }
        : null,
    })),

  backtestResults: [],
  setBacktestResults: (results) => set({ backtestResults: results }),
  addBacktestResult: (result) =>
    set((state) => ({
      backtestResults: [...state.backtestResults, result],
    })),
  selectedBacktest: null,
  setSelectedBacktest: (result) => set({ selectedBacktest: result }),

  tasks: [],
  setTasks: (tasks) => set({ tasks }),
  updateTask: (taskId, update) =>
    set((state) => ({
      tasks: state.tasks.map((t) =>
        t.task_id === taskId ? { ...t, ...update } : t
      ),
    })),

  activePage: 'strategy-builder',
  setActivePage: (page) => set({ activePage: page }),
  sidebarCollapsed: false,
  setSidebarCollapsed: (collapsed) => set({ sidebarCollapsed: collapsed }),
}));
