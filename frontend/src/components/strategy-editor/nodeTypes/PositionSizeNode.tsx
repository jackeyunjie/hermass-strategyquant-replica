import React, { memo } from 'react';
import { Handle, Position, type NodeProps } from 'reactflow';
import { Card, Tag, Typography } from 'antd';
import { PercentageOutlined } from '@ant-design/icons';
import type { CustomNodeData, NodePort } from '../../../types';

const { Text } = Typography;

function PositionSizeNode({ data, selected }: NodeProps<CustomNodeData>) {
  const inputs = (data.inputs as NodePort[]) || [];
  const outputs = (data.outputs as NodePort[]) || [];
  const sizingType = (data.sizingType as string) || 'fixed';
  const value = (data.value as number) || 100000;

  const displayText = sizingType === 'fixed' ? `固定 ¥${value}` :
    sizingType === 'percent' ? `资金 ${value}%` :
    sizingType === 'atr' ? `ATR 风险 ${value}%` : `${value}`;

  return (
    <Card
      
      className={`custom-node position-size-node ${selected ? 'selected' : ''}`}
      style={{
        width: 170,
        borderRadius: 8,
        borderColor: (data.color as string) || '#2f54eb',
        boxShadow: selected ? `0 0 0 2px ${(data.color as string) || '#2f54eb'}` : '0 2px 8px rgba(0,0,0,0.1)',
      }}
      bodyStyle={{ padding: '8px 12px' }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
        <PercentageOutlined style={{ color: (data.color as string) || '#2f54eb' }} />
        <Text strong style={{ fontSize: 13 }}>{data.label}</Text>
      </div>
      <div style={{ marginBottom: 4 }}>
        <Tag color="blue">{displayText}</Tag>
      </div>

      {inputs.map((port, i) => (
        <Handle
          key={port.id}
          type="target"
          position={Position.Left}
          id={port.id}
          style={{
            top: 40 + i * 20,
            left: -6,
            width: 10,
            height: 10,
            background: '#2f54eb',
            border: '2px solid #fff',
          }}
        />
      ))}
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
            background: '#2f54eb',
            border: '2px solid #fff',
          }}
        />
      ))}
    </Card>
  );
}

export default memo(PositionSizeNode);
