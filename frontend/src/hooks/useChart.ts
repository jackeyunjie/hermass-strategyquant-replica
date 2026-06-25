import { useEffect, useRef, useCallback } from 'react';
import { createChart, LineSeries } from 'lightweight-charts';
import type { IChartApi, LineData, Time } from 'lightweight-charts';

interface ChartConfig {
  container: HTMLElement;
  data?: Array<{ time: string; value: number }>;
  color?: string;
  autoSize?: boolean;
}

export function useChart() {
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ReturnType<IChartApi['addSeries']> | null>(null);
  const containerRef = useRef<HTMLElement | null>(null);

  const initChart = useCallback((config: ChartConfig) => {
    if (!config.container) return null;

    if (chartRef.current) {
      chartRef.current.remove();
      chartRef.current = null;
      seriesRef.current = null;
    }

    containerRef.current = config.container;

    const chart = createChart(config.container, {
      layout: {
        background: { color: '#ffffff' },
        textColor: '#333333',
      },
      grid: {
        vertLines: { color: '#f0f0f0' },
        horzLines: { color: '#f0f0f0' },
      },
      crosshair: {
        mode: 1,
      },
      rightPriceScale: {
        borderColor: '#e0e0e0',
      },
      timeScale: {
        borderColor: '#e0e0e0',
        timeVisible: true,
      },
      autoSize: config.autoSize !== false,
    });

    chartRef.current = chart;

    const series = chart.addSeries(LineSeries, {
      color: config.color || '#1890ff',
      lineWidth: 2,
    });

    seriesRef.current = series;

    if (config.data && config.data.length > 0) {
      const lineData: LineData[] = config.data.map((d) => ({
        time: d.time as Time,
        value: d.value,
      }));
      series.setData(lineData);
      chart.timeScale().fitContent();
    }

    return chart;
  }, []);

  const updateData = useCallback((data: Array<{ time: string; value: number }>) => {
    if (!seriesRef.current || !chartRef.current) return;

    const lineData: LineData[] = data.map((d) => ({
      time: d.time as Time,
      value: d.value,
    }));
    seriesRef.current.setData(lineData);
    chartRef.current.timeScale().fitContent();
  }, []);

  const resize = useCallback(() => {
    if (!chartRef.current || !containerRef.current) return;
    const { width, height } = containerRef.current.getBoundingClientRect();
    chartRef.current.applyOptions({ width, height });
  }, []);

  const destroy = useCallback(() => {
    if (chartRef.current) {
      chartRef.current.remove();
      chartRef.current = null;
      seriesRef.current = null;
      containerRef.current = null;
    }
  }, []);

  useEffect(() => {
    const handleResize = () => resize();
    window.addEventListener('resize', handleResize);
    return () => {
      window.removeEventListener('resize', handleResize);
      destroy();
    };
  }, [resize, destroy]);

  return {
    chartRef,
    seriesRef,
    initChart,
    updateData,
    resize,
    destroy,
  };
}
