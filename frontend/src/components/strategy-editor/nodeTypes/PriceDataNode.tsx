import React, { memo } from 'react';
import { Handle, Position, type NodeProps } from 'reactflow';
import { Card, Tag, Typography } from 'antd';
import { BarChartOutlined } from '@ant-design/icons';
import type { CustomNodeData, NodePort } from '../../../types';

const { Text } = Typography;

function PriceDataNode({ data, selected }: NodeProps<CustomNodeData>) {
  const outputs = (data.outputs as NodePort[]) || [];
  const symbol = (data.symbol as string) || '000001.SZ';
  const timeframe = (data.timeframe as string) || '1d';

  return (
    <Card
      
      className={`custom-node price-data-node ${selected ? 'selected' : ''}`}
      style={{
        width: 180,
        borderRadius: 8,
        borderColor: (data.color as string) || '#1890ff',
        boxShadow: selected ? `0 0 0 2px ${(data.color as string) || '#1890ff'}` : '0 2px 8px rgba(0,0,0,0.1)',
      }}
      bodyStyle={{ padding: '8px 12px' }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
        <BarChartOutlined style={{ color: (data.color as string) || '#1890ff' }} />
        <Text strong style={{ fontSize: 13 }}>{data.label}</Text>
      </div>
      <div style={{ marginBottom: 4 }}>
        <Tag>{symbol}</Tag>
        <Tag>{timeframe}</Tag>
      </div>

      {outputs.map((port, i) => (
        <Handle
          key={port.id}
          type="source"
          position={Position.Right}
          id={port.id}
          style={{
            top: 40 + i * 20,
            right: -6,
            width: 10,
            height: 10,
            background: '#1890ff',
            border: '2px solid #fff',
          }}
        />
      ))}
      <div style={{ position: 'absolute', right: -20, top: 40 }}>
        {outputs.map((port, i) => (
          <div
            key={port.id}
            style={{
              position: 'absolute',
              top: i * 20,
              fontSize: 10,
              color: '#666',
              whiteSpace: 'nowrap',
            }}
          >
            {port.label}
          </div>
        ))}
      </div>
    </Card>
  );
}

export default memo(PriceDataNode);
