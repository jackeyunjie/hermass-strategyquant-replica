import React, { memo } from 'react';
import { Handle, Position, type NodeProps } from 'reactflow';
import { Card, Tag, Typography } from 'antd';
import { ApiOutlined } from '@ant-design/icons';
import type { CustomNodeData, NodePort } from '../../../types';

const { Text } = Typography;

function LogicalNode({ data, selected }: NodeProps<CustomNodeData>) {
  const inputs = (data.inputs as NodePort[]) || [];
  const outputs = (data.outputs as NodePort[]) || [];
  const operator = (data.operator as string) || 'AND';

  return (
    <Card
      
      className={`custom-node logical-node ${selected ? 'selected' : ''}`}
      style={{
        width: 160,
        borderRadius: 8,
        borderColor: (data.color as string) || '#eb2f96',
        boxShadow: selected ? `0 0 0 2px ${(data.color as string) || '#eb2f96'}` : '0 2px 8px rgba(0,0,0,0.1)',
      }}
      bodyStyle={{ padding: '8px 12px' }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
        <ApiOutlined style={{ color: (data.color as string) || '#eb2f96' }} />
        <Text strong style={{ fontSize: 13 }}>{data.label}</Text>
      </div>
      <div style={{ textAlign: 'center', margin: '4px 0' }}>
        <Tag color="magenta">{operator}</Tag>
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
            background: '#eb2f96',
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
            background: '#eb2f96',
            border: '2px solid #fff',
          }}
        />
      ))}
    </Card>
  );
}

export default memo(LogicalNode);
