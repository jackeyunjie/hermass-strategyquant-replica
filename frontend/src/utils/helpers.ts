import { type Node, type Edge, type XYPosition } from 'reactflow';
import type { CustomNodeData, NodePort, NodeType } from '../types';

export function generateUUID(): string {
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    const v = c === 'x' ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
}

export function deepClone<T>(obj: T): T {
  return JSON.parse(JSON.stringify(obj));
}

export function debounce<T extends (...args: unknown[]) => void>(
  fn: T,
  delay: number
): (...args: Parameters<T>) => void {
  let timer: ReturnType<typeof setTimeout> | null = null;
  return (...args: Parameters<T>) => {
    if (timer) clearTimeout(timer);
    timer = setTimeout(() => fn(...args), delay);
  };
}

export function throttle<T extends (...args: unknown[]) => void>(
  fn: T,
  limit: number
): (...args: Parameters<T>) => void {
  let inThrottle = false;
  return (...args: Parameters<T>) => {
    if (!inThrottle) {
      fn(...args);
      inThrottle = true;
      setTimeout(() => { inThrottle = false; }, limit);
    }
  };
}

export function clamp(value: number, min: number, max: number): number {
  return Math.min(Math.max(value, min), max);
}

export function createNode(
  type: NodeType,
  position: XYPosition,
  data: Partial<CustomNodeData> = {}
): Node<CustomNodeData> {
  const id = generateUUID();
  const { inputs, outputs, color, label } = getNodeDefaults(type);

  return {
    id,
    type,
    position,
    data: {
      label: data.label || label,
      nodeType: type,
      inputs: data.inputs || inputs,
      outputs: data.outputs || outputs,
      color: data.color || color,
      ...data,
    } as CustomNodeData,
  };
}

