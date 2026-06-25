import React from 'react';
import { Row, Col, Card, Statistic, Badge } from 'antd';
import {
  ArrowUpOutlined,
  ArrowDownOutlined,
  TrophyOutlined,
  WarningOutlined,
  PercentageOutlined,
  LineChartOutlined,
} from '@ant-design/icons';
import type { PerformanceMetrics } from '../../types';

interface MetricsPanelProps {
  metrics: PerformanceMetrics;
}

export default function MetricsPanel({ metrics }: MetricsPanelProps) {
  const items = [
    {
      title: '净利润',
      value: metrics.net_profit,
      prefix: <LineChartOutlined />,
      precision: 2,
      prefixValue: '¥',
      color: metrics.net_profit >= 0 ? '#52c41a' : '#f5222d',
      trend: metrics.net_profit >= 0 ? 'up' : 'down' as const,
    },
    {
      title: '总收益率',
      value: metrics.total_return_pct,
      suffix: '%',
      precision: 2,
      prefix: <PercentageOutlined />,
      color: metrics.total_return_pct >= 0 ? '#52c41a' : '#f5222d',
      trend: metrics.total_return_pct >= 0 ? 'up' : 'down' as const,
    },
    {
      title: '夏普比率',
      value: metrics.sharpe_ratio,
      precision: 3,
      prefix: <TrophyOutlined />,
      color: metrics.sharpe_ratio >= 1 ? '#52c41a' : metrics.sharpe_ratio >= 0.5 ? '#faad14' : '#f5222d',
      trend: metrics.sharpe_ratio >= 1 ? 'up' : 'down' as const,
    },
    {
      title: '最大回撤',
      value: metrics.max_drawdown_pct,
      suffix: '%',
      precision: 2,
      prefix: <WarningOutlined />,
      color: '#f5222d',
      trend: 'down' as const,
    },
    {
      title: '胜率',
      value: metrics.win_rate,
      suffix: '%',
      precision: 1,
      prefix: <ArrowUpOutlined />,
      color: metrics.win_rate >= 50 ? '#52c41a' : '#faad14',
      trend: metrics.win_rate >= 50 ? 'up' : 'down' as const,
    },
    {
      title: '盈亏比',
      value: metrics.profit_factor,
      precision: 3,
      prefix: <ArrowDownOutlined />,
      color: metrics.profit_factor >= 1.5 ? '#52c41a' : metrics.profit_factor >= 1 ? '#faad14' : '#f5222d',
      trend: metrics.profit_factor >= 1 ? 'up' : 'down' as const,
    },
  ];

  return (
    <Row gutter={[16, 16]}>
      {items.map((item, index) => (
        <Col key={index} xs={24} sm={12} lg={8}>
          <Card bodyStyle={{ padding: 16 }}>
            <Statistic
              title={
                <span>
                  {item.prefix}
                  <span style={{ marginLeft: 8 }}>{item.title}</span>
                  <Badge
                    style={{ marginLeft: 8, backgroundColor: 'transparent' }}
                    count={
                      <span style={{ color: item.color, fontSize: 12 }}>
                        {item.trend === 'up' ? <ArrowUpOutlined /> : <ArrowDownOutlined />}
                      </span>
                    }
                  />
                </span>
              }
              value={item.value}
              precision={item.precision}
              suffix={item.suffix}
              prefix={item.prefixValue}
              valueStyle={{ color: item.color, fontSize: 24, fontWeight: 600 }}
            />
          </Card>
        </Col>
      ))}
    </Row>
  );
}
