import React, { useState, useCallback, useEffect } from 'react';
import {
  Card,
  Tabs,
  Form,
  Input,
  Select,
  Switch,
  Button,
  Row,
  Col,
  Slider,
  InputNumber,
  Typography,
  Divider,
  message,
  Space,
} from 'antd';
import {
  GlobalOutlined,
  UserOutlined,
  DatabaseOutlined,
  SettingOutlined,
  SaveOutlined,
} from '@ant-design/icons';
import type { Settings as SettingsType } from '../types';

const { Title, Text } = Typography;
const { TabPane } = Tabs;
const { Option } = Select;

export default function SettingsPage() {
  const [generalForm] = Form.useForm();
  const [accountForm] = Form.useForm();
  const [dataSourceForm] = Form.useForm();
  const [engineForm] = Form.useForm();
  const [settings, setSettings] = useState<SettingsType>({
    general: { language: 'zh-CN', theme: 'light' },
    account: { email: 'user@hermass.com' },
    dataSource: { tushare_token: '' },
    engine: { population_size: 100, generations: 50, crossover_rate: 0.8, mutation_rate: 0.1 },
  });

  useEffect(() => {
    const stored = localStorage.getItem('settings');
    if (stored) {
      try {
        const parsed = JSON.parse(stored) as SettingsType;
        setSettings(parsed);
        generalForm.setFieldsValue(parsed.general);
        accountForm.setFieldsValue(parsed.account);
        dataSourceForm.setFieldsValue(parsed.dataSource);
        engineForm.setFieldsValue(parsed.engine);
      } catch {
        // ignore
      }
    }
  }, [generalForm, accountForm, dataSourceForm, engineForm]);

  const saveSettings = useCallback(() => {
    const general = generalForm.getFieldsValue();
    const account = accountForm.getFieldsValue();
    const dataSource = dataSourceForm.getFieldsValue();
    const engine = engineForm.getFieldsValue();
    const newSettings = { general, account, dataSource, engine };
    setSettings(newSettings);
    localStorage.setItem('settings', JSON.stringify(newSettings));
    message.success('设置已保存');
  }, [generalForm, accountForm, dataSourceForm, engineForm]);

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
        <Title level={3} style={{ margin: 0 }}>系统设置</Title>
        <Button type="primary" icon={<SaveOutlined />} onClick={saveSettings}>
          保存设置
        </Button>
      </div>

      <Card>
        <Tabs defaultActiveKey="general" items={[
          {
            key: 'general',
            label: (
              <span>
                <GlobalOutlined /> 通用
              </span>
            ),
            children: (
              <Form form={generalForm} layout="vertical" initialValues={settings.general}>
                <Row gutter={16}>
                  <Col xs={24} md={12}>
                    <Form.Item name="language" label="语言">
                      <Select>
                        <Option value="zh-CN">简体中文</Option>
                        <Option value="en-US">English</Option>
                      </Select>
                    </Form.Item>
                  </Col>
                  <Col xs={24} md={12}>
                    <Form.Item name="theme" label="主题" valuePropName="checked">
                      <div>
                        <Switch
                          checked={generalForm.getFieldValue('theme') === 'dark'}
                          onChange={(checked) => generalForm.setFieldValue('theme', checked ? 'dark' : 'light')}
                          checkedChildren="Dark"
                          unCheckedChildren="Light"
                        />
                      </div>
                    </Form.Item>
                  </Col>
                </Row>
              </Form>
            ),
          },
          {
            key: 'account',
            label: (
              <span>
                <UserOutlined /> 账户
              </span>
            ),
            children: (
              <Form form={accountForm} layout="vertical" initialValues={settings.account}>
                <Row gutter={16}>
                  <Col xs={24} md={12}>
                    <Form.Item name="email" label="邮箱">
                      <Input disabled />
                    </Form.Item>
                  </Col>
                  <Col xs={24} md={12}>
                    <Form.Item label="修改密码">
                      <Button>修改密码</Button>
                    </Form.Item>
                  </Col>
                </Row>
              </Form>
            ),
          },
          {
            key: 'dataSource',
            label: (
              <span>
                <DatabaseOutlined /> 数据源
              </span>
            ),
            children: (
              <Form form={dataSourceForm} layout="vertical" initialValues={settings.dataSource}>
                <Form.Item
                  name="tushare_token"
                  label="Tushare API Token"
                  extra="用于获取A股行情数据"
                >
                  <Input.Password placeholder="输入 Tushare Token" />
                </Form.Item>
                <Button type="primary" onClick={() => message.success('Token 已保存')}>
                  验证并保存
                </Button>
              </Form>
            ),
          },
          {
            key: 'engine',
            label: (
              <span>
                <SettingOutlined /> 引擎
              </span>
            ),
            children: (
              <Form form={engineForm} layout="vertical" initialValues={settings.engine}>
                <Row gutter={16}>
                  <Col xs={24} md={12}>
                    <Form.Item name="population_size" label="种群大小">
                      <Slider min={10} max={1000} step={10} />
                      <InputNumber min={10} max={1000} step={10} style={{ width: '100%' }} />
                    </Form.Item>
                  </Col>
                  <Col xs={24} md={12}>
                    <Form.Item name="generations" label="进化代数">
                      <Slider min={10} max={500} step={10} />
                      <InputNumber min={10} max={500} step={10} style={{ width: '100%' }} />
                    </Form.Item>
                  </Col>
                  <Col xs={24} md={12}>
                    <Form.Item name="crossover_rate" label="交叉率">
                      <Slider min={0} max={1} step={0.01} />
                      <InputNumber min={0} max={1} step={0.01} style={{ width: '100%' }} />
                    </Form.Item>
                  </Col>
                  <Col xs={24} md={12}>
                    <Form.Item name="mutation_rate" label="变异率">
                      <Slider min={0} max={1} step={0.01} />
                      <InputNumber min={0} max={1} step={0.01} style={{ width: '100%' }} />
                    </Form.Item>
                  </Col>
                </Row>
              </Form>
            ),
          },
        ]} />
      </Card>
    </div>
  );
}
