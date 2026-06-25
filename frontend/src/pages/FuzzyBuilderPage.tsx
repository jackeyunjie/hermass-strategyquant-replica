import React, { useCallback, useMemo, useState } from 'react';
import {
  Button,
  Card,
  Col,
  Form,
  Input,
  InputNumber,
  List,
  Row,
  Select,
  Space,
  Tag,
  Typography,
  message,
} from 'antd';
import { ForkOutlined, ImportOutlined } from '@ant-design/icons';
import ReactFlow, { Background, Controls, MiniMap } from 'reactflow';
import { api } from '../services/api';
import type { FuzzyStrategyResponse } from '../types';
import IndicatorNode from '../components/strategy-editor/nodeTypes/IndicatorNode';
import EntryRuleNode from '../components/strategy-editor/nodeTypes/EntryRuleNode';
import ExitRuleNode from '../components/strategy-editor/nodeTypes/ExitRuleNode';
import PositionSizeNode from '../components/strategy-editor/nodeTypes/PositionSizeNode';
import CustomFunctionNode from '../components/strategy-editor/nodeTypes/CustomFunctionNode';

const { Title, Text, Paragraph } = Typography;

const nodeTypes = {
  indicatorNode: IndicatorNode,
  customFunctionNode: CustomFunctionNode,
  entryRuleNode: EntryRuleNode,
  exitRuleNode: ExitRuleNode,
  positionSizeNode: PositionSizeNode,
};

export default function FuzzyBuilderPage() {
  const [form] = Form.useForm();
  const [result, setResult] = useState<FuzzyStrategyResponse | null>(null);
  const [loading, setLoading] = useState(false);

  const nodes = useMemo(() => result?.frontend_graph.nodes || [], [result]);
  const edges = useMemo(() => result?.frontend_graph.edges || [], [result]);
  const fuzzySpec = useMemo<any>(() => result?.fuzzy_spec || null, [result]);

  const generate = useCallback(async () => {
    const values = await form.validateFields();
    setLoading(true);
    try {
      const response = await api.generateFuzzyStrategy(values);
      setResult(response);
      message.success('模糊策略已生成');
    } catch (error) {
      const fallback = buildLocalFuzzy(values);
      setResult(fallback);
      message.warning('后端不可用，已使用前端模板生成');
    } finally {
      setLoading(false);
    }
  }, [form]);

  const saveToLocalStrategy = useCallback(() => {
    if (!result) return;
    localStorage.setItem('hermass:lastFuzzyStrategy', JSON.stringify(result.frontend_graph));
    message.success('策略图已保存到本地草稿缓存');
  }, [result]);

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
        <Title level={3} style={{ margin: 0 }}>Fuzzy Logic 策略生成</Title>
        <Space>
          <Button icon={<ImportOutlined />} disabled={!result} onClick={saveToLocalStrategy}>
            保存草稿
          </Button>
          <Button type="primary" icon={<ForkOutlined />} loading={loading} onClick={generate}>
            生成策略
          </Button>
        </Space>
      </div>

      <Row gutter={[16, 16]}>
        <Col xs={24} lg={7}>
          <Card title="生成参数">
            <Form
              form={form}
              layout="vertical"
              initialValues={{
                template: 'balanced',
                name: 'Fuzzy A股候选策略',
                buy_threshold: 0.62,
                sell_threshold: 0.58,
              }}
            >
              <Form.Item name="template" label="模板" rules={[{ required: true }]}>
                <Select
                  options={[
                    { label: '均衡模板', value: 'balanced' },
                    { label: '趋势动量', value: 'momentum' },
                    { label: '超卖反转', value: 'reversal' },
                  ]}
                />
              </Form.Item>
              <Form.Item name="name" label="策略名称">
                <Input />
              </Form.Item>
              <Form.Item name="buy_threshold" label="买入评分阈值">
                <InputNumber min={0.1} max={1} step={0.01} style={{ width: '100%' }} />
              </Form.Item>
              <Form.Item name="sell_threshold" label="卖出评分阈值">
                <InputNumber min={0.1} max={1} step={0.01} style={{ width: '100%' }} />
              </Form.Item>
            </Form>
          </Card>

          {fuzzySpec && (
            <Card title="规则解释" style={{ marginTop: 16 }}>
              <Paragraph type="secondary">{fuzzySpec.description}</Paragraph>
              <List
                dataSource={fuzzySpec.rules || []}
                renderItem={(rule: any) => (
                  <List.Item>
                    <Space direction="vertical" size={4}>
                      <Space>
                        <Tag color={rule.action === 'buy' ? 'success' : 'error'}>{rule.action}</Tag>
                        <Text strong>{rule.name}</Text>
                      </Space>
                      <Text type="secondary">
                        {(rule.clauses || []).map((clause: any) => `${clause.variable}.${clause.membership}`).join(' + ')}
                      </Text>
                    </Space>
                  </List.Item>
                )}
              />
            </Card>
          )}
        </Col>

        <Col xs={24} lg={17}>
          <Card title="生成策略图" bodyStyle={{ height: 680, padding: 0 }}>
            {nodes.length > 0 ? (
              <ReactFlow nodeTypes={nodeTypes} nodes={nodes as any} edges={edges as any} fitView>
                <Background />
                <MiniMap />
                <Controls />
              </ReactFlow>
            ) : (
              <div style={{ padding: 32 }}>
                <Text type="secondary">生成后将在这里显示模糊变量、规则评分和交易动作链路。</Text>
              </div>
            )}
          </Card>
        </Col>
      </Row>
    </div>
  );
}

