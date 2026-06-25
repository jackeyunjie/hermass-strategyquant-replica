import React, { useState, useCallback, useRef, useMemo, useEffect } from 'react';
import ReactFlow, {
  ReactFlowProvider,
  Background,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
  addEdge,
  type Connection,
  type Edge,
  type Node,
  type ReactFlowInstance,
  Panel,
  type XYPosition,
  useReactFlow,
} from 'reactflow';
import 'reactflow/dist/style.css';
import {
  Button,
  Tooltip,
  Space,
  message,
  Typography,
  Divider,
  Modal,
  Input,
  Form,
} from 'antd';
import {
  SaveOutlined,
  FolderOpenOutlined,
  DeleteOutlined,
  LayoutOutlined,
  CodeOutlined,
  PlayCircleOutlined,
  CheckCircleOutlined,
  ClearOutlined,
  RedoOutlined,
  UndoOutlined,
} from '@ant-design/icons';
import type { CustomNodeData, NodeType, StrategyIR } from '../../types';
import { useStrategy } from '../../hooks/useStrategy';
import { useAppStore } from '../../stores/appStore';
import {
  generateUUID,
  createNode,
  isValidConnection,
  validateStrategy,
  generateStrategyText,
  convertToStrategyIR,
  convertFromStrategyIR,
  deepClone,
} from '../../utils/helpers';
import NodePalette from './NodePalette';
import PropertyPanel from './PropertyPanel';
import PriceDataNode from './nodeTypes/PriceDataNode';
import IndicatorNode from './nodeTypes/IndicatorNode';
import ComparatorNode from './nodeTypes/ComparatorNode';
import LogicalNode from './nodeTypes/LogicalNode';
import MathNode from './nodeTypes/MathNode';
import EntryRuleNode from './nodeTypes/EntryRuleNode';
import ExitRuleNode from './nodeTypes/ExitRuleNode';
import StopLossNode from './nodeTypes/StopLossNode';
import TakeProfitNode from './nodeTypes/TakeProfitNode';
import PositionSizeNode from './nodeTypes/PositionSizeNode';
import CustomFunctionNode from './nodeTypes/CustomFunctionNode';

const { Text } = Typography;

const nodeTypes = {
  priceDataNode: PriceDataNode,
  indicatorNode: IndicatorNode,
  comparatorNode: ComparatorNode,
  logicalNode: LogicalNode,
  mathNode: MathNode,
  entryRuleNode: EntryRuleNode,
  exitRuleNode: ExitRuleNode,
  stopLossNode: StopLossNode,
  takeProfitNode: TakeProfitNode,
  positionSizeNode: PositionSizeNode,
  customFunctionNode: CustomFunctionNode,
};

