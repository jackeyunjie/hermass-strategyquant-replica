import React, { useMemo, useCallback } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import {
  Layout,
  Breadcrumb,
  Badge,
  Avatar,
  Dropdown,
  Typography,
  Space,
  theme,
} from 'antd';
import {
  BellOutlined,
  UserOutlined,
  SettingOutlined,
  LogoutOutlined,
  DownOutlined,
} from '@ant-design/icons';
import { useAppStore } from '../../stores/appStore';

const { Header: AntHeader } = Layout;
const { Text } = Typography;

const routeTitleMap: Record<string, string> = {
  '/': '仪表盘',
  '/strategy-builder': '策略编辑器',
  '/backtest': '回测中心',
  '/portfolio': '组合管理',
  '/data': '数据管理',
  '/settings': '系统设置',
};

export default function Header() {
  const location = useLocation();
  const navigate = useNavigate();
  const user = useAppStore((s) => s.user);
  const clearAuth = useAppStore((s) => s.clearAuth);
  const sidebarCollapsed = useAppStore((s) => s.sidebarCollapsed);
  const { token } = theme.useToken();

  const breadcrumbItems = useMemo(() => {
    const items: { title: string }[] = [{ title: '首页' }];
    const path = location.pathname;
    if (routeTitleMap[path]) {
      items.push({ title: routeTitleMap[path] });
    }
    return items;
  }, [location.pathname]);

  const handleLogout = useCallback(() => {
    clearAuth();
    localStorage.removeItem('token');
    localStorage.removeItem('user');
    window.location.href = '/login';
  }, [clearAuth]);

  const dropdownItems = useMemo(
    () => [
      {
        key: 'settings',
        icon: <SettingOutlined />,
        label: '个人设置',
        onClick: () => navigate('/settings'),
      },
      {
        key: 'logout',
        icon: <LogoutOutlined />,
        label: '退出登录',
        onClick: handleLogout,
      },
    ],
    [navigate, handleLogout]
  );

  return (
    <AntHeader
      style={{
        position: 'fixed',
        top: 0,
        left: sidebarCollapsed ? 64 : 200,
        right: 0,
        zIndex: 99,
        height: 64,
        padding: '0 24px',
        background: '#fff',
        boxShadow: '0 1px 4px rgba(0,0,0,0.1)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        transition: 'left 0.2s',
      }}
    >
      <div>
        <div style={{ fontSize: 18, fontWeight: 600, marginBottom: 4 }}>
          Hermass StrategyQuant
        </div>
        <Breadcrumb items={breadcrumbItems} style={{ fontSize: 12 }} />
      </div>

      <Space size="large">
        <Badge count={3} size="small">
          <BellOutlined
            style={{ fontSize: 18, color: token.colorTextSecondary, cursor: 'pointer' }}
          />
        </Badge>

        <Dropdown menu={{ items: dropdownItems }} placement="bottomRight">
          <Space style={{ cursor: 'pointer' }}>
            <Avatar size="small" icon={<UserOutlined />} style={{ backgroundColor: '#1890ff' }} />
            <Text style={{ fontSize: 14 }}>{user?.email || '用户'}</Text>
            <DownOutlined style={{ fontSize: 12 }} />
          </Space>
        </Dropdown>
      </Space>
    </AntHeader>
  );
}
