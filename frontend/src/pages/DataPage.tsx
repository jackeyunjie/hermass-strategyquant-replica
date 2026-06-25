import React, { useState, useEffect, useCallback } from 'react';
import {
  Card,
  Form,
  Input,
  DatePicker,
  Select,
  Button,
  Table,
  Tag,
  Typography,
  Row,
  Col,
  Space,
  Popconfirm,
  message,
  Modal,
} from 'antd';
import {
  DownloadOutlined,
  DeleteOutlined,
  EyeOutlined,
  ReloadOutlined,
} from '@ant-design/icons';
import { useData } from '../hooks/useData';
import {
  formatDate,
  formatStatus,
  formatCompactNumber,
} from '../utils/formatters';
import { validateSymbolList } from '../utils/validators';
import { mockDataSources } from '../utils/mockData';
import type { DataSource } from '../types';

const { Title, Text } = Typography;
const { RangePicker } = DatePicker;
const { Option } = Select;
const { TextArea } = Input;

export default function DataPage() {
  const [form] = Form.useForm();
  const { dataSources, isLoading, fetchDataSources, downloadData, deleteData } = useData();
  const [previewVisible, setPreviewVisible] = useState(false);
  const [previewSource, setPreviewSource] = useState<DataSource | null>(null);
  const [previewRows, setPreviewRows] = useState<Record<string, number>[]>([]);
  const [selectedRows, setSelectedRows] = useState<React.Key[]>([]);

  const displayData = useCallback(() => {
    return dataSources.length > 0 ? dataSources : mockDataSources(8);
  }, [dataSources]);

  useEffect(() => {
    fetchDataSources();
  }, [fetchDataSources]);

  const handleDownload = useCallback(async () => {
    const values = form.getFieldsValue();
    const symbols = values.symbols?.trim() || '';
    const err = validateSymbolList(symbols);
    if (err) {
      message.error(err);
      return;
    }
    if (!values.dateRange || values.dateRange.length !== 2) {
      message.error('请选择时间范围');
      return;
    }

    const request = {
      symbols: symbols.split(/[,\s]+/).filter(Boolean),
      start_date: values.dateRange[0].format('YYYY-MM-DD'),
      end_date: values.dateRange[1].format('YYYY-MM-DD'),
      timeframe: values.timeframe || '1d',
    };

    await downloadData(request);
  }, [form, downloadData]);

  const handlePreview = useCallback((source: DataSource) => {
    setPreviewSource(source);
    const rows: Record<string, number>[] = [];
    const base = Math.random() * 100 + 10;
    for (let i = 0; i < 20; i++) {
      const open = base + (Math.random() - 0.5) * 5;
      const close = open + (Math.random() - 0.5) * 3;
      const high = Math.max(open, close) + Math.random() * 2;
      const low = Math.min(open, close) - Math.random() * 2;
      rows.push({
        open: Number(open.toFixed(2)),
        high: Number(high.toFixed(2)),
        low: Number(low.toFixed(2)),
        close: Number(close.toFixed(2)),
        volume: Math.floor(Math.random() * 1000000),
      });
    }
    setPreviewRows(rows);
    setPreviewVisible(true);
  }, []);

  const handleDelete = useCallback(async () => {
    if (selectedRows.length === 0) {
      message.warning('请至少选择一项');
      return;
    }
    for (const id of selectedRows) {
      await deleteData(id as string);
    }
    setSelectedRows([]);
    message.success('删除成功');
  }, [selectedRows, deleteData]);

  const columns = [
    { title: '代码', dataIndex: 'symbol', key: 'symbol' },
    { title: '周期', dataIndex: 'timeframe', key: 'timeframe' },
    { title: '起始日期', dataIndex: 'start_date', key: 'start_date', render: (d: string) => formatDate(d) },
    { title: '结束日期', dataIndex: 'end_date', key: 'end_date', render: (d: string) => formatDate(d) },
    {
      title: '记录数',
      dataIndex: 'record_count',
      key: 'record_count',
      render: (v: number) => formatCompactNumber(v),
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      render: (status: string) => (
        <Tag color={status === 'downloaded' ? 'success' : status === 'pending' ? 'processing' : 'error'}>
          {formatStatus(status)}
        </Tag>
      ),
    },
    {
      title: '操作',
      key: 'action',
      render: (_: unknown, record: DataSource) => (
        <Space size="small">
          <Button type="text" icon={<EyeOutlined />} size="small" onClick={() => handlePreview(record)}>
            预览
          </Button>
          <Popconfirm title="确定删除？" onConfirm={() => deleteData(record.id)}>
            <Button type="text" danger icon={<DeleteOutlined />} size="small" />
          </Popconfirm>
        </Space>
      ),
    },
  ];

  const previewColumns = [
    { title: 'Open', dataIndex: 'open', key: 'open' },
    { title: 'High', dataIndex: 'high', key: 'high' },
    { title: 'Low', dataIndex: 'low', key: 'low' },
    { title: 'Close', dataIndex: 'close', key: 'close' },
    { title: 'Volume', dataIndex: 'volume', key: 'volume' },
  ];

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
        <Title level={3} style={{ margin: 0 }}>数据管理</Title>
        <Space>
          <Button icon={<ReloadOutlined />} onClick={fetchDataSources} loading={isLoading}>
            刷新
          </Button>
          <Button danger icon={<DeleteOutlined />} onClick={handleDelete} disabled={selectedRows.length === 0}>
            删除选中
          </Button>
        </Space>
      </div>

      <Card title="数据下载" style={{ marginBottom: 16 }}>
        <Form form={form} layout="vertical">
          <Row gutter={16}>
            <Col xs={24} md={12}>
              <Form.Item
                name="symbols"
                label="股票代码"
                rules={[{ required: true, message: '请输入股票代码' }]}
                extra="支持批量输入，用逗号或空格分隔"
              >
                <TextArea rows={3} placeholder="例如: 000001.SZ, 600519.SH" />
              </Form.Item>
            </Col>
            <Col xs={24} md={6}>
              <Form.Item name="dateRange" label="时间范围" rules={[{ required: true }]}>
                <RangePicker style={{ width: '100%' }} />
              </Form.Item>
            </Col>
            <Col xs={24} md={6}>
              <Form.Item name="timeframe" label="周期" initialValue="1d">
                <Select>
                  <Option value="1d">日线</Option>
                  <Option value="1h">1小时</Option>
                  <Option value="30m">30分钟</Option>
                  <Option value="15m">15分钟</Option>
                  <Option value="5m">5分钟</Option>
                  <Option value="1m">1分钟</Option>
                </Select>
              </Form.Item>
            </Col>
          </Row>
          <Button type="primary" icon={<DownloadOutlined />} onClick={handleDownload} loading={isLoading}>
            提交下载
          </Button>
        </Form>
      </Card>

      <Card title="已下载数据">
        <Table
          dataSource={displayData()}
          columns={columns}
          rowKey="id"
          loading={isLoading}
          rowSelection={{
            selectedRowKeys: selectedRows,
            onChange: setSelectedRows,
          }}
          pagination={{ pageSize: 10 }}
          size="small"
        />
      </Card>

      <Modal
        title={`数据预览: ${previewSource?.symbol || ''}`}
        open={previewVisible}
        onCancel={() => setPreviewVisible(false)}
        footer={null}
        width={800}
      >
        <Table dataSource={previewRows} columns={previewColumns} size="small" pagination={false} />
      </Modal>
    </div>
  );
}
