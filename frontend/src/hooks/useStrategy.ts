import { useState, useCallback } from 'react';
import { message } from 'antd';
import { api } from '../services/api';
import type { Strategy, StrategyIR } from '../types';

export function useStrategy() {
  const [strategies, setStrategies] = useState<Strategy[]>([]);
  const [currentStrategy, setCurrentStrategy] = useState<StrategyIR | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  const fetchStrategies = useCallback(async () => {
    setIsLoading(true);
    try {
      const data = await api.getStrategies();
      setStrategies(data || []);
      return data || [];
    } catch (err: unknown) {
      const error = err as { response?: { data?: { detail?: string } } };
      message.error(error?.response?.data?.detail || '获取策略列表失败');
      return [];
    } finally {
      setIsLoading(false);
    }
  }, []);

  const fetchStrategy = useCallback(async (id: string): Promise<StrategyIR | null> => {
    setIsLoading(true);
    try {
      const data = await api.getStrategy(id);
      setCurrentStrategy(data?.ir_json || data || null);
      return data?.ir_json || data || null;
    } catch (err: unknown) {
      const error = err as { response?: { data?: { detail?: string } } };
      message.error(error?.response?.data?.detail || '获取策略详情失败');
      return null;
    } finally {
      setIsLoading(false);
    }
  }, []);

  const createStrategy = useCallback(async (ir: StrategyIR): Promise<Strategy | null> => {
    setIsLoading(true);
    try {
      const data = await api.createStrategy(ir);
      message.success('策略创建成功');
      await fetchStrategies();
      return data;
    } catch (err: unknown) {
      const error = err as { response?: { data?: { detail?: string } } };
      message.error(error?.response?.data?.detail || '创建策略失败');
      return null;
    } finally {
      setIsLoading(false);
    }
  }, [fetchStrategies]);

  const saveStrategy = useCallback(async (ir: StrategyIR): Promise<boolean> => {
    setIsLoading(true);
    try {
      if (ir.id && ir.id !== 'new') {
        await api.updateStrategy(ir.id, ir);
      } else {
        await api.createStrategy(ir);
      }
      setCurrentStrategy(ir);
      message.success('策略保存成功');
      await fetchStrategies();
      return true;
    } catch (err: unknown) {
      const error = err as { response?: { data?: { detail?: string } } };
      message.error(error?.response?.data?.detail || '保存策略失败');
      return false;
    } finally {
      setIsLoading(false);
    }
  }, [fetchStrategies]);

  const deleteStrategy = useCallback(async (id: string): Promise<boolean> => {
    try {
      await api.deleteStrategy(id);
      message.success('策略删除成功');
      await fetchStrategies();
      return true;
    } catch (err: unknown) {
      const error = err as { response?: { data?: { detail?: string } } };
      message.error(error?.response?.data?.detail || '删除策略失败');
      return false;
    }
  }, [fetchStrategies]);

  return {
    strategies,
    currentStrategy,
    isLoading,
    fetchStrategies,
    fetchStrategy,
    createStrategy,
    saveStrategy,
    deleteStrategy,
    setCurrentStrategy,
  };
}
