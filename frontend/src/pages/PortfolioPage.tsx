import React, { useState, useMemo, useCallback } from 'react';
import {
  Card,
  Select,
  Slider,
  Button,
  Typography,
  Row,
  Col,
  Tag,
  Statistic,
  Space,
  Divider,
  message,
} from 'antd';
import {
  PieChartOutlined,
  PlayCircleOutlined,
  ReloadOutlined,
} from '@ant-design/icons';
import ReactECharts from 'echarts-for-react';
import { mockStrategies, mockEquityCurve, mockCorrelationMatrix } from '../utils/mockData';
import {
  formatCurrency,
  formatPercentage,
  formatNumber,
} from '../utils/formatters';
import type { Strategy } from '../types';

const { Title, Text } = Typography;
const { Option } = Select;

interface SelectedStrategy {
  id: string;
  name: string;
  weight: number;
}

export default function PortfolioPage() {
  const strategies = mockStrategies(10);
  const [selected, setSelected] = useState<SelectedStrategy[]>([]);
  const [resultVisible, setResultVisible] = useState(false);

  const handleStrategyChange = useCallback((ids: string[]) => {
    const newSelected = ids.map((id) => {
      const existing = selected.find((s) => s.id === id);
      if (existing) return existing;
      const strategy = strategies.find((s) => s.id === id);
      return { id, name: strategy?.name || id, weight: 0 };
    });
    // Equal weight distribution
    const count = newSelected.length;
    if (count > 0) {
      const equalWeight = Math.floor(100 / count);
      const remainder = 100 - equalWeight * count;
      newSelected.forEach((s, i) => {
        s.weight = equalWeight + (i === 0 ? remainder : 0);
      });
    }
    setSelected(newSelected);
  }, [selected, strategies]);

  const handleWeightChange = useCallback((id: string, weight: number) => {
    setSelected((prev) =>
      prev.map((s) => (s.id === id ? { ...s, weight } : s))
    );
  }, []);

  const totalWeight = useMemo(() => selected.reduce((sum, s) => sum + s.weight, 0), [selected]);

  const runPortfolioBacktest = useCallback(() => {
    if (selected.length === 0) {
      message.warning('请至少选择一个策略');
      return;
    }
    if (totalWeight !== 100) {
      message.warning('策略权重总和必须等于100%');
      return;
    }
    setResultVisible(true);
    message.success('组合回测完成');
  }, [selected, totalWeight]);

  const equityData = useMemo(() => {
    const curve = mockEquityCurve('2024-01-01', 60);
    return curve.map((d) => [d.date, d.equity]);
  }, []);

  const equityOption = useMemo(() => {
    return {
      grid: { left: '3%', right: '4%', bottom: '3%', top: '10%', containLabel: true },
      xAxis: {
        type: 'category',
        data: equityData.map((d) => d[0]),
        axisLabel: { rotate: 45, fontSize: 10 },
      },
      yAxis: {
        type: 'value',
        axisLabel: { formatter: (v: number) => `¥${(v / 10000).toFixed(1)}万` },
      },
      tooltip: { trigger: 'axis' },
      series: [
        {
          name: '组合资金曲线',
          type: 'line',
          data: equityData.map((d) => d[1]),
          smooth: true,
          lineStyle: { color: '#52c41a', width: 2 },
          itemStyle: { color: '#52c41a' },
          areaStyle: {
            color: {
              type: 'linear',
              x: 0, y: 0, x2: 0, y2: 1,
              colorStops: [
                { offset: 0, color: 'rgba(82, 196, 26, 0.3)' },
                { offset: 1, color: 'rgba(82, 196, 26, 0.01)' },
              ],
            },
          },
        },
      ],
    };
  }, [equityData]);

  const correlationMatrix = useMemo(() => mockCorrelationMatrix(selected.length || 3), [selected.length]);
  const labels = selected.length > 0 ? selected.map((s) => s.name) : ['策略A', '策略B', '策略C'];

  const correlationOption = useMemo(() => {
    const data: Array<[number, number, number]> = [];
    for (let i = 0; i < correlationMatrix.length; i++) {
      for (let j = 0; j < correlationMatrix[i].length; j++) {
        data.push([i, j, correlationMatrix[i][j]]);
      }
    }
    return {
      tooltip: {
        position: 'top',
        formatter: (params: { data: [number, number, number] }) => {
          return `${labels[params.data[0]]} vs ${labels[params.data[1]]}: ${params.data[2].toFixed(2)}`;
        },
      },
      grid: { height: '70%', top: '10%' },
      xAxis: {
        type: 'category',
        data: labels,
        splitArea: { show: true },
      },
      yAxis: {
        type: 'category',
        data: labels,
        splitArea: { show: true },
      },
      visualMap: {
        min: -1,
        max: 1,
        calculable: true,
        orient: 'horizontal',
        left: 'center',
        bottom: '5%',
        inRange: {
          color: ['#f5222d', '#fff', '#52c41a'],
        },
      },
      series: [
        {
          name: '相关性',
          type: 'heatmap',
          data,
          label: {
            show: true,
            formatter: (params: { data: [number, number, number] }) => params.data[2].toFixed(2),
          },
          emphasis: {
            itemStyle: {
              shadowBlur: 10,
              shadowColor: 'rgba(0, 0, 0, 0.5)',
            },
          },
        },
      ],
    };
  }, [correlationMatrix, labels]);

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
        <Title level={3} style={{ margin: 0 }}>组合管理</Title>
        <Space>
          <Button icon={<ReloadOutlined />}>刷新</Button>
          <Button type="primary" icon={<PlayCircleOutlined />} onClick={runPortfolioBacktest}>
            组合回测
          </Button>
        </Space>
      </div>

      <Row gutter={[16, 16]}>
        <Col xs={24} lg={12}>
          <Card title="策略选择" extra={<PieChartOutlined />}>
            <Select
              mode="multiple"
              style={{ width: '100%', marginBottom: 16 }}
              placeholder="选择策略组成组合"
              onChange={handleStrategyChange}
              value={selected.map((s) => s.id)}
            >
              {strategies.map((s) => (
                <Option key={s.id} value={s.id}>
                  {s.name} <Tag color="blue">{s.status}</Tag>
                </Option>
              ))}
            </Select>

            {selected.length > 0 && (
              <div>
                <Divider>权重设置</Divider>
                {selected.map((s) => (
                  <div key={s.id} style={{ marginBottom: 16 }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                      <Text strong>{s.name}</Text>
                      <Text>{s.weight}%</Text>
                    </div>
                    <Slider
                      min={0}
                      max={100}
                      value={s.weight}
                      onChange={(v) => handleWeightChange(s.id, v)}
                      tooltip={{ formatter: (v) => `${v}%` }}
                    />
                  </div>
                ))}
                <div style={{ textAlign: 'right', marginTop: 8 }}>
                  <Text type={totalWeight === 100 ? 'success' : 'warning'} strong>
                    总权重: {totalWeight}%
                  </Text>
                </div>
              </div>
            )}
          </Card>
        </Col>

        <Col xs={24} lg={12}>
          <Card title="组合统计">
            <Row gutter={[16, 16]}>
              <Col span={12}>
                <Statistic title="组合收益率" value={15.67} precision={2} suffix="%" valueStyle={{ color: '#52c41a' }} />
              </Col>
              <Col span={12}>
                <Statistic title="夏普比率" value={1.832} precision={3} />
              </Col>
              <Col span={12}>
                <Statistic title="最大回撤" value={-8.45} precision={2} suffix="%" valueStyle={{ color: '#f5222d' }} />
              </Col>
              <Col span={12}>
                <Statistic title="胜率" value={58.3} precision={1} suffix="%" />
              </Col>
            </Row>
          </Card>
        </Col>
      </Row>

      {resultVisible && (
        <>
          <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
            <Col xs={24} lg={12}>
              <Card title="组合资金曲线">
                <ReactECharts option={equityOption} style={{ height: 300 }} />
              </Card>
            </Col>
            <Col xs={24} lg={12}>
              <Card title="策略相关性矩阵">
                <ReactECharts option={correlationOption} style={{ height: 300 }} />
              </Card>
            </Col>
          </Row>
        </>
      )}
    </div>
  );
}
