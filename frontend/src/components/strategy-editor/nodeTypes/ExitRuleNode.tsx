import React, { memo } from 'react';
import { Handle, Position, type NodeProps } from 'reactflow';
import { Card, Tag, Typography, Badge } from 'antd';
import { ArrowDownOutlined } from '@ant-design/icons';
import type { CustomNodeData, NodePort } from '../../../types';

const { Text } = Typography;

function ExitRuleNode({ data, selected }: NodeProps<CustomNodeData>) {
  const inputs = (data.inputs as NodePort[]) || [];
  const outputs = (data.outputs as NodePort[]) || [];

  return (
    <Card
      
      className={`custom-node exit-rule-node ${selected ? 'selected' : ''}`}
      style={{
        width: 160,
        borderRadius: 8,
        borderColor: (data.color as string) || '#f5222d',
        boxShadow: selected ? `0 0 0 2px ${(data.color as string) || '#f5222d'}` : '0 2px 8px rgba(0,0,0,0.1)',
      }}
      bodyStyle={{ padding: '8px 12px' }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
        <ArrowDownOutlined style={{ color: (data.color as string) || '#f5222d' }} />
        <Text strong style={{ fontSize: 13 }}>{data.label}</Text>
      </div>
      <div style={{ textAlign: 'center', margin: '4px 0' }}>
        <Badge status="error" text={<Tag color="red">SELL</Tag>} />
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
            background: '#f5222d',
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
            background: '#f5222d',
            border: '2px solid #fff',
          }}
        />
      ))}
    </Card>
  );
}

export default memo(ExitRuleNode);
