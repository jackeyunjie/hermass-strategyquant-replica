import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Button,
  Card,
  Col,
  Form,
  Input,
  List,
  Modal,
  Rate,
  Row,
  Select,
  Space,
  Tag,
  Typography,
  message,
} from 'antd';
import { DownloadOutlined, PlusOutlined, ShopOutlined } from '@ant-design/icons';
import { api } from '../services/api';
import type { MarketplaceIndicator } from '../types';

const { Title, Text, Paragraph } = Typography;

const builtinIndicators: MarketplaceIndicator[] = [
  {
    id: 'capital-pressure-score',
    name: 'CapitalPressureScore',
    display_name: '资金压力评分',
    description: '结合成交额变化和收盘位置衡量主动资金压力。',
    category: '资金',
    formula: 'zscore(pct_change(amount, 1), 20) + (close - low) / (high - low + 0.000001)',
    author: 'Hermass',
    rating: 4.7,
    downloads: 1280,
    tags: ['A股', '资金', '短线'],
    status: 'active',
  },
  {
    id: 'trend-volume-confirm',
    name: 'TrendVolumeConfirm',
    display_name: '趋势放量确认',
    description: '用均线斜率和成交量比率确认趋势突破质量。',
    category: '趋势',
    formula: '(sma(close, 10) - sma(close, 30)) / close + volume / sma(volume, 20)',
    author: 'Hermass',
    rating: 4.5,
    downloads: 970,
    tags: ['趋势', '成交量'],
    status: 'active',
  },
  {
    id: 'range-squeeze',
    name: 'RangeSqueeze',
    display_name: '波动收缩',
    description: '识别振幅和成交量同时收缩后的潜在突破环境。',
    category: '波动率',
    formula: 'std(close, 20) / sma(close, 20) + sma(high - low, 10) / close',
    author: 'Hermass',
    rating: 4.3,
    downloads: 812,
    tags: ['突破', '波动率'],
    status: 'active',
  },
];

