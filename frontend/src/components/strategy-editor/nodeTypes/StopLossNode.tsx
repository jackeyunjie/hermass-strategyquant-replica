import React, { memo } from 'react';
import { Handle, Position, type NodeProps } from 'reactflow';
import { Card, Tag, Typography } from 'antd';
import { StopOutlined } from '@ant-design/icons';
import type { CustomNodeData, NodePort } from '../../../types';

const { Text } = Typography;

function StopLossNode({ data, selected }: NodeProps<CustomNodeData>) {
  const inputs = (data.inputs as NodePort[]) || [];
  const outputs = (data.outputs as NodePort[]) || [];
  const atrMultiplier = (data.atrMultiplier as number) || 2.0;
  const fixedPoints = (data.fixedPoints as number) || 0;

  return (
    <Card
      
      className={`custom-node stop-loss-node ${selected ? 'selected' : ''}`}
      style={{
        width: 170,
        borderRadius: 8,
        borderColor: (data.color as string) || '#ff4d4f',
        boxShadow: selected ? `0 0 0 2px ${(data.color as string) || '#ff4d4f'}` : '0 2px 8px rgba(0,0,0,0.1)',
      }}
      bodyStyle={{ padding: '8px 12px' }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
        <StopOutlined style={{ color: (data.color as string) || '#ff4d4f' }} />
        <Text strong style={{ fontSize: 13 }}>{data.label}</Text>
      </div>
      <div style={{ marginBottom: 4 }}>
        {fixedPoints > 0 ? (
          <Tag color="red">固定: {fixedPoints}点</Tag>
        ) : (
          <Tag color="red">ATR × {atrMultiplier}</Tag>
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
            background: '#ff4d4f',
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
            background: '#ff4d4f',
            border: '2px solid #fff',
          }}
        />
      ))}
    </Card>
  );
}

export default memo(StopLossNode);
