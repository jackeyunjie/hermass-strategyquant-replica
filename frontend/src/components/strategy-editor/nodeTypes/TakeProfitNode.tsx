import React, { memo } from 'react';
import { Handle, Position, type NodeProps } from 'reactflow';
import { Card, Tag, Typography } from 'antd';
import { SafetyOutlined } from '@ant-design/icons';
import type { CustomNodeData, NodePort } from '../../../types';

const { Text } = Typography;

function TakeProfitNode({ data, selected }: NodeProps<CustomNodeData>) {
  const inputs = (data.inputs as NodePort[]) || [];
  const outputs = (data.outputs as NodePort[]) || [];
  const atrMultiplier = (data.atrMultiplier as number) || 3.0;
  const fixedPoints = (data.fixedPoints as number) || 0;

  return (
    <Card
      
      className={`custom-node take-profit-node ${selected ? 'selected' : ''}`}
      style={{
        width: 170,
        borderRadius: 8,
        borderColor: (data.color as string) || '#faad14',
        boxShadow: selected ? `0 0 0 2px ${(data.color as string) || '#faad14'}` : '0 2px 8px rgba(0,0,0,0.1)',
      }}
      bodyStyle={{ padding: '8px 12px' }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
        <SafetyOutlined style={{ color: (data.color as string) || '#faad14' }} />
        <Text strong style={{ fontSize: 13 }}>{data.label}</Text>
      </div>
      <div style={{ marginBottom: 4 }}>
        {fixedPoints > 0 ? (
          <Tag color="orange">固定: {fixedPoints}点</Tag>
        ) : (
          <Tag color="orange">ATR × {atrMultiplier}</Tag>
        )}
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
            background: '#faad14',
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
            background: '#faad14',
            border: '2px solid #fff',
          }}
        />
      ))}
    </Card>
  );
}

export default memo(TakeProfitNode);