export default function IndicatorMarketplacePage() {
  const [items, setItems] = useState<MarketplaceIndicator[]>(builtinIndicators);
  const [search, setSearch] = useState('');
  const [category, setCategory] = useState<string | undefined>();
  const [loading, setLoading] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [form] = Form.useForm();

  const categories = useMemo(() => Array.from(new Set(items.map((item) => item.category))), [items]);
  const filteredItems = useMemo(() => {
    const text = search.trim().toLowerCase();
    return items.filter((item) => {
      const categoryOk = !category || item.category === category;
      const searchOk = !text
        || item.name.toLowerCase().includes(text)
        || item.display_name.toLowerCase().includes(text)
        || item.description.toLowerCase().includes(text)
        || item.tags.some((tag) => tag.toLowerCase().includes(text));
      return categoryOk && searchOk;
    });
  }, [category, items, search]);

  const loadItems = useCallback(async () => {
    setLoading(true);
    try {
      const response = await api.getMarketplaceIndicators({ category, search });
      setItems(response.items || builtinIndicators);
    } catch {
      setItems((current) => current.length ? current : builtinIndicators);
    } finally {
      setLoading(false);
    }
  }, [category, search]);

  useEffect(() => {
    loadItems();
  }, [loadItems]);

  const install = useCallback(async (item: MarketplaceIndicator) => {
    try {
      await api.installMarketplaceIndicator(item.id);
      message.success(`${item.display_name} 已安装到指标库`);
      setItems((current) => current.map((row) => (
        row.id === item.id ? { ...row, downloads: row.downloads + 1 } : row
      )));
    } catch {
      message.warning('后端不可用，已记录本地安装意图');
      localStorage.setItem(`hermass:indicator:${item.id}`, JSON.stringify(item));
    }
  }, []);

  const createIndicator = useCallback(async () => {
    const values = await form.validateFields();
    const payload = {
      ...values,
      tags: values.tags ? values.tags.split(',').map((tag: string) => tag.trim()).filter(Boolean) : [],
    };
    try {
      const created = await api.createMarketplaceIndicator(payload);
      setItems((current) => [created, ...current]);
      message.success('自定义指标已创建');
    } catch {
      const localItem: MarketplaceIndicator = {
        id: `local-${Date.now()}`,
        author: 'local',
        rating: 0,
        downloads: 0,
        status: 'draft',
        ...payload,
      };
      setItems((current) => [localItem, ...current]);
      message.warning('后端不可用，已创建本地草稿');
    }
    setModalOpen(false);
    form.resetFields();
  }, [form]);

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
        <Title level={3} style={{ margin: 0 }}>自定义指标市场</Title>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => setModalOpen(true)}>
          创建指标
        </Button>
      </div>

      <Card style={{ marginBottom: 16 }}>
        <Row gutter={[12, 12]}>
          <Col xs={24} md={10}>
            <Input.Search placeholder="搜索指标、标签、说明" value={search} onChange={(event) => setSearch(event.target.value)} allowClear />
          </Col>
          <Col xs={24} md={6}>
            <Select
              placeholder="分类"
              value={category}
              onChange={setCategory}
              allowClear
              style={{ width: '100%' }}
              options={categories.map((value) => ({ label: value, value }))}
            />
          </Col>
          <Col xs={24} md={4}>
            <Button icon={<ShopOutlined />} loading={loading} onClick={loadItems}>
              刷新
            </Button>
          </Col>
        </Row>
      </Card>

      <Row gutter={[16, 16]}>
        {filteredItems.map((item) => (
          <Col xs={24} lg={12} xl={8} key={item.id}>
            <Card
              title={
                <Space>
                  <Text strong>{item.display_name}</Text>
                  <Tag>{item.category}</Tag>
                </Space>
              }
              extra={<Button type="text" icon={<DownloadOutlined />} onClick={() => install(item)} />}
              style={{ minHeight: 300 }}
            >
              <Space direction="vertical" size={10} style={{ width: '100%' }}>
                <Text type="secondary">{item.name}</Text>
                <Paragraph style={{ minHeight: 44 }}>{item.description}</Paragraph>
                <div style={{ background: '#fafafa', border: '1px solid #f0f0f0', borderRadius: 6, padding: 10 }}>
                  <Text code style={{ whiteSpace: 'pre-wrap' }}>{item.formula}</Text>
                </div>
                <Space wrap>
                  {item.tags.map((tag) => <Tag key={tag}>{tag}</Tag>)}
                </Space>
                <Space split={<span style={{ color: '#d9d9d9' }}>|</span>}>
                  <Rate disabled allowHalf value={item.rating} style={{ fontSize: 14 }} />
                  <Text type="secondary">{item.downloads} installs</Text>
                  <Text type="secondary">{item.author}</Text>
                </Space>
              </Space>
            </Card>
          </Col>
        ))}
      </Row>

      <Modal
        title="创建公式指标"
        open={modalOpen}
        onCancel={() => setModalOpen(false)}
        onOk={createIndicator}
        okText="创建"
        width={720}
      >
        <Form form={form} layout="vertical">
          <Row gutter={12}>
            <Col span={12}>
              <Form.Item name="display_name" label="显示名称" rules={[{ required: true }]}>
                <Input placeholder="例如：量价背离评分" />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="name" label="英文标识" rules={[{ required: true }]}>
                <Input placeholder="VolumeDivergenceScore" />
              </Form.Item>
            </Col>
          </Row>
          <Form.Item name="description" label="说明" rules={[{ required: true }]}>
            <Input.TextArea rows={2} />
          </Form.Item>
          <Row gutter={12}>
            <Col span={12}>
              <Form.Item name="category" label="分类" rules={[{ required: true }]}>
                <Input placeholder="资金 / 趋势 / 波动率" />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="tags" label="标签">
                <Input placeholder="逗号分隔，例如 A股,短线,成交量" />
              </Form.Item>
            </Col>
          </Row>
          <Form.Item name="formula" label="公式" rules={[{ required: true }]}>
            <Input.TextArea
              rows={4}
              placeholder="支持 sma, ema, std, zscore, pct_change, shift 等函数"
              style={{ fontFamily: 'Menlo, Monaco, Consolas, monospace' }}
            />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
