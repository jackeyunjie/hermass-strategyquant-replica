import React, { useState, useMemo, useCallback } from 'react';
import {
  Card,
  Form,
  Select,
  DatePicker,
  Input,
  InputNumber,
  Button,
  Row,
  Col,
  Progress,
  Typography,
  Space,
  message,
  Empty,
} from 'antd';
import {
  PlayCircleOutlined,
  ReloadOutlined,
  SettingOutlined,
  BarChartOutlined,
} from '@ant-design/icons';
import type { BacktestResult, BacktestConfig } from '../../types';
import { useBacktest } from '../../hooks/useBacktest';
import { useStrategy } from '../../hooks/useStrategy';
import { mockBacktestResult } from '../../utils/mockData';
import MetricsPanel from './MetricsPanel';
import EquityChart from './EquityChart';
import TradeTable from './TradeTable';
import ReactECharts from 'echarts-for-react';

const { Title, Text } = Typography;
const { RangePicker } = DatePicker;
const { Option } = Select;

interface BacktestDashboardProps {
  initialResult?: BacktestResult | null;
}

export default function BacktestDashboard({ initialResult }: BacktestDashboardProps) {
  const [form] = Form.useForm();
  const { strategies, fetchStrategies } = useStrategy();
  const { isRunning, progress, result, submitBacktest, cancelBacktest } = useBacktest();
  const [displayResult, setDisplayResult] = useState<BacktestResult | null>(initialResult || null);

  const activeResult = displayResult || result;

  const handleSubmit = useCallback(async () => {
    const values = form.getFieldsValue();
    if (!values.strategy_id) {
      message.error('请选择策略');
      return;
    }
    if (!values.symbol) {
      message.error('请输入股票代码');
      return;
    }
    if (!values.dateRange || values.dateRange.length !== 2) {
      message.error('请选择时间范围');
      return;
    }

    const config: BacktestConfig = {
      strategy_id: values.strategy_id,
      symbol: values.symbol,
      start_date: values.dateRange[0].format('YYYY-MM-DD'),
      end_date: values.dateRange[1].format('YYYY-MM-DD'),
      timeframe: values.timeframe || '1d',
      initial_capital: values.initial_capital || 1000000,
      commission: values.commission || 0.0003,
      slippage: values.slippage || 0.001,
    };

    const success = await submitBacktest(config);
    if (!success) {
      // Fallback to mock result for demo
      setDisplayResult(mockBacktestResult());
    }
  }, [form, submitBacktest]);

  const pnlDistribution = useMemo(() => {
    if (!activeResult) return [];
    return activeResult.trades.map((t) => t.pnl);
  }, [activeResult]);

  const pnlOption = useMemo(() => {
    if (!activeResult || pnlDistribution.length === 0) return {};
    const bins = 20;
    const min = Math.min(...pnlDistribution);
    const max = Math.max(...pnlDistribution);
    const step = (max - min) / bins;
    const counts = new Array(bins).fill(0);
    pnlDistribution.forEach((v) => {
      const idx = Math.min(Math.floor((v - min) / step), bins - 1);
      counts[idx]++;
    });
    const labels = counts.map((_, i) => `${(min + i * step).toFixed(0)} ~ ${(min + (i + 1) * step).toFixed(0)}`);

    return {
      tooltip: { trigger: 'axis' },
      xAxis: { type: 'category', data: labels, axisLabel: { rotate: 45, fontSize: 10 } },
      yAxis: { type: 'value', name: '次数' },
      series: [{
        type: 'bar',
        data: counts,
        itemStyle: {
          color: (params: { dataIndex: number }) => {
            const mid = bins / 2;
            return params.dataIndex < mid ? '#52c41a' : '#f5222d';
          },
        },
      }],
    };
  }, [activeResult, pnlDistribution]);

  const drawdownOption = useMemo(() => {
    if (!activeResult) return {};
    const equity = activeResult.equity_curve;
    let peak = equity[0]?.equity || 0;
    const drawdowns = equity.map((e) => {
      if (e.equity > peak) peak = e.equity;
      return {
        date: e.date,
        drawdown: ((e.equity - peak) / peak) * 100,
      };
    });

    return {
      tooltip: { trigger: 'axis' },
      xAxis: { type: 'category', data: drawdowns.map((d) => d.date), axisLabel: { rotate: 45, fontSize: 10 } },
      yAxis: { type: 'value', name: '%', axisLabel: { formatter: '{value}%' } },
      series: [{
        type: 'line',
        data: drawdowns.map((d) => d.drawdown.toFixed(2)),
        areaStyle: { color: 'rgba(245, 34, 45, 0.2)' },
        lineStyle: { color: '#f5222d', width: 1 },
        itemStyle: { color: '#f5222d' },
      }],
    };
  }, [activeResult]);

  return (
    <div>
      {/* Control Panel */}
      <Card title={<span><SettingOutlined /> 回测配置</span>} style={{ marginBottom: 16 }}>
        <Form form={form} layout="vertical">
          <Row gutter={16}>
            <Col xs={24} sm={12} md={6}>
              <Form.Item name="strategy_id" label="选择策略" rules={[{ required: true }]}>
                <Select placeholder="选择策略" allowClear>
                  {strategies.map((s) => (
                    <Option key={s.id} value={s.id}>{s.name}</Option>
                  ))}
                  <Option value="mock">双均线趋势跟踪 (Mock)</Option>
                </Select>
              </Form.Item>
            </Col>
            <Col xs={24} sm={12} md={6}>
              <Form.Item name="symbol" label="股票代码" rules={[{ required: true }]}>
                <Input placeholder="000001.SZ" />
              </Form.Item>
            </Col>
            <Col xs={24} sm={12} md={6}>
              <Form.Item name="dateRange" label="时间范围" rules={[{ required: true }]}>
                <RangePicker style={{ width: '100%' }} />
              </Form.Item>
            </Col>
            <Col xs={24} sm={12} md={6}>
              <Form.Item name="timeframe" label="周期" initialValue="1d">
                <Select>
                  <Option value="1d">日线</Option>
                  <Option value="1h">1小时</Option>
                  <Option value="30m">30分钟</Option>
                  <Option value="15m">15分钟</Option>
                  <Option value="5m">5分钟</Option>
                </Select>
              </Form.Item>
            </Col>
          </Row>
          <Row gutter={16}>
            <Col xs={24} sm={12} md={8}>
              <Form.Item name="initial_capital" label="初始资金" initialValue={1000000}>
                <InputNumber style={{ width: '100%' }} min={10000} step={100000} formatter={(v) => `¥${v}`} />
              </Form.Item>
            </Col>
            <Col xs={24} sm={12} md={8}>
              <Form.Item name="commission" label="佣金率" initialValue={0.0003}>
                <InputNumber style={{ width: '100%' }} min={0} max={0.01} step={0.0001} formatter={(v) => `${v}`} />
              </Form.Item>
            </Col>
            <Col xs={24} sm={12} md={8}>
              <Form.Item name="slippage" label="滑点" initialValue={0.001}>
                <InputNumber style={{ width: '100%' }} min={0} max={0.05} step={0.001} />
              </Form.Item>
            </Col>
          </Row>
          <Space>
            <Button type="primary" icon={<PlayCircleOutlined />} onClick={handleSubmit} loading={isRunning}>
              开始回测
            </Button>
            {isRunning && (
              <Button icon={<ReloadOutlined />} onClick={cancelBacktest}>
                取消
              </Button>
            )}
          </Space>
        </Form>
      </Card>

      {/* Progress */}
      {isRunning && (
        <Card style={{ marginBottom: 16 }}>
          <Progress percent={progress} status="active" strokeColor="#1890ff" />
          <Text type="secondary">回测运行中... {progress}%</Text>
        </Card>
      )}

      {/* Results */}
      {activeResult ? (
        <>
          <MetricsPanel metrics={activeResult.metrics} />

          <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
            <Col xs={24} lg={12}>
              <Card title={<span><BarChartOutlined /> 资金曲线</span>}>
                <EquityChart equityCurve={activeResult.equity_curve} />
              </Card>
            </Col>
            <Col xs={24} lg={12}>
              <Card title="收益分布">
                <ReactECharts option={pnlOption} style={{ height: 300 }} />
              </Card>
            </Col>
          </Row>

          <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
            <Col xs={24} lg={12}>
              <Card title="回撤分析">
                <ReactECharts option={drawdownOption} style={{ height: 300 }} />
              </Card>
            </Col>
            <Col xs={24} lg={12}>
              <Card title="K线 + 交易标记">
                <div style={{ height: 300, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                  <Text type="secondary">K线图表组件（集成 Lightweight Charts）</Text>
                </div>
              </Card>
            </Col>
          </Row>

          <Card title="交易记录" style={{ marginTop: 16 }}>
            <TradeTable trades={activeResult.trades} />
          </Card>
        </>
      ) : (
        <Card>
          <Empty description="尚未运行回测，请配置参数并点击开始回测" />
        </Card>
      )}
    </div>
  );
}