function getNodeDefaults(type: NodeType): {
  label: string;
  color: string;
  inputs: NodePort[];
  outputs: NodePort[];
} {
  const defaults: Record<NodeType, { label: string; color: string; inputs: NodePort[]; outputs: NodePort[] }> = {
    priceDataNode: {
      label: '价格数据',
      color: '#1890ff',
      inputs: [],
      outputs: [
        { id: 'open', label: 'Open', type: 'series', required: false, direction: 'output' },
        { id: 'high', label: 'High', type: 'series', required: false, direction: 'output' },
        { id: 'low', label: 'Low', type: 'series', required: false, direction: 'output' },
        { id: 'close', label: 'Close', type: 'series', required: false, direction: 'output' },
        { id: 'volume', label: 'Volume', type: 'series', required: false, direction: 'output' },
      ],
    },
    indicatorNode: {
      label: '技术指标',
      color: '#722ed1',
      inputs: [
        { id: 'input', label: 'Input', type: 'series', required: false, direction: 'input' },
      ],
      outputs: [
        { id: 'value', label: 'Value', type: 'series', required: false, direction: 'output' },
      ],
    },
    comparatorNode: {
      label: '比较器',
      color: '#13c2c2',
      inputs: [
        { id: 'left', label: 'A', type: 'series', required: true, direction: 'input' },
        { id: 'right', label: 'B', type: 'series', required: true, direction: 'input' },
      ],
      outputs: [
        { id: 'result', label: 'Result', type: 'boolean', required: false, direction: 'output' },
      ],
    },
    logicalNode: {
      label: '逻辑运算',
      color: '#eb2f96',
      inputs: [
        { id: 'a', label: 'A', type: 'boolean', required: true, direction: 'input' },
        { id: 'b', label: 'B', type: 'boolean', required: false, direction: 'input' },
      ],
      outputs: [
        { id: 'result', label: 'Result', type: 'boolean', required: false, direction: 'output' },
      ],
    },
    mathNode: {
      label: '数学运算',
      color: '#fa8c16',
      inputs: [
        { id: 'a', label: 'A', type: 'number', required: true, direction: 'input' },
        { id: 'b', label: 'B', type: 'number', required: true, direction: 'input' },
      ],
      outputs: [
        { id: 'result', label: 'Result', type: 'number', required: false, direction: 'output' },
      ],
    },
    entryRuleNode: {
      label: '入场规则',
      color: '#52c41a',
      inputs: [
        { id: 'condition', label: 'Condition', type: 'boolean', required: true, direction: 'input' },
      ],
      outputs: [
        { id: 'signal', label: 'Buy Signal', type: 'trade', required: false, direction: 'output' },
      ],
    },
    exitRuleNode: {
      label: '出场规则',
      color: '#f5222d',
      inputs: [
        { id: 'condition', label: 'Condition', type: 'boolean', required: true, direction: 'input' },
      ],
      outputs: [
        { id: 'signal', label: 'Sell Signal', type: 'trade', required: false, direction: 'output' },
      ],
    },
    stopLossNode: {
      label: '止损',
      color: '#ff4d4f',
      inputs: [
        { id: 'signal', label: 'Signal', type: 'trade', required: true, direction: 'input' },
      ],
      outputs: [
        { id: 'adjusted', label: 'Adjusted', type: 'trade', required: false, direction: 'output' },
      ],
    },
    takeProfitNode: {
      label: '止盈',
      color: '#faad14',
      inputs: [
        { id: 'signal', label: 'Signal', type: 'trade', required: true, direction: 'input' },
      ],
      outputs: [
        { id: 'adjusted', label: 'Adjusted', type: 'trade', required: false, direction: 'output' },
      ],
    },
    positionSizeNode: {
      label: '仓位管理',
      color: '#2f54eb',
      inputs: [
        { id: 'signal', label: 'Signal', type: 'trade', required: true, direction: 'input' },
      ],
      outputs: [
        { id: 'sized', label: 'Sized', type: 'trade', required: false, direction: 'output' },
      ],
    },
    filterNode: {
      label: '过滤器',
      color: '#a0d911',
      inputs: [
        { id: 'condition', label: 'Condition', type: 'boolean', required: true, direction: 'input' },
        { id: 'signal', label: 'Signal', type: 'trade', required: true, direction: 'input' },
      ],
      outputs: [
        { id: 'filtered', label: 'Filtered', type: 'trade', required: false, direction: 'output' },
      ],
    },
    orderNode: {
      label: '订单',
      color: '#cf1322',
      inputs: [
        { id: 'signal', label: 'Signal', type: 'trade', required: true, direction: 'input' },
      ],
      outputs: [
        { id: 'order', label: 'Order', type: 'trade', required: false, direction: 'output' },
      ],
    },
    variableNode: {
      label: '变量',
      color: '#614700',
      inputs: [],
      outputs: [
        { id: 'value', label: 'Value', type: 'any', required: false, direction: 'output' },
      ],
    },
    conditionalNode: {
      label: '条件',
      color: '#391085',
      inputs: [
        { id: 'condition', label: 'Condition', type: 'boolean', required: true, direction: 'input' },
        { id: 'true', label: 'True', type: 'any', required: true, direction: 'input' },
        { id: 'false', label: 'False', type: 'any', required: true, direction: 'input' },
      ],
      outputs: [
        { id: 'result', label: 'Result', type: 'any', required: false, direction: 'output' },
      ],
    },
    signalNode: {
      label: '信号',
      color: '#006d75',
      inputs: [
        { id: 'input', label: 'Input', type: 'any', required: true, direction: 'input' },
      ],
      outputs: [
        { id: 'output', label: 'Output', type: 'trade', required: false, direction: 'output' },
      ],
    },
    subchartNode: {
      label: '子图表',
      color: '#10239e',
      inputs: [],
      outputs: [],
    },
    customFunctionNode: {
      label: '自定义函数',
      color: '#22075e',
      inputs: [
        { id: 'input', label: 'Input', type: 'any', required: false, direction: 'input' },
      ],
      outputs: [
        { id: 'output', label: 'Output', type: 'any', required: false, direction: 'output' },
      ],
    },
  };

  return defaults[type] || { label: 'Unknown', color: '#999999', inputs: [], outputs: [] };
}

export function isValidConnection(
  sourceType: string,
  targetType: string
): boolean {
  if (sourceType === 'any' || targetType === 'any') return true;
  if (sourceType === targetType) return true;
  if (sourceType === 'series' && targetType === 'number') return true;
  if (sourceType === 'number' && targetType === 'series') return true;
  return false;
}

