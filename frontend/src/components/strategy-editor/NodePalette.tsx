import React, { useState, useCallback } from 'react';
import { Collapse, Input, Space, Tag, Typography } from 'antd';
import {
  BarChartOutlined,
  FunctionOutlined,
  SwapOutlined,
  ApiOutlined,
  CalculatorOutlined,
  ArrowUpOutlined,
  ArrowDownOutlined,
  StopOutlined,
  SafetyOutlined,
  PercentageOutlined,
  FilterOutlined,
  QuestionOutlined,
  BranchesOutlined,
  AimOutlined,
} from '@ant-design/icons';
import type { NodeType } from '../../types';

const { Panel } = Collapse;
const { Text } = Typography;

interface PaletteItem {
  type: NodeType;
  label: string;
  icon: React.ReactNode;
  category: string;
}

const paletteItems: PaletteItem[] = [
  { type: 'priceDataNode', label: '价格数据', icon: <BarChartOutlined />, category: '数据源' },
  { type: 'indicatorNode', label: '技术指标', icon: <FunctionOutlined />, category: '指标' },
  { type: 'comparatorNode', label: '比较器', icon: <SwapOutlined />, category: '比较' },
  { type: 'logicalNode', label: '逻辑运算', icon: <ApiOutlined />, category: '逻辑' },
  { type: 'mathNode', label: '数学运算', icon: <CalculatorOutlined />, category: '数学' },
  { type: 'entryRuleNode', label: '入场规则', icon: <ArrowUpOutlined />, category: '规则' },
  { type: 'exitRuleNode', label: '出场规则', icon: <ArrowDownOutlined />, category: '规则' },
  { type: 'stopLossNode', label: '止损', icon: <StopOutlined />, category: '风控' },
  { type: 'takeProfitNode', label: '止盈', icon: <SafetyOutlined />, category: '风控' },
  { type: 'positionSizeNode', label: '仓位管理', icon: <PercentageOutlined />, category: '风控' },
];

const categories = ['数据源', '指标', '逻辑', '比较', '数学', '规则', '风控'];

const categoryIcons: Record<string, React.ReactNode> = {
  '数据源': <BarChartOutlined />,
  '指标': <FunctionOutlined />,
  '逻辑': <BranchesOutlined />,
  '比较': <SwapOutlined />,
  '数学': <CalculatorOutlined />,
  '规则': <AimOutlined />,
  '风控': <FilterOutlined />,
};

export default function NodePalette() {
  const [search, setSearch] = useState('');

  const filteredItems = paletteItems.filter((item) =>
    item.label.toLowerCase().includes(search.toLowerCase())
  );

  const onDragStart = useCallback(
    (event: React.DragEvent<HTMLDivElement>, nodeType: NodeType) => {
      event.dataTransfer.setData('application/reactflow', nodeType);
      event.dataTransfer.effectAllowed = 'move';
    },
    []
  );

  return (
    <div
      style={{
        width: 220,
        background: '#fff',
        borderRight: '1px solid #f0f0f0',
        display: 'flex',
        flexDirection: 'column',
        height: '100%',
        overflow: 'hidden',
      }}
    >
      <div style={{ padding: '12px 16px', borderBottom: '1px solid #f0f0f0' }}>
        <Input.Search
          placeholder="搜索节点..."
          size="small"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          allowClear
        />
      </div>
      <div style={{ flex: 1, overflow: 'auto', padding: '0 8px' }}>
        <Collapse
          defaultActiveKey={categories}
          ghost
          expandIconPosition="end"
          style={{ border: 'none' }}
        >
          {categories.map((category) => {
            const items = filteredItems.filter((item) => item.category === category);
            if (items.length === 0) return null;

            return (
              <Panel
                header={
                  <Space>
                    {categoryIcons[category] || <QuestionOutlined />}
                    <Text strong>{category}</Text>
                    <Tag>{items.length}</Tag>
                  </Space>
                }
                key={category}
                style={{ border: 'none' }}
              >
                <Space direction="vertical" size="small" style={{ width: '100%' }}>
                  {items.map((item) => (
                    <div
                      key={item.type}
                      draggable
                      onDragStart={(e) => onDragStart(e, item.type)}
                      style={{
                        padding: '8px 12px',
                        borderRadius: 6,
                        border: '1px solid #e8e8e8',
                        cursor: 'grab',
                        display: 'flex',
                        alignItems: 'center',
                        gap: 8,
                        transition: 'all 0.2s',
                      }}
                      onMouseEnter={(e) => {
                        e.currentTarget.style.background = '#f0f5ff';
                        e.currentTarget.style.borderColor = '#1890ff';
                      }}
                      onMouseLeave={(e) => {
                        e.currentTarget.style.background = '#fff';
                        e.currentTarget.style.borderColor = '#e8e8e8';
                      }}
                    >
                      {item.icon}
                      <Text style={{ fontSize: 13 }}>{item.label}</Text>
                    </div>
                  ))}
                </Space>
              </Panel>
            );
          })}
        </Collapse>
      </div>
    </div>
  );
}
