import React, { useMemo, useCallback } from 'react';
import {
  Form,
  Input,
  Select,
  InputNumber,
  Typography,
  Divider,
  Tag,
  Space,
  Empty,
} from 'antd';
import type { Node as FlowNode } from 'reactflow';
import type { CustomNodeData, NodePort } from '../../types';

const { Text, Title } = Typography;
const { Option } = Select;

interface PropertyPanelProps {
  selectedNode: FlowNode<CustomNodeData> | null;
  strategyName: string;
  strategyDescription: string;
  onUpdateNode: (nodeId: string, data: Partial<CustomNodeData>) => void;
  onUpdateStrategy: (name: string, description: string) => void;
}

export default function PropertyPanel({
  selectedNode,
  strategyName,
  strategyDescription,
  onUpdateNode,
  onUpdateStrategy,
}: PropertyPanelProps) {
  const nodeTypeLabels: Record<string, string> = {
    priceDataNode: '价格数据源',
    indicatorNode: '技术指标',
    comparatorNode: '比较器',
    logicalNode: '逻辑运算',
    mathNode: '数学运算',
    entryRuleNode: '入场规则',
    exitRuleNode: '出场规则',
    stopLossNode: '止损',
    takeProfitNode: '止盈',
    positionSizeNode: '仓位管理',
  };

  const handleNodeChange = useCallback(
    (field: string, value: unknown) => {
      if (!selectedNode) return;
      onUpdateNode(selectedNode.id, { ...selectedNode.data, [field]: value });
    },
    [selectedNode, onUpdateNode]
  );

  const renderNodeProperties = useMemo(() => {
    if (!selectedNode) return null;
    const type = selectedNode.type || '';
    const data = selectedNode.data;

    const commonFields = (
      <>
        <Form.Item label="节点 ID">
          <Input value={selectedNode.id} disabled size="small" />
        </Form.Item>
        <Form.Item label="节点名称">
          <Input
            value={(data.label as string) || ''}
            onChange={(e) => handleNodeChange('label', e.target.value)}
            size="small"
          />
        </Form.Item>
        <Form.Item label="节点类型">
          <Tag color="blue">{nodeTypeLabels[type] || type}</Tag>
        </Form.Item>
      </>
    );

    if (type === 'indicatorNode') {
      return (
        <>
          {commonFields}
          <Divider style={{ margin: '12px 0' }} />
          <Form.Item label="指标名称">
            <Select
              value={(data.indicator as string) || 'SMA'}
              onChange={(v) => handleNodeChange('indicator', v)}
              size="small"
            >
              <Option value="SMA">SMA - 简单移动平均</Option>
              <Option value="EMA">EMA - 指数移动平均</Option>
              <Option value="RSI">RSI - 相对强弱指数</Option>
              <Option value="MACD">MACD - 异同移动平均线</Option>
              <Option value="BB">Bollinger Bands - 布林带</Option>
              <Option value="ATR">ATR - 平均真实波幅</Option>
              <Option value="KDJ">KDJ - 随机指标</Option>
              <Option value="OBV">OBV - 能量潮</Option>
            </Select>
          </Form.Item>
          <Form.Item label="周期">
            <InputNumber
              value={(data.period as number) || 20}
              onChange={(v) => handleNodeChange('period', v)}
              min={1}
              max={500}
              size="small"
              style={{ width: '100%' }}
            />
          </Form.Item>
        </>
      );
    }

    if (type === 'comparatorNode') {
      return (
        <>
          {commonFields}
          <Divider style={{ margin: '12px 0' }} />
          <Form.Item label="比较符">
            <Select
              value={(data.operator as string) || '>'}
              onChange={(v) => handleNodeChange('operator', v)}
              size="small"
            >
              <Option value=">">大于 (&#62;)</Option>
              <Option value="<">小于 (&lt;)</Option>
              <Option value="=">等于 (=)</Option>
              <Option value=">=">大于等于 (≥)</Option>
              <Option value="<=">小于等于 (≤)</Option>
              <Option value="!=">不等于 (!=)</Option>
            </Select>
          </Form.Item>
        </>
      );
    }

    if (type === 'logicalNode') {
      return (
        <>
          {commonFields}
          <Divider style={{ margin: '12px 0' }} />
          <Form.Item label="逻辑符">
            <Select
              value={(data.operator as string) || 'AND'}
              onChange={(v) => handleNodeChange('operator', v)}
              size="small"
            >
              <Option value="AND">与 (AND)</Option>
              <Option value="OR">或 (OR)</Option>
              <Option value="NOT">非 (NOT)</Option>
              <Option value="XOR">异或 (XOR)</Option>
            </Select>
          </Form.Item>
        </>
      );
    }

    if (type === 'mathNode') {
      return (
        <>
          {commonFields}
          <Divider style={{ margin: '12px 0' }} />
          <Form.Item label="运算符">
            <Select
              value={(data.operator as string) || '+'}
              onChange={(v) => handleNodeChange('operator', v)}
              size="small"
            >
              <Option value="+">加 (+)</Option>
              <Option value="-">减 (-)</Option>
              <Option value="*">乘 (*)</Option>
              <Option value="/">除 (/)</Option>
              <Option value="%">取模 (%)</Option>
              <Option value="**">幂 (^)</Option>
            </Select>
          </Form.Item>
        </>
      );
    }

    if (type === 'stopLossNode' || type === 'takeProfitNode') {
      return (
        <>
          {commonFields}
          <Divider style={{ margin: '12px 0' }} />
          <Form.Item label="止损类型">
            <Select
              value={(data.sizingType as string) || 'atr'}
              onChange={(v) => handleNodeChange('sizingType', v)}
              size="small"
            >
              <Option value="atr">ATR 倍数</Option>
              <Option value="fixed">固定点数</Option>
            </Select>
          </Form.Item>
          <Form.Item label={type === 'stopLossNode' ? 'ATR倍数 / 点数' : 'ATR倍数 / 点数'}>
            <InputNumber
              value={(data.atrMultiplier as number) || (type === 'stopLossNode' ? 2 : 3)}
              onChange={(v) => handleNodeChange('atrMultiplier', v)}
              min={0.1}
              max={100}
              step={0.1}
              size="small"
              style={{ width: '100%' }}
            />
          </Form.Item>
        </>
      );
    }

    if (type === 'positionSizeNode') {
      return (
        <>
          {commonFields}
          <Divider style={{ margin: '12px 0' }} />
          <Form.Item label="仓位类型">
            <Select
              value={(data.sizingType as string) || 'fixed'}
              onChange={(v) => handleNodeChange('sizingType', v)}
              size="small"
            >
              <Option value="fixed">固定金额</Option>
              <Option value="percent">资金百分比</Option>
              <Option value="atr">ATR 风险</Option>
            </Select>
          </Form.Item>
          <Form.Item label="数值">
            <InputNumber
              value={(data.value as number) || 100000}
              onChange={(v) => handleNodeChange('value', v)}
              min={1}
              max={10000000}
              step={1000}
              size="small"
              style={{ width: '100%' }}
            />
          </Form.Item>
        </>
      );
    }

    if (type === 'priceDataNode') {
      return (
        <>
          {commonFields}
          <Divider style={{ margin: '12px 0' }} />
          <Form.Item label="股票代码">
            <Input
              value={(data.symbol as string) || '000001.SZ'}
              onChange={(e) => handleNodeChange('symbol', e.target.value)}
              size="small"
            />
          </Form.Item>
          <Form.Item label="时间周期">
            <Select
              value={(data.timeframe as string) || '1d'}
              onChange={(v) => handleNodeChange('timeframe', v)}
              size="small"
            >
              <Option value="1d">日线</Option>
              <Option value="1h">1小时</Option>
              <Option value="30m">30分钟</Option>
              <Option value="15m">15分钟</Option>
              <Option value="5m">5分钟</Option>
              <Option value="1m">1分钟</Option>
            </Select>
          </Form.Item>
        </>
      );
    }

    return commonFields;
  }, [selectedNode, handleNodeChange, nodeTypeLabels]);

  return (
    <div
      style={{
        width: 280,
        background: '#fff',
        borderLeft: '1px solid #f0f0f0',
        display: 'flex',
        flexDirection: 'column',
        height: '100%',
        overflow: 'hidden',
      }}
    >
      <div style={{ padding: '12px 16px', borderBottom: '1px solid #f0f0f0' }}>
        <Title level={5} style={{ margin: 0 }}>属性面板</Title>
      </div>
      <div style={{ flex: 1, overflow: 'auto', padding: '12px 16px' }}>
        {selectedNode ? (
          <Form layout="vertical" size="small">
            {renderNodeProperties}
            <Divider style={{ margin: '12px 0' }} />
            <div>
              <Text type="secondary" style={{ fontSize: 12 }}>输入端口</Text>
              <Space direction="vertical" size="small" style={{ marginTop: 8 }}>
                {((selectedNode.data.inputs as NodePort[]) || []).map((port) => (
                  <Tag key={port.id} color="blue">
                    {port.label} ({port.type})
                  </Tag>
                ))}
                {((selectedNode.data.inputs as NodePort[]) || []).length === 0 && (
                  <Text type="secondary" style={{ fontSize: 12 }}>无输入端口</Text>
                )}
              </Space>
            </div>
            <div style={{ marginTop: 12 }}>
              <Text type="secondary" style={{ fontSize: 12 }}>输出端口</Text>
              <Space direction="vertical" size="small" style={{ marginTop: 8 }}>
                {((selectedNode.data.outputs as NodePort[]) || []).map((port) => (
                  <Tag key={port.id} color="green">
                    {port.label} ({port.type})
                  </Tag>
                ))}
                {((selectedNode.data.outputs as NodePort[]) || []).length === 0 && (
                  <Text type="secondary" style={{ fontSize: 12 }}>无输出端口</Text>
                )}
              </Space>
            </div>
          </Form>
        ) : (
          <>
            <Form layout="vertical" size="small">
              <Form.Item label="策略名称">
                <Input
                  value={strategyName}
                  onChange={(e) => onUpdateStrategy(e.target.value, strategyDescription)}
                  size="small"
                  placeholder="未命名策略"
                />
              </Form.Item>
              <Form.Item label="策略描述">
                <Input.TextArea
                  value={strategyDescription}
                  onChange={(e) => onUpdateStrategy(strategyName, e.target.value)}
                  rows={3}
                  size="small"
                  placeholder="描述策略逻辑..."
                />
              </Form.Item>
            </Form>
            <Divider />
            <Empty
              image={Empty.PRESENTED_IMAGE_SIMPLE}
              description="选择节点以编辑属性"
              style={{ marginTop: 32 }}
            />
          </>
        )}
      </div>
    </div>
  );
}