function buildLocalFuzzy(values: any): FuzzyStrategyResponse {
  const variables = [
    { name: 'trend_strength', source: 'ADX' },
    { name: 'volume_pressure', source: 'volume_ratio_20' },
    { name: 'risk_heat', source: 'ATR_pct' },
    { name: 'reversal_pressure', source: 'RSI' },
  ];
  const rules = [
    { name: '趋势确认买入', action: 'buy', clauses: [{ variable: 'trend_strength', membership: 'strong' }, { variable: 'volume_pressure', membership: 'high' }] },
    { name: '过热卖出', action: 'sell', clauses: [{ variable: 'risk_heat', membership: 'hot' }, { variable: 'reversal_pressure', membership: 'overbought' }] },
  ];
  const nodes = [
    ...variables.map((variable, index) => ({
      id: `local-var-${variable.name}`,
      type: 'indicatorNode',
      position: { x: 0, y: 80 + index * 130 },
      data: { label: `模糊变量: ${variable.name}`, indicator: variable.source },
    })),
    ...rules.map((rule, index) => ({
      id: `local-rule-${index + 1}`,
      type: 'customFunctionNode',
      position: { x: 300, y: 120 + index * 180 },
      data: { label: rule.name, rule },
    })),
    { id: 'local-entry', type: 'entryRuleNode', position: { x: 620, y: 120 }, data: { label: '模糊买入评分' } },
    { id: 'local-exit', type: 'exitRuleNode', position: { x: 620, y: 320 }, data: { label: '模糊卖出评分' } },
  ];
  const edges = rules.map((rule, index) => ({
    id: `local-edge-${index + 1}`,
    source: `local-rule-${index + 1}`,
    sourceHandle: 'output',
    target: rule.action === 'buy' ? 'local-entry' : 'local-exit',
    targetHandle: 'condition',
  }));
  return {
    strategy_ir: { name: values.name, variables: { template: values.template } },
    frontend_graph: {
      nodes: nodes as any,
      edges: edges as any,
      fuzzy_spec: { name: values.name, description: '前端离线模板', rules },
    },
    fuzzy_spec: { name: values.name, description: '前端离线模板', rules },
  };
}
