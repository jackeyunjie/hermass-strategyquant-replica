import React, { memo } from 'react';
import { Handle, Position, type NodeProps } from 'reactflow';
import { Card, Tag, Typography } from 'antd';
import { CodeOutlined } from '@ant-design/icons';
import type { CustomNodeData, NodePort } from '../../../types';

const { Text } = Typography;

function CustomFunctionNode({ data, selected }: NodeProps<CustomNodeData>) {
  const inputs = (data.inputs as NodePort[]) || [
    { id: 'input', label: 'Input', type: 'any', required: false, direction: 'input' },
  ];
  const outputs = (data.outputs as NodePort[]) || [
    { id: 'output', label: 'Output', type: 'any', required: false, direction: 'output' },
  ];
  const functionName = (data.function as string) || 'custom';

  return (
    <Card
      className={`custom-node custom-function-node ${selected ? 'selected' : ''}`}
      style={{
        width: 200,
        borderRadius: 8,
        borderColor: (data.color as string) || '#22075e',
        boxShadow: selected ? `0 0 0 2px ${(data.color as string) || '#22075e'}` : '0 2px 8px rgba(0,0,0,0.1)',
      }}
      bodyStyle={{ padding: '8px 12px' }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
        <CodeOutlined style={{ color: (data.color as string) || '#22075e' }} />
        <Text strong style={{ fontSize: 13 }}>{data.label}</Text>
      </div>
      <Tag color="geekblue">{functionName}</Tag>

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
            background: '#22075e',
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
            background: '#22075e',
            border: '2px solid #fff',
          }}
        />
      ))}
    </Card>
  );
}

export default memo(CustomFunctionNode);
