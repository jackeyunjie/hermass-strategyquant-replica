import React, { useEffect, useRef, useState } from 'react';
import { createChart, AreaSeries, ColorType } from 'lightweight-charts';
import type { IChartApi, Time } from 'lightweight-charts';

interface EquityChartProps {
  equityCurve: Array<{ date: string; equity: number }>;
}

export default function EquityChart({ equityCurve }: EquityChartProps) {
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ReturnType<IChartApi['addSeries']> | null>(null);
  const [tooltip, setTooltip] = useState<{ date: string; equity: number } | null>(null);

  useEffect(() => {
    if (!chartContainerRef.current) return;

    const chart = createChart(chartContainerRef.current, {
      layout: {
        background: { type: ColorType.Solid, color: '#ffffff' },
        textColor: '#333',
      },
      grid: {
        vertLines: { color: '#f0f0f0' },
        horzLines: { color: '#f0f0f0' },
      },
      rightPriceScale: { borderColor: '#e0e0e0' },
      timeScale: {
        borderColor: '#e0e0e0',
        timeVisible: true,
      },
      crosshair: { mode: 1 },
      autoSize: true,
    });

    chartRef.current = chart;

    const series = chart.addSeries(AreaSeries, {
      lineColor: '#1890ff',
      topColor: 'rgba(24, 144, 255, 0.3)',
      bottomColor: 'rgba(24, 144, 255, 0.01)',
      lineWidth: 2,
    });

    seriesRef.current = series;

    if (equityCurve && equityCurve.length > 0) {
      const data = equityCurve.map((item) => ({
        time: item.date as Time,
        value: item.equity,
      }));
      series.setData(data);
      chart.timeScale().fitContent();
    }

    chart.subscribeCrosshairMove((param) => {
      if (param.time && param.point && param.point.x >= 0 && param.point.y >= 0) {
        const data = param.seriesData.get(series) as { value?: number } | undefined;
        if (data && 'value' in data) {
          setTooltip({ date: String(param.time), equity: data.value || 0 });
        }
      } else {
        setTooltip(null);
      }
    });

    const handleResize = () => {
      if (chartContainerRef.current && chartRef.current) {
        const { width, height } = chartContainerRef.current.getBoundingClientRect();
        chartRef.current.applyOptions({ width, height });
      }
    };

    window.addEventListener('resize', handleResize);
    handleResize();

    return () => {
      window.removeEventListener('resize', handleResize);
      chart.remove();
      chartRef.current = null;
      seriesRef.current = null;
    };
  }, [equityCurve]);

  return (
    <div style={{ position: 'relative', width: '100%', height: 300 }}>
      <div ref={chartContainerRef} style={{ width: '100%', height: '100%' }} />
      {tooltip && (
        <div
          style={{
            position: 'absolute',
            top: 8,
            left: 8,
            background: 'rgba(255, 255, 255, 0.9)',
            padding: '4px 8px',
            borderRadius: 4,
            fontSize: 12,
            border: '1px solid #e0e0e0',
            pointerEvents: 'none',
            zIndex: 10,
          }}
        >
          <div>{tooltip.date}</div>
          <div style={{ fontWeight: 'bold', color: '#1890ff' }}>
            ¥{tooltip.equity.toLocaleString('zh-CN', { minimumFractionDigits: 2 })}
          </div>
        </div>
      )}
    </div>
  );
}