export function validateStrategy(nodes: Node[], edges: Edge[]): string[] {
  const errors: string[] = [];

  // Check for isolated nodes
  const connectedNodeIds = new Set<string>();
  edges.forEach((e) => {
    connectedNodeIds.add(e.source);
    connectedNodeIds.add(e.target);
  });

  nodes.forEach((node) => {
    if (!connectedNodeIds.has(node.id) && node.type !== 'priceDataNode') {
      errors.push(`节点 "${node.data?.label || node.id}" 未连接`);
    }
  });

  // Check for cycles
  const adjacency: Record<string, string[]> = {};
  edges.forEach((e) => {
    if (!adjacency[e.source]) adjacency[e.source] = [];
    adjacency[e.source].push(e.target);
  });

  const visited = new Set<string>();
  const recStack = new Set<string>();

  function hasCycle(nodeId: string): boolean {
    visited.add(nodeId);
    recStack.add(nodeId);
    const neighbors = adjacency[nodeId] || [];
    for (const neighbor of neighbors) {
      if (!visited.has(neighbor) && hasCycle(neighbor)) return true;
      if (recStack.has(neighbor)) return true;
    }
    recStack.delete(nodeId);
    return false;
  }

  nodes.forEach((node) => {
    if (!visited.has(node.id)) {
      if (hasCycle(node.id)) {
        errors.push('检测到策略中存在循环依赖');
      }
    }
  });

  return errors;
}

export function generateStrategyText(nodes: Node[], edges: Edge[]): string {
  if (nodes.length === 0) return '策略为空';

  const entryRule = nodes.find((n) => n.type === 'entryRuleNode');
  if (!entryRule) return '未配置入场规则';

  const conditionEdges = edges.filter((e) => e.target === entryRule.id && e.targetHandle === 'condition');
  if (conditionEdges.length === 0) return '入场规则未连接条件';

  const conditionSource = conditionEdges[0].source;
  const conditionNode = nodes.find((n) => n.id === conditionSource);

  if (!conditionNode) return '条件节点未找到';

  let conditionText = '';
  if (conditionNode.type === 'comparatorNode') {
    const op = (conditionNode.data?.operator as string) || '>';
    const leftEdges = edges.filter((e) => e.target === conditionNode.id && e.targetHandle === 'left');
    const rightEdges = edges.filter((e) => e.target === conditionNode.id && e.targetHandle === 'right');
    const leftNode = leftEdges.length > 0 ? nodes.find((n) => n.id === leftEdges[0].source) : null;
    const rightNode = rightEdges.length > 0 ? nodes.find((n) => n.id === rightEdges[0].source) : null;
    const leftName = leftNode?.data?.label || '?';
    const rightName = rightNode?.data?.label || '?';
    conditionText = `${leftName} ${op} ${rightName}`;
  } else if (conditionNode.type === 'logicalNode') {
    const op = (conditionNode.data?.operator as string) || 'AND';
    conditionText = `逻辑 ${op}`;
  } else {
    conditionText = conditionNode.data?.label || '?';
  }

  return `IF ${conditionText} THEN BUY ELSE HOLD`;
}

export function convertToStrategyIR(nodes: Node[], edges: Edge[]): {
  nodes: Array<{ id: string; type: string; position: { x: number; y: number }; data: Record<string, unknown> }>;
  edges: Array<{ id: string; source: string; sourceHandle: string; target: string; targetHandle: string }>;
} {
  return {
    nodes: nodes.map((n) => ({
      id: n.id,
      type: n.type || 'default',
      position: { x: n.position.x, y: n.position.y },
      data: deepClone(n.data || {}),
    })),
    edges: edges.map((e) => ({
      id: e.id,
      source: e.source,
      sourceHandle: e.sourceHandle || 'output',
      target: e.target,
      targetHandle: e.targetHandle || 'input',
    })),
  };
}

export function convertFromStrategyIR(
  irNodes: Array<{ id: string; type: string; position: { x: number; y: number }; data: Record<string, unknown> }>,
  irEdges: Array<{ id: string; source: string; sourceHandle: string; target: string; targetHandle: string }>
): { nodes: Node<CustomNodeData>[]; edges: Edge[] } {
  const nodes: Node<CustomNodeData>[] = irNodes.map((n) => ({
    id: n.id,
    type: n.type as NodeType,
    position: n.position,
    data: { ...n.data } as CustomNodeData,
  }));

  const edges: Edge[] = irEdges.map((e) => ({
    id: e.id,
    source: e.source,
    sourceHandle: e.sourceHandle,
    target: e.target,
    targetHandle: e.targetHandle,
  }));

  return { nodes, edges };
}
