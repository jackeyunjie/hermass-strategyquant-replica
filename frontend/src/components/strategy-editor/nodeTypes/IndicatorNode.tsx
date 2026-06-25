import React, { memo } from 'react';
import { Handle, Position, type NodeProps } from 'reactflow';
import { Card, Tag, Typography, Select } from 'antd';
import { FunctionOutlined } from '@ant-design/icons';
import type { CustomNodeData, NodePort } from '../../../types';

const { Text } = Typography;

function IndicatorNode({ data, selected }: NodeProps<CustomNodeData>) {
  const inputs = (data.inputs as NodePort[]) || [];
  const outputs = (data.outputs as NodePort[]) || [];
  const indicator = (data.indicator as string) || 'SMA';
  const period = (data.period as number) || 20;

  return (
    <Card
      
      className={`custom-node indicator-node ${selected ? 'selected' : ''}`}
      style={{
        width: 180,
        borderRadius: 8,
        borderColor: (data.color as string) || '#722ed1',
        boxShadow: selected ? `0 0 0 2px ${(data.color as string) || '#722ed1'}` : '0 2px 8px rgba(0,0,0,0.1)',
      }}
      bodyStyle={{ padding: '8px 12px' }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
        <FunctionOutlined style={{ color: (data.color as string) || '#722ed1' }} />
        <Text strong style={{ fontSize: 13 }}>{data.label}</Text>
      </div>
      <div style={{ marginBottom: 4 }}>
        <Tag color="purple">{indicator}({period})</Tag>
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
            background: '#722ed1',
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
            background: '#722ed1',
            border: '2px solid #fff',
          }}
        />
      ))}
    </Card>
  );
}

export default memo(IndicatorNode);
