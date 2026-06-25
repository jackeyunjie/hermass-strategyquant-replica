import React, { useMemo } from 'react';
import {
  Card,
  Statistic,
  Row,
  Col,
  Table,
  Tag,
  Progress,
  Typography,
  Button,
  Space,
  Tooltip,
} from 'antd';
import {
  BuildOutlined,
  ExperimentOutlined,
  TrophyOutlined,
  RiseOutlined,
  EditOutlined,
  PlayCircleOutlined,
  ReloadOutlined,
  BarChartOutlined,
} from '@ant-design/icons';
import ReactECharts from 'echarts-for-react';
import { useAppStore } from '../stores/appStore';
import { useStrategy } from '../hooks/useStrategy';
import { useBacktest } from '../hooks/useBacktest';
import {
  formatCurrency,
  formatPercentage,
  formatNumber,
  formatDate,
  formatStatus,
} from '../utils/formatters';
import {
  mockStrategies,
  mockTaskList,
  mockEquityCurve,
} from '../utils/mockData';
import type { Strategy, TaskStatus } from '../types';

const { Title, Text } = Typography;

export default function Dashboard() {
  const activePage = useAppStore((s) => s.activePage);
  const setActivePage = useAppStore((s) => s.setActivePage);
  const { strategies } = useStrategy();
  const { isRunning } = useBacktest();

  const recentStrategies = useMemo(() => {
    const list = strategies.length > 0 ? strategies : mockStrategies(5);
    return list.slice(0, 5);
  }, [strategies]);

  const recentTasks = useMemo(() => {
    return mockTaskList(5);
  }, []);

  const equityData = useMemo(() => {
    const curve = mockEquityCurve('2024-01-01', 60);
    return curve.map((d) => [d.date, d.equity]);
  }, []);

  const chartOption = useMemo(() => {
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
      tooltip: {
        trigger: 'axis',
        formatter: (params: Array<{ value: [string, number] }>) => {
          const p = params[0];
          return `${p.value[0]}<br/>净值: ${formatCurrency(p.value[1])}`;
        },
      },
      series: [
        {
          name: '资金曲线',
          type: 'line',
          data: equityData.map((d) => d[1]),
          smooth: true,
          areaStyle: {
            color: {
              type: 'linear',
              x: 0, y: 0, x2: 0, y2: 1,
              colorStops: [
                { offset: 0, color: 'rgba(24, 144, 255, 0.3)' },
                { offset: 1, color: 'rgba(24, 144, 255, 0.01)' },
              ],
            },
          },
          lineStyle: { color: '#1890ff', width: 2 },
          itemStyle: { color: '#1890ff' },
        },
      ],
    };
  }, [equityData]);

  const strategyColumns = [
    {
      title: '策略名称',
      dataIndex: 'name',
      key: 'name',
      render: (text: string) => <Text strong>{text}</Text>,
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      render: (status: string) => {
        const colorMap: Record<string, string> = {
          draft: 'default',
          active: 'success',
          archived: 'warning',
        };
        return <Tag color={colorMap[status] || 'default'}>{formatStatus(status)}</Tag>;
      },
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      render: (date: string) => formatDate(date),
    },
    {
      title: '操作',
      key: 'action',
      render: (_: unknown, record: Strategy) => (
        <Space size="small">
          <Tooltip title="编辑">
            <Button type="text" icon={<EditOutlined />} size="small" />
          </Tooltip>
          <Tooltip title="回测">
            <Button type="text" icon={<PlayCircleOutlined />} size="small" />
          </Tooltip>
        </Space>
      ),
    },
  ];

  const taskColumns = [
    {
      title: '任务ID',
      dataIndex: 'task_id',
      key: 'task_id',
      render: (id: string) => id.slice(0, 8),
    },
    {
      title: '策略',
      dataIndex: 'strategy_name',
      key: 'strategy_name',
      render: () => '双均线趋势跟踪',
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      render: (status: string) => {
        const colorMap: Record<string, string> = {
          pending: 'default',
          running: 'processing',
          completed: 'success',
          failed: 'error',
        };
        return <Tag color={colorMap[status] || 'default'}>{formatStatus(status)}</Tag>;
      },
    },
    {
      title: '进度',
      dataIndex: 'progress',
      key: 'progress',
      render: (progress: number, record: TaskStatus) => (
        <Progress
          percent={progress}
          size="small"
          status={record.status === 'failed' ? 'exception' : undefined}
        />
      ),
    },
    {
      title: '操作',
      key: 'action',
      render: () => (
        <Space size="small">
          <Button type="text" icon={<ReloadOutlined />} size="small" />
        </Space>
      ),
    },
  ];

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
        <Title level={3} style={{ margin: 0 }}>仪表盘</Title>
      </div>

      <Row gutter={[16, 16]}>
        <Col xs={24} sm={12} lg={6}>
          <Card>
            <Statistic
              title="总策略数"
              value={recentStrategies.length}
              prefix={<BuildOutlined />}
              valueStyle={{ color: '#1890ff' }}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card>
            <Statistic
              title="今日回测次数"
              value={3}
              prefix={<ExperimentOutlined />}
              valueStyle={{ color: '#722ed1' }}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card>
            <Statistic
              title="平均夏普比率"
              value={1.523}
              precision={3}
              prefix={<TrophyOutlined />}
              valueStyle={{ color: '#52c41a' }}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card>
            <Statistic
              title="组合收益率"
              value={12.34}
              precision={2}
              suffix="%"
              prefix={<RiseOutlined />}
              valueStyle={{ color: '#52c41a' }}
            />
          </Card>
        </Col>
      </Row>

      <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
        <Col xs={24} lg={12}>
          <Card
            title="资金曲线"
            extra={<Button type="text" icon={<BarChartOutlined />} size="small" />}
          >
            <ReactECharts
              option={chartOption}
              style={{ height: 300 }}
              opts={{ renderer: 'canvas' }}
            />
          </Card>
        </Col>

        <Col xs={24} lg={12}>
          <Card title="策略列表" extra={<Button type="link">查看全部</Button>}>
            <Table
              dataSource={recentStrategies}
              columns={strategyColumns}
              rowKey="id"
              pagination={false}
              size="small"
            />
          </Card>
        </Col>
      </Row>

      <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
        <Col xs={24}>
          <Card title="回测任务状态">
            <Table
              dataSource={recentTasks}
              columns={taskColumns}
              rowKey="task_id"
              pagination={false}
              size="small"
            />
          </Card>
        </Col>
      </Row>
    </div>
  );
}
