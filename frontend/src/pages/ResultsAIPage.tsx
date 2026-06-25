import React, { useCallback, useMemo, useState } from 'react';
import {
  Alert,
  Button,
  Card,
  Col,
  Divider,
  Input,
  List,
  Progress,
  Row,
  Space,
  Statistic,
  Tag,
  Typography,
  message,
} from 'antd';
import {
  BulbOutlined,
  ExperimentOutlined,
  RobotOutlined,
  SafetyOutlined,
} from '@ant-design/icons';
import ReactECharts from 'echarts-for-react';
import { api } from '../services/api';
import { mockBacktestResult } from '../utils/mockData';
import type { BacktestResult, ResultsAIReport } from '../types';

const { Title, Text, Paragraph } = Typography;

const severityColor: Record<string, string> = {
  high: 'error',
  medium: 'warning',
  low: 'success',
};

export default function ResultsAIPage() {
  const [question, setQuestion] = useState('这条策略是否适合进入实盘候选池？');
  const [backtestJson, setBacktestJson] = useState(() => JSON.stringify(mockBacktestResult(), null, 2));
  const [report, setReport] = useState<ResultsAIReport | null>(null);
  const [loading, setLoading] = useState(false);

  const parsedBacktest = useMemo<BacktestResult | null>(() => {
    try {
      return JSON.parse(backtestJson) as BacktestResult;
    } catch {
      return null;
    }
  }, [backtestJson]);

  const runAnalysis = useCallback(async () => {
    if (!parsedBacktest) {
      message.error('回测 JSON 格式不正确');
      return;
    }
    setLoading(true);
    try {
      const result = await api.analyzeResultsAI({
        backtest_result: parsedBacktest,
        strategy_context: {
          market: 'A股',
          review_stage: 'candidate_selection',
        },
        question,
      });
      setReport(result);
      message.success('Results AI 分析完成');
    } catch (error) {
      const fallback = localAnalyze(parsedBacktest, question);
      setReport(fallback);
      message.warning('后端不可用，已使用前端离线分析结果');
    } finally {
      setLoading(false);
    }
  }, [parsedBacktest, question]);

  const chartOption = useMemo(() => {
    if (!parsedBacktest) return {};
    return {
      grid: { left: 36, right: 16, top: 24, bottom: 28 },
      tooltip: { trigger: 'axis' },
      xAxis: {
        type: 'category',
        data: parsedBacktest.equity_curve.map((item) => item.date),
        axisLabel: { fontSize: 10 },
      },
      yAxis: { type: 'value', scale: true },
      series: [{
        name: 'Equity',
        type: 'line',
        smooth: true,
        data: parsedBacktest.equity_curve.map((item) => item.equity),
        areaStyle: { color: 'rgba(24,144,255,0.12)' },
        lineStyle: { color: '#1890ff', width: 2 },
        symbol: 'none',
      }],
    };
  }, [parsedBacktest]);

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
        <Title level={3} style={{ margin: 0 }}>Results AI</Title>
        <Button type="primary" icon={<RobotOutlined />} loading={loading} onClick={runAnalysis}>
          分析回测结果
        </Button>
      </div>

      <Row gutter={[16, 16]}>
        <Col xs={24} xl={9}>
          <Card title="分析输入">
            <Space direction="vertical" style={{ width: '100%' }} size={12}>
              <Input.TextArea
                value={question}
                onChange={(event) => setQuestion(event.target.value)}
                rows={2}
                placeholder="输入你希望 Results AI 回答的问题"
              />
              <Input.TextArea
                value={backtestJson}
                onChange={(event) => setBacktestJson(event.target.value)}
                rows={22}
                spellCheck={false}
                style={{ fontFamily: 'Menlo, Monaco, Consolas, monospace', fontSize: 12 }}
              />
            </Space>
          </Card>
        </Col>

        <Col xs={24} xl={15}>
          <Row gutter={[16, 16]}>
            <Col xs={24}>
              <Card title="资金曲线">
                {parsedBacktest ? (
                  <ReactECharts option={chartOption} style={{ height: 260 }} />
                ) : (
                  <Alert type="error" message="回测 JSON 无法解析" />
                )}
              </Card>
            </Col>

            {report && (
              <>
                <Col xs={24} md={8}>
                  <Card>
                    <Statistic title="质量分" value={report.quality_score} suffix="/100" prefix={<BulbOutlined />} />
                    <Progress percent={Math.round(report.quality_score)} showInfo={false} strokeColor="#52c41a" />
                  </Card>
                </Col>
                <Col xs={24} md={8}>
                  <Card>
                    <Statistic title="风险分" value={report.risk_score} suffix="/100" prefix={<SafetyOutlined />} />
                    <Progress percent={Math.round(report.risk_score)} showInfo={false} strokeColor="#fa8c16" />
                  </Card>
                </Col>
                <Col xs={24} md={8}>
                  <Card>
                    <Statistic title="改进空间" value={report.opportunity_score} suffix="/100" prefix={<ExperimentOutlined />} />
                    <Progress percent={Math.round(report.opportunity_score)} showInfo={false} strokeColor="#1890ff" />
                  </Card>
                </Col>
                <Col xs={24}>
                  <Card
                    title={
                      <Space>
                        <RobotOutlined />
                        <span>{report.regime}</span>
                      </Space>
                    }
                  >
                    <Paragraph>{report.summary}</Paragraph>
                    <Divider />
                    <List
                      header={<Text strong>关键洞察</Text>}
                      dataSource={report.insights}
                      renderItem={(item) => (
                        <List.Item>
                          <List.Item.Meta
                            title={
                              <Space>
                                <Tag color={severityColor[item.severity]}>{item.severity}</Tag>
                                <Text strong>{item.title}</Text>
                              </Space>
                            }
                            description={
                              <Space direction="vertical" size={4}>
                                <Text>{item.evidence}</Text>
                                <Text type="secondary">{item.recommendation}</Text>
                              </Space>
                            }
                          />
                        </List.Item>
                      )}
                    />
                    <Divider />
                    <List
                      header={<Text strong>建议执行顺序</Text>}
                      dataSource={report.suggested_actions}
                      renderItem={(item, index) => (
                        <List.Item>
                          <Text>{index + 1}. {item}</Text>
                        </List.Item>
                      )}
                    />
                  </Card>
                </Col>
              </>
            )}
          </Row>
        </Col>
      </Row>
    </div>
  );
}