function StrategyEditorInner() {
  const reactFlowWrapper = useRef<HTMLDivElement>(null);
  const [nodes, setNodes, onNodesChange] = useNodesState<CustomNodeData>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);
  const [selectedNode, setSelectedNode] = useState<Node<CustomNodeData> | null>(null);
  const [strategyName, setStrategyName] = useState('未命名策略');
  const [strategyDescription, setStrategyDescription] = useState('');
  const [strategyText, setStrategyText] = useState('策略为空');
  const [validationErrors, setValidationErrors] = useState<string[]>([]);
  const [history, setHistory] = useState<Array<{ nodes: Node<CustomNodeData>[]; edges: Edge[] }>>([]);
  const [historyIndex, setHistoryIndex] = useState(-1);
  const [saveModalVisible, setSaveModalVisible] = useState(false);
  const [codeModalVisible, setCodeModalVisible] = useState(false);
  const [generatedCode, setGeneratedCode] = useState('');

  const reactFlowInstance = useReactFlow();
  const { saveStrategy } = useStrategy();
  const currentStrategy = useAppStore((s) => s.currentStrategy);
  const setCurrentStrategy = useAppStore((s) => s.setCurrentStrategy);

  // Load from store if exists
  useEffect(() => {
    if (currentStrategy && currentStrategy.nodes && currentStrategy.nodes.length > 0) {
      const { nodes: loadedNodes, edges: loadedEdges } = convertFromStrategyIR(
        currentStrategy.nodes,
        currentStrategy.edges
      );
      setNodes(loadedNodes);
      setEdges(loadedEdges);
      setStrategyName(currentStrategy.name || '未命名策略');
      setStrategyDescription(currentStrategy.description || '');
    }
  }, [currentStrategy, setNodes, setEdges]);

  // Update strategy text when nodes/edges change
  useEffect(() => {
    const text = generateStrategyText(nodes, edges);
    setStrategyText(text);
  }, [nodes, edges]);

  const pushHistory = useCallback(() => {
    const newHistory = history.slice(0, historyIndex + 1);
    newHistory.push({ nodes: deepClone(nodes), edges: deepClone(edges) });
    if (newHistory.length > 50) newHistory.shift();
    setHistory(newHistory);
    setHistoryIndex(newHistory.length - 1);
  }, [history, historyIndex, nodes, edges]);

  const onConnect = useCallback(
    (params: Connection) => {
      // Check type compatibility
      const sourceNode = nodes.find((n) => n.id === params.source);
      const targetNode = nodes.find((n) => n.id === params.target);
      if (!sourceNode || !targetNode) return;

      const sourcePort = (sourceNode.data.outputs as Array<{ id: string; type: string }>)?.find(
        (p) => p.id === params.sourceHandle
      );
      const targetPort = (targetNode.data.inputs as Array<{ id: string; type: string }>)?.find(
        (p) => p.id === params.targetHandle
      );

      if (sourcePort && targetPort && !isValidConnection(sourcePort.type, targetPort.type)) {
        message.warning('端口类型不兼容，无法连接');
        return;
      }

      setEdges((eds) => addEdge(params, eds));
      pushHistory();
    },
    [nodes, setEdges, pushHistory]
  );

  const onNodeClick = useCallback((_: React.MouseEvent, node: Node<CustomNodeData>) => {
    setSelectedNode(node);
  }, []);

  const onPaneClick = useCallback(() => {
    setSelectedNode(null);
  }, []);

  const onDrop = useCallback(
    (event: React.DragEvent) => {
      event.preventDefault();
      const type = event.dataTransfer.getData('application/reactflow') as NodeType;
      if (!type) return;

      const bounds = reactFlowWrapper.current?.getBoundingClientRect();
      if (!bounds || !reactFlowInstance) return;

      const position = reactFlowInstance.project({
        x: event.clientX - bounds.left,
        y: event.clientY - bounds.top,
      });

      const newNode = createNode(type, position);
      setNodes((nds) => nds.concat(newNode as Node<CustomNodeData>));
      pushHistory();
    },
    [reactFlowInstance, setNodes, pushHistory]
  );

  const onDragOver = useCallback((event: React.DragEvent) => {
    event.preventDefault();
    event.dataTransfer.dropEffect = 'move';
  }, []);

  const handleUpdateNode = useCallback(
    (nodeId: string, data: Partial<CustomNodeData>) => {
      setNodes((nds) =>
        nds.map((n) => {
          if (n.id === nodeId) {
            return { ...n, data: { ...n.data, ...data } };
          }
          return n;
        })
      );
    },
    [setNodes]
  );

  const handleUpdateStrategy = useCallback((name: string, description: string) => {
    setStrategyName(name);
    setStrategyDescription(description);
  }, []);

  const handleDeleteNode = useCallback(() => {
    if (!selectedNode) return;
    setNodes((nds) => nds.filter((n) => n.id !== selectedNode.id));
    setEdges((eds) => eds.filter((e) => e.source !== selectedNode.id && e.target !== selectedNode.id));
    setSelectedNode(null);
    pushHistory();
    message.success('节点已删除');
  }, [selectedNode, setNodes, setEdges, pushHistory]);

  const handleDuplicateNode = useCallback(() => {
    if (!selectedNode) return;
    const newNode = {
      ...selectedNode,
      id: generateUUID(),
      position: { x: selectedNode.position.x + 50, y: selectedNode.position.y + 50 },
    };
    setNodes((nds) => nds.concat(newNode));
    pushHistory();
  }, [selectedNode, setNodes, pushHistory]);

  const handleClear = useCallback(() => {
    Modal.confirm({
      title: '确认清空画布？',
      content: '所有节点和连接将被删除，此操作不可撤销。',
      onOk: () => {
        setNodes([]);
        setEdges([]);
        setSelectedNode(null);
        pushHistory();
      },
    });
  }, [setNodes, setEdges, pushHistory]);

  const handleAutoLayout = useCallback(() => {
    // Simple layout: arrange nodes by type in columns
    const typeColumns: Record<string, number> = {
      priceDataNode: 0,
      indicatorNode: 1,
      comparatorNode: 2,
      logicalNode: 2,
      mathNode: 2,
      entryRuleNode: 3,
      exitRuleNode: 3,
      stopLossNode: 4,
      takeProfitNode: 4,
      positionSizeNode: 4,
    };
    const columnWidth = 240;
    const rowHeight = 100;
    const columnCounts: Record<number, number> = {};

    const newNodes = nodes.map((node) => {
      const col = typeColumns[node.type || ''] || 0;
      const row = columnCounts[col] || 0;
      columnCounts[col] = row + 1;
      return {
        ...node,
        position: { x: col * columnWidth + 20, y: row * rowHeight + 20 },
      };
    });
    setNodes(newNodes);
    pushHistory();
  }, [nodes, setNodes, pushHistory]);

  const handleValidate = useCallback(() => {
    const errors = validateStrategy(nodes, edges);
    setValidationErrors(errors);
    if (errors.length === 0) {
      message.success('策略验证通过，未发现错误');
    } else {
      message.error(`发现 ${errors.length} 个错误`);
    }
  }, [nodes, edges]);

  const handleSave = useCallback(async () => {
    const { nodes: irNodes, edges: irEdges } = convertToStrategyIR(nodes, edges);
    const ir: StrategyIR = {
      id: currentStrategy?.id || generateUUID(),
      name: strategyName,
      description: strategyDescription,
      version: 1,
      metadata: {
        author: 'user',
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      },
      settings: {
        main_symbol: '000001.SZ',
        main_timeframe: '1d',
        market_type: 'stock',
      },
      nodes: irNodes,
      edges: irEdges,
      variables: [],
    };
    setCurrentStrategy(ir);
    setSaveModalVisible(true);
  }, [nodes, edges, strategyName, strategyDescription, currentStrategy, setCurrentStrategy]);

  const handleConfirmSave = useCallback(async () => {
    if (!currentStrategy) return;
    const success = await saveStrategy(currentStrategy);
    if (success) {
      setSaveModalVisible(false);
    }
  }, [currentStrategy, saveStrategy]);

  const handleGenerateCode = useCallback(() => {
    const code = `# Hermass Strategy Generated Code
# Strategy: ${strategyName}
# Description: ${strategyDescription}

${strategyText}

# TODO: Implement strategy logic in Python
`;
    setGeneratedCode(code);
    setCodeModalVisible(true);
  }, [strategyName, strategyDescription, strategyText]);

  const handleUndo = useCallback(() => {
    if (historyIndex > 0) {
      const idx = historyIndex - 1;
      setHistoryIndex(idx);
      setNodes(deepClone(history[idx].nodes));
      setEdges(deepClone(history[idx].edges));
    }
  }, [history, historyIndex, setNodes, setEdges]);

  const handleRedo = useCallback(() => {
    if (historyIndex < history.length - 1) {
      const idx = historyIndex + 1;
      setHistoryIndex(idx);
      setNodes(deepClone(history[idx].nodes));
      setEdges(deepClone(history[idx].edges));
    }
  }, [history, historyIndex, setNodes, setEdges]);

  // Context menu
  const onNodeContextMenu = useCallback(
    (event: React.MouseEvent, node: Node<CustomNodeData>) => {
      event.preventDefault();
      setSelectedNode(node);
    },
    []
  );

  const contextMenuItems = useMemo(() => {
    if (!selectedNode) return [];
    return [
      { key: 'delete', label: '删除节点', icon: <DeleteOutlined />, onClick: handleDeleteNode },
      { key: 'duplicate', label: '复制节点', icon: <RedoOutlined />, onClick: handleDuplicateNode },
    ];
  }, [selectedNode, handleDeleteNode, handleDuplicateNode]);

  return (
    <div
      style={{ display: 'flex', height: '100%', width: '100%' }}
      onDrop={onDrop}
      onDragOver={onDragOver}
    >
      <NodePalette />

      <div ref={reactFlowWrapper} style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
        {/* Toolbar */}
        <div
          style={{
            padding: '8px 16px',
            background: '#fff',
            borderBottom: '1px solid #f0f0f0',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
          }}
        >
          <Space>
            <Tooltip title="撤销 (Ctrl+Z)">
              <Button icon={<UndoOutlined />} size="small" onClick={handleUndo} disabled={historyIndex <= 0} />
            </Tooltip>
            <Tooltip title="重做 (Ctrl+Y)">
              <Button icon={<RedoOutlined />} size="small" onClick={handleRedo} disabled={historyIndex >= history.length - 1} />
            </Tooltip>
            <Divider type="vertical" />
            <Tooltip title="保存策略">
              <Button icon={<SaveOutlined />} size="small" onClick={handleSave} />
            </Tooltip>
            <Tooltip title="加载策略">
              <Button icon={<FolderOpenOutlined />} size="small" />
            </Tooltip>
            <Tooltip title="清空画布">
              <Button icon={<ClearOutlined />} size="small" danger onClick={handleClear} />
            </Tooltip>
            <Tooltip title="自动布局">
              <Button icon={<LayoutOutlined />} size="small" onClick={handleAutoLayout} />
            </Tooltip>
            <Tooltip title="生成代码">
              <Button icon={<CodeOutlined />} size="small" onClick={handleGenerateCode} />
            </Tooltip>
            <Tooltip title="回测">
              <Button icon={<PlayCircleOutlined />} size="small" type="primary" onClick={handleValidate} />
            </Tooltip>
            <Tooltip title="校验">
              <Button icon={<CheckCircleOutlined />} size="small" onClick={handleValidate} />
            </Tooltip>
          </Space>

          <div style={{ fontSize: 12 }}>
            <Text type="secondary">策略: </Text>
            <Text strong>{strategyName}</Text>
          </div>
        </div>

        {/* ReactFlow Canvas */}
        <div style={{ flex: 1, position: 'relative' }}>
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onConnect={onConnect}
            onNodeClick={onNodeClick}
            onPaneClick={onPaneClick}
            onNodeContextMenu={onNodeContextMenu}
            nodeTypes={nodeTypes}
            fitView
            attributionPosition="bottom-left"
            deleteKeyCode={['Delete', 'Backspace']}
            multiSelectionKeyCode={['Control', 'Meta']}
          >
            <Background gap={12} size={1} color="#f0f0f0" />
            <Controls />
            <MiniMap
              nodeStrokeWidth={3}
              zoomable
              pannable
              style={{ backgroundColor: '#fff', border: '1px solid #f0f0f0' }}
            />
            <Panel position="top-left" style={{ width: 300, background: '#fff', padding: 12, borderRadius: 8, boxShadow: '0 2px 8px rgba(0,0,0,0.1)' }}>
              <Text strong style={{ fontSize: 13, display: 'block', marginBottom: 4 }}>策略逻辑</Text>
              <Text code style={{ fontSize: 12, color: '#666', display: 'block', whiteSpace: 'pre-wrap' }}>
                {strategyText}
              </Text>
              {validationErrors.length > 0 && (
                <div style={{ marginTop: 8 }}>
                  {validationErrors.map((err, i) => (
                    <Text key={i} type="danger" style={{ fontSize: 11, display: 'block' }}>
                      • {err}
                    </Text>
                  ))}
                </div>
              )}
            </Panel>
          </ReactFlow>
        </div>
      </div>

      <PropertyPanel
        selectedNode={selectedNode}
        strategyName={strategyName}
        strategyDescription={strategyDescription}
        onUpdateNode={handleUpdateNode}
        onUpdateStrategy={handleUpdateStrategy}
      />

      <Modal
        title="保存策略"
        open={saveModalVisible}
        onOk={handleConfirmSave}
        onCancel={() => setSaveModalVisible(false)}
      >
        <Form layout="vertical">
          <Form.Item label="策略名称">
            <Input value={strategyName} onChange={(e) => setStrategyName(e.target.value)} />
          </Form.Item>
          <Form.Item label="策略描述">
            <Input.TextArea value={strategyDescription} onChange={(e) => setStrategyDescription(e.target.value)} rows={3} />
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title="生成代码"
        open={codeModalVisible}
        onOk={() => setCodeModalVisible(false)}
        onCancel={() => setCodeModalVisible(false)}
        width={800}
      >
        <pre style={{ background: '#f6f8fa', padding: 16, borderRadius: 4, overflow: 'auto', maxHeight: 400 }}>
          <code>{generatedCode}</code>
        </pre>
      </Modal>
    </div>
  );
}

export default function StrategyEditor() {
  return (
    <ReactFlowProvider>
      <StrategyEditorInner />
    </ReactFlowProvider>
  );
}
