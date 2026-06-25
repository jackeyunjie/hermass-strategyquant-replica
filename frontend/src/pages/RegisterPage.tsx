import React, { useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Card,
  Form,
  Input,
  Button,
  Typography,
  Space,
  Divider,
  Row,
  Col,
  message,
  Progress,
} from 'antd';
import {
  UserOutlined,
  LockOutlined,
  EyeOutlined,
  EyeInvisibleOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
} from '@ant-design/icons';
import { useAuth } from '../hooks/useAuth.ts';
import {
  validateEmail,
  getEmailError,
  validatePassword,
  getPasswordMatchError,
} from '../utils/validators.ts';

const { Title, Text, Link } = Typography;

export default function RegisterPage() {
  const navigate = useNavigate();
  const { register, isLoading } = useAuth();
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);
  const [passwordStrength, setPasswordStrength] = useState<'weak' | 'medium' | 'strong' | null>(null);
  const [passwordErrors, setPasswordErrors] = useState<string[]>([]);

  const handlePasswordChange = useCallback((value: string) => {
    const result = validatePassword(value);
    setPasswordStrength(result.strength);
    setPasswordErrors(result.errors);
  }, []);

  const getStrengthColor = () => {
    if (passwordStrength === 'strong') return '#52c41a';
    if (passwordStrength === 'medium') return '#faad14';
    return '#f5222d';
  };

  const getStrengthPercent = () => {
    if (passwordStrength === 'strong') return 100;
    if (passwordStrength === 'medium') return 60;
    return 30;
  };

  const handleSubmit = useCallback(
    async (values: { email: string; password: string; confirmPassword: string }) => {
      const emailErr = getEmailError(values.email);
      if (emailErr) {
        message.error(emailErr);
        return;
      }

      const pwdResult = validatePassword(values.password);
      if (!pwdResult.isValid) {
        message.error(pwdResult.errors[0]);
        return;
      }

      const matchErr = getPasswordMatchError(values.password, values.confirmPassword);
      if (matchErr) {
        message.error(matchErr);
        return;
      }

      const success = await register(values.email, values.password);
      if (success) {
        navigate('/');
      }
    },
    [register, navigate]
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
              开启智能量化之旅
              <br />
              多周期共振 · 收缩突破
            </Text>
          </Col>

          <Col xs={24} sm={24} md={12} style={{ padding: '48px 32px' }}>
            <Title level={3} style={{ marginBottom: 32 }}>
              注册账号
            </Title>

            <Form
              name="register"
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
                  placeholder="密码（至少8位）"
                  size="large"
                  iconRender={(visible) =>
                    visible ? <EyeOutlined /> : <EyeInvisibleOutlined />
                  }
                  visibilityToggle={{ visible: showPassword, onVisibleChange: setShowPassword }}
                  onChange={(e) => handlePasswordChange(e.target.value)}
                />
              </Form.Item>

              {passwordStrength && (
                <div style={{ marginBottom: 16 }}>
                  <Progress
                    percent={getStrengthPercent()}
                    showInfo={false}
                    strokeColor={getStrengthColor()}
                    size="small"
                  />
                  <Space size="small" style={{ marginTop: 4, flexWrap: 'wrap' }}>
                    {passwordErrors.length === 0 ? (
                      <Text type="success" style={{ fontSize: 12 }}>
                        <CheckCircleOutlined /> 密码强度合格
                      </Text>
                    ) : (
                      passwordErrors.map((err, i) => (
                        <Text key={i} type="danger" style={{ fontSize: 12 }}>
                          <CloseCircleOutlined /> {err}
                        </Text>
                      ))
                    )}
                  </Space>
                </div>
              )}

              <Form.Item
                name="confirmPassword"
                rules={[
                  { required: true, message: '请确认密码' },
                  ({ getFieldValue }) => ({
                    validator(_, value) {
                      if (!value || getFieldValue('password') === value) {
                        return Promise.resolve();
                      }
                      return Promise.reject(new Error('两次输入的密码不一致'));
                    },
                  }),
                ]}
              >
                <Input.Password
                  prefix={<LockOutlined />}
                  placeholder="确认密码"
                  size="large"
                  iconRender={(visible) =>
                    visible ? <EyeOutlined /> : <EyeInvisibleOutlined />
                  }
                  visibilityToggle={{ visible: showConfirm, onVisibleChange: setShowConfirm }}
                />
              </Form.Item>

              <Form.Item>
                <Button
                  type="primary"
                  htmlType="submit"
                  size="large"
                  block
                  loading={isLoading}
                >
                  注册
                </Button>
              </Form.Item>
            </Form>

            <Divider plain>或</Divider>

            <div style={{ textAlign: 'center' }}>
              <Text>已有账号？ </Text>
              <Link onClick={() => navigate('/login')}>立即登录</Link>
            </div>
          </Col>
        </Row>
      </Card>
    </div>
  );
}