function localAnalyze(result: BacktestResult, question: string): ResultsAIReport {
  const metrics = result.metrics;
  const maxDrawdown = Math.abs(metrics.max_drawdown_pct || 0);
  const quality = Math.max(0, Math.min(100, 50 + metrics.sharpe_ratio * 14 + (metrics.profit_factor - 1) * 18 - maxDrawdown * 0.8));
  const risk = Math.max(0, Math.min(100, maxDrawdown * 2 + (metrics.total_trades < 20 ? 18 : 0)));
  const insights = [
    {
      title: maxDrawdown > 20 ? '回撤暴露偏高' : '回撤处于可监控范围',
      severity: maxDrawdown > 20 ? 'high' as const : 'medium' as const,
      evidence: `最大回撤 ${maxDrawdown.toFixed(2)}%，Sharpe ${metrics.sharpe_ratio.toFixed(2)}。`,
      recommendation: '执行 Monte Carlo 跳单、参数扰动和 WFO 复验。',
    },
    {
      title: metrics.total_trades < 20 ? '交易样本不足' : '交易样本可用于初筛',
      severity: metrics.total_trades < 20 ? 'high' as const : 'low' as const,
      evidence: `当前交易数 ${metrics.total_trades}。`,
      recommendation: '扩展回测区间或证券池后再确认上线优先级。',
    },
  ];
  return {
    summary: `针对问题「${question}」，离线分析认为策略质量分 ${quality.toFixed(1)}，风险分 ${risk.toFixed(1)}。`,
    regime: quality > 70 ? '可晋级候选' : '需稳健性确认',
    quality_score: Number(quality.toFixed(2)),
    risk_score: Number(risk.toFixed(2)),
    opportunity_score: Number(Math.max(0, 100 - quality + risk * 0.25).toFixed(2)),
    insights,
    suggested_actions: insights.map((item) => item.recommendation),
    prompt_context: { source: 'frontend_fallback' },
  };
}
