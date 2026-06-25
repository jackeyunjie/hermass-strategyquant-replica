import { useState, useCallback, useEffect, useRef } from 'react';
import { message } from 'antd';
import { api } from '../services/api';
import type { BacktestResult, BacktestConfig, TaskStatus } from '../types';

export function useBacktest() {
  const [isRunning, setIsRunning] = useState(false);
  const [progress, setProgress] = useState(0);
  const [result, setResult] = useState<BacktestResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [taskId, setTaskId] = useState<string | null>(null);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const submitBacktest = useCallback(async (config: BacktestConfig): Promise<boolean> => {
    setIsRunning(true);
    setProgress(0);
    setError(null);
    setResult(null);

    try {
      const response: TaskStatus = await api.runBacktest(config.strategy_id, config);
      setTaskId(response.task_id);
      message.success('回测任务已提交');
      return true;
    } catch (err: unknown) {
      const error = err as { response?: { data?: { detail?: string } } };
      const errMsg = error?.response?.data?.detail || '回测提交失败';
      setError(errMsg);
      message.error(errMsg);
      setIsRunning(false);
      return false;
    }
  }, []);

  const pollTaskStatus = useCallback(async (id: string) => {
    try {
      // For mock/demo purposes, we simulate progress
      const mockProgress = Math.min(100, progress + randomInt(5, 25));
      setProgress(mockProgress);

      if (mockProgress >= 100) {
        // Simulate completion
        const mockResult: BacktestResult = await import('../utils/mockData').then((m) => m.mockBacktestResult());
        setResult(mockResult);
        setIsRunning(false);
        setTaskId(null);
        message.success('回测完成');
        return true;
      }
      return false;
    } catch {
      setError('轮询任务状态失败');
      setIsRunning(false);
      return true;
    }
  }, [progress]);

  // Polling effect
  useEffect(() => {
    if (taskId && isRunning) {
      intervalRef.current = setInterval(() => {
        pollTaskStatus(taskId).then((done) => {
          if (done && intervalRef.current) {
            clearInterval(intervalRef.current);
            intervalRef.current = null;
          }
        });
      }, 2000);
    }

    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
      }
    };
  }, [taskId, isRunning, pollTaskStatus]);

  const cancelBacktest = useCallback(() => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
    setIsRunning(false);
    setTaskId(null);
    setProgress(0);
  }, []);

  const fetchBacktestHistory = useCallback(async (): Promise<BacktestResult[]> => {
    try {
      return await api.getBacktestResults();
    } catch (err: unknown) {
      const error = err as { response?: { data?: { detail?: string } } };
      message.error(error?.response?.data?.detail || '获取回测历史失败');
      return [];
    }
  }, []);

  const fetchBacktestResult = useCallback(async (id: string): Promise<BacktestResult | null> => {
    try {
      return await api.getBacktestResult(id);
    } catch (err: unknown) {
      const error = err as { response?: { data?: { detail?: string } } };
      message.error(error?.response?.data?.detail || '获取回测结果失败');
      return null;
    }
  }, []);

  return {
    isRunning,
    progress,
    result,
    error,
    submitBacktest,
    cancelBacktest,
    fetchBacktestHistory,
    fetchBacktestResult,
  };
}

function randomInt(min: number, max: number): number {
  return Math.floor(Math.random() * (max - min + 1)) + min;
}
