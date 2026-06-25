import React, { useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Card,
  Form,
  Input,
  Button,
  Checkbox,
  Typography,
  Space,
  Divider,
  Row,
  Col,
  message,
} from 'antd';
import {
  UserOutlined,
  LockOutlined,
  EyeOutlined,
  EyeInvisibleOutlined,
} from '@ant-design/icons';
import { useAuth } from '../hooks/useAuth.ts';
import { validateEmail, getEmailError } from '../utils/validators.ts';

const { Title, Text, Link } = Typography;

export default function LoginPage() {
  const navigate = useNavigate();
  const { login, isLoading } = useAuth();
  const [showPassword, setShowPassword] = useState(false);

  const handleSubmit = useCallback(
    async (values: { email: string; password: string; remember: boolean }) => {
      const emailErr = getEmailError(values.email);
      if (emailErr) {
        message.error(emailErr);
        return;
      }
      if (!values.password) {
        message.error('请输入密码');
        return;
      }

      const success = await login(values.email, values.password);
      if (success) {
        if (values.remember) {
          localStorage.setItem('remember_email', values.email);
        } else {
          localStorage.removeItem('remember_email');
        }
        navigate('/');
      }
    },
    [login, navigate]
  );

  return (
    <div
      style={{
        minHeight: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        background: '#f0f2f5',
        padding: 24,
      }}
    >
      <Card
        style={{ width: 900, maxWidth: '100%', borderRadius: 8, overflow: 'hidden' }}
        bodyStyle={{ padding: 0 }}
      >
        <Row>
          <Col
            xs={0}
            sm={0}
            md={12}
            style={{
              background: '#001529',
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              padding: 48,
              minHeight: 500,
            }}
          >
            <Title level={2} style={{ color: '#fff', marginBottom: 16 }}>
              Hermass
            </Title>
            <Text style={{ color: 'rgba(255,255,255,0.65)', textAlign: 'center' }}>
              智能量化策略平台
              <br />
              多周期共振 · 收缩突破
            </Text>
          </Col>

          <Col xs={24} sm={24} md={12} style={{ padding: '48px 32px' }}>
            <Title level={3} style={{ marginBottom: 32 }}>
              欢迎登录
            </Title>

            <Form
              name="login"
              layout="vertical"
              onFinish={handleSubmit}
              autoComplete="off"
            >
              <Form.Item
                name="email"
                rules={[
                  { required: true, message: '请输入邮箱' },
                  { validator: (_, value) => {
                    if (!value || validateEmail(value)) return Promise.resolve();
                    return Promise.reject(new Error('请输入有效的邮箱地址'));
                  } },
                ]}
              >
                <Input
                  prefix={<UserOutlined />}
                  placeholder="邮箱地址"
                  size="large"
                />
              </Form.Item>

              <Form.Item
                name="password"
                rules={[{ required: true, message: '请输入密码' }]}
              >
                <Input.Password
                  prefix={<LockOutlined />}
                  placeholder="密码"
                  size="large"
                  iconRender={(visible) =>
                    visible ? <EyeOutlined /> : <EyeInvisibleOutlined />
                  }
                  visibilityToggle={{ visible: showPassword, onVisibleChange: setShowPassword }}
                />
              </Form.Item>

              <Form.Item>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <Form.Item name="remember" valuePropName="checked" noStyle>
                    <Checkbox>记住我</Checkbox>
                  </Form.Item>
                  <Link>忘记密码？</Link>
                </div>
              </Form.Item>

              <Form.Item>
                <Button
                  type="primary"
                  htmlType="submit"
                  size="large"
                  block
                  loading={isLoading}
                >
                  登录
                </Button>
              </Form.Item>
            </Form>

            <Divider plain>或</Divider>

            <div style={{ textAlign: 'center' }}>
              <Text>没有账号？ </Text>
              <Link onClick={() => navigate('/register')}>立即注册</Link>
            </div>
          </Col>
        </Row>
      </Card>
    </div>
  );
}
