import React, { useMemo, useCallback } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import {
  Layout,
  Menu,
  Avatar,
  Button,
  Typography,
  Divider,
  Tooltip,
} from 'antd';
import {
  DashboardOutlined,
  BuildOutlined,
  ExperimentOutlined,
  PieChartOutlined,
  DatabaseOutlined,
  SettingOutlined,
  RobotOutlined,
  ForkOutlined,
  ShopOutlined,
  MenuFoldOutlined,
  MenuUnfoldOutlined,
  LogoutOutlined,
  UserOutlined,
} from '@ant-design/icons';
import { useAppStore } from '../../stores/appStore';

const { Sider } = Layout;
const { Text } = Typography;

interface MenuItemDef {
  key: string;
  icon: React.ReactNode;
  label: string;
  path: string;
}

const menuItems: MenuItemDef[] = [
  { key: '/', icon: <DashboardOutlined />, label: '仪表盘', path: '/' },
  { key: '/strategy-builder', icon: <BuildOutlined />, label: '策略编辑器', path: '/strategy-builder' },
  { key: '/backtest', icon: <ExperimentOutlined />, label: '回测中心', path: '/backtest' },
  { key: '/results-ai', icon: <RobotOutlined />, label: 'Results AI', path: '/results-ai' },
  { key: '/fuzzy-builder', icon: <ForkOutlined />, label: '模糊策略', path: '/fuzzy-builder' },
  { key: '/indicator-marketplace', icon: <ShopOutlined />, label: '指标市场', path: '/indicator-marketplace' },
  { key: '/portfolio', icon: <PieChartOutlined />, label: '组合管理', path: '/portfolio' },
  { key: '/data', icon: <DatabaseOutlined />, label: '数据管理', path: '/data' },
  { key: '/settings', icon: <SettingOutlined />, label: '系统设置', path: '/settings' },
];

export default function Sidebar() {
  const navigate = useNavigate();
  const location = useLocation();
  const collapsed = useAppStore((s) => s.sidebarCollapsed);
  const setCollapsed = useAppStore((s) => s.setSidebarCollapsed);
  const user = useAppStore((s) => s.user);
  const clearAuth = useAppStore((s) => s.clearAuth);

  const selectedKey = useMemo(() => {
    const item = menuItems.find((m) => location.pathname === m.path || location.pathname.startsWith(`${m.path}/`));
    return item?.key || '/';
  }, [location.pathname]);

  const handleClick = useCallback(
    (e: { key: string }) => {
      const item = menuItems.find((m) => m.key === e.key);
      if (item) {
        navigate(item.path);
      }
    },
    [navigate]
  );

  const handleLogout = useCallback(() => {
    clearAuth();
    localStorage.removeItem('token');
    localStorage.removeItem('user');
    window.location.href = '/login';
  }, [clearAuth]);

  return (
    <Sider
      collapsible
      collapsed={collapsed}
      trigger={null}
      width={200}
      collapsedWidth={64}
      className="sidebar-container"
      style={{
        position: 'fixed',
        left: 0,
        top: 0,
        bottom: 0,
        zIndex: 100,
        background: '#001529',
        display: 'flex',
        flexDirection: 'column',
      }}
    >
      <div
        style={{
          height: 64,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          padding: collapsed ? 0 : '0 16px',
        }}
      >
        {!collapsed && (
          <div className="logo" style={{ fontSize: 18, fontWeight: 'bold', color: '#fff' }}>
            Hermass
          </div>
        )}
        <Button
          type="text"
          icon={collapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />}
          onClick={() => setCollapsed(!collapsed)}
          style={{ color: '#fff', marginLeft: collapsed ? 0 : 'auto' }}
        />
      </div>

      <Menu
        theme="dark"
        mode="inline"
        selectedKeys={[selectedKey]}
        items={menuItems.map((item) => ({
          key: item.key,
          icon: item.icon,
          label: item.label,
        }))}
        onClick={handleClick}
        style={{ flex: 1, borderRight: 0 }}
      />

      <div style={{ padding: collapsed ? 8 : 16, borderTop: '1px solid rgba(255,255,255,0.1)' }}>
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 8,
            justifyContent: collapsed ? 'center' : 'flex-start',
          }}
        >
          <Avatar size="small" icon={<UserOutlined />} style={{ backgroundColor: '#1890ff' }} />
          {!collapsed && (
            <div style={{ flex: 1, minWidth: 0 }}>
              <Text ellipsis style={{ color: 'rgba(255,255,255,0.85)', fontSize: 12, display: 'block' }}>
                {user?.email || '用户'}
              </Text>
            </div>
          )}
        </div>

        {!collapsed && (
          <>
            <Divider style={{ margin: '8px 0', borderColor: 'rgba(255,255,255,0.1)' }} />
            <Button
              type="text"
              danger
              icon={<LogoutOutlined />}
              onClick={handleLogout}
              style={{ color: 'rgba(255,255,255,0.65)', width: '100%', textAlign: 'left' }}
              size="small"
            >
              退出登录
            </Button>
          </>
        )}

        {collapsed && (
          <Tooltip title="退出登录" placement="right">
            <Button
              type="text"
              danger
              icon={<LogoutOutlined />}
              onClick={handleLogout}
              style={{ color: 'rgba(255,255,255,0.65)', marginTop: 8, width: '100%' }}
              size="small"
            />
          </Tooltip>
        )}
      </div>
    </Sider>
  );
}
