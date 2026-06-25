import React, { useState, useCallback, useEffect } from 'react';
import {
  Typography,
  Row,
  Col,
  Card,
  List,
  Tag,
  Button,
  Space,
} from 'antd';
import {
  HistoryOutlined,
  ExperimentOutlined,
  ReloadOutlined,
} from '@ant-design/icons';
import BacktestDashboard from '../components/backtest-dashboard/BacktestDashboard';
import { mockBacktestResult } from '../utils/mockData';
import type { BacktestResult } from '../types';

const { Title, Text } = Typography;

export default function BacktestPage() {
  const [history, setHistory] = useState<BacktestResult[]>([]);
  const [selectedResult, setSelectedResult] = useState<BacktestResult | null>(null);
  const [loading, setLoading] = useState(false);

  const loadHistory = useCallback(() => {
    setLoading(true);
    // Simulate API call
    setTimeout(() => {
      const results = Array.from({ length: 5 }, () => mockBacktestResult());
      setHistory(results);
      if (results.length > 0) {
        setSelectedResult(results[0]);
      }
      setLoading(false);
    }, 500);
  }, []);

  useEffect(() => {
    loadHistory();
  }, [loadHistory]);

  const handleSelectResult = useCallback((result: BacktestResult) => {
    setSelectedResult(result);
  }, []);

  const handleNewBacktest = useCallback(() => {
    setSelectedResult(null);
  }, []);

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
        <Title level={3} style={{ margin: 0 }}>回测中心</Title>
        <Space>
          <Button icon={<ReloadOutlined />} onClick={loadHistory} loading={loading}>
            刷新
          </Button>
          <Button type="primary" icon={<ExperimentOutlined />} onClick={handleNewBacktest}>
            新建回测
          </Button>
        </Space>
      </div>

      <Row gutter={[16, 16]}>
        <Col xs={24} lg={5}>
          <Card
            title={
              <span>
                <HistoryOutlined /> 回测历史
              </span>
            }
            bodyStyle={{ padding: 0, maxHeight: 600, overflow: 'auto' }}
          >
            <List
              dataSource={history}
              loading={loading}
              renderItem={(item) => (
                <List.Item
                  style={{
                    cursor: 'pointer',
                    padding: '12px 16px',
                    background: selectedResult?.run_id === item.run_id ? '#e6f7ff' : 'transparent',
                    borderLeft: selectedResult?.run_id === item.run_id ? '3px solid #1890ff' : '3px solid transparent',
                  }}
                  onClick={() => handleSelectResult(item)}
                >
                  <div style={{ width: '100%' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <Text strong style={{ fontSize: 13 }}>{item.strategy_name}</Text>
                      <Tag color={item.metrics.total_return_pct > 0 ? 'success' : 'error'}>
                        {item.metrics.total_return_pct.toFixed(2)}%
                      </Tag>
                    </div>
                    <Text type="secondary" style={{ fontSize: 12 }}>
                      {item.period.start_date} ~ {item.period.end_date}
                    </Text>
                  </div>
                </List.Item>
              )}
            />
          </Card>
        </Col>

        <Col xs={24} lg={19}>
          {selectedResult ? (
            <BacktestDashboard initialResult={selectedResult} />
          ) : (
            <BacktestDashboard />
          )}
        </Col>
      </Row>
    </div>
  );
}
