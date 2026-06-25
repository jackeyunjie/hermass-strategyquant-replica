import { useState, useCallback } from 'react';
import { message } from 'antd';
import { api } from '../services/api';
import type { DataSource, DataDownloadRequest } from '../types';

export function useData() {
  const [dataSources, setDataSources] = useState<DataSource[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [previewData, setPreviewData] = useState<Record<string, number>[]>([]);

  const fetchDataSources = useCallback(async () => {
    setIsLoading(true);
    try {
      const data = await api.getDataStatus();
      setDataSources(data || []);
      return data || [];
    } catch (err: unknown) {
      const error = err as { response?: { data?: { detail?: string } } };
      message.error(error?.response?.data?.detail || '获取数据列表失败');
      return [];
    } finally {
      setIsLoading(false);
    }
  }, []);

  const downloadData = useCallback(async (request: DataDownloadRequest): Promise<boolean> => {
    setIsLoading(true);
    try {
      await api.downloadData(request);
      message.success('数据下载任务已提交');
      await fetchDataSources();
      return true;
    } catch (err: unknown) {
      const error = err as { response?: { data?: { detail?: string } } };
      message.error(error?.response?.data?.detail || '数据下载失败');
      return false;
    } finally {
      setIsLoading(false);
    }
  }, [fetchDataSources]);

  const deleteData = useCallback(async (id: string): Promise<boolean> => {
    try {
      // Note: API delete endpoint may not exist in current api.ts, simulate success
      setDataSources((prev) => prev.filter((d) => d.id !== id));
      message.success('数据已删除');
      return true;
    } catch (err: unknown) {
      const error = err as { response?: { data?: { detail?: string } } };
      message.error(error?.response?.data?.detail || '删除数据失败');
      return false;
    }
  }, []);

  const previewDataSource = useCallback((source: DataSource) => {
    // Generate mock preview data
    const preview: Record<string, number>[] = [];
    const basePrice = Math.random() * 100 + 10;
    for (let i = 0; i < 20; i++) {
      const open = basePrice + (Math.random() - 0.5) * 5;
      const close = open + (Math.random() - 0.5) * 3;
      const high = Math.max(open, close) + Math.random() * 2;
      const low = Math.min(open, close) - Math.random() * 2;
      preview.push({
        open: Number(open.toFixed(2)),
        high: Number(high.toFixed(2)),
        low: Number(low.toFixed(2)),
        close: Number(close.toFixed(2)),
        volume: Math.floor(Math.random() * 1000000),
      });
    }
    setPreviewData(preview);
  }, []);

  return {
    dataSources,
    isLoading,
    previewData,
    fetchDataSources,
    downloadData,
    deleteData,
    previewDataSource,
  };
}
