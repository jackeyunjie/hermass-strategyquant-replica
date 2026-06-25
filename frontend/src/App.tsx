import React, { Suspense, lazy } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { Layout } from 'antd';
import Sidebar from './components/common/Sidebar';
import Header from './components/common/Header';
import ProtectedRoute from './components/common/ProtectedRoute';
import { useAppStore } from './stores/appStore';
import './index.css';

const LoginPage = lazy(() => import('./pages/LoginPage'));
const RegisterPage = lazy(() => import('./pages/RegisterPage'));
const Dashboard = lazy(() => import('./pages/Dashboard'));
const StrategyEditor = lazy(() => import('./components/strategy-editor/StrategyEditor'));
const BacktestPage = lazy(() => import('./pages/BacktestPage'));
const ResultsAIPage = lazy(() => import('./pages/ResultsAIPage'));
const FuzzyBuilderPage = lazy(() => import('./pages/FuzzyBuilderPage'));
const IndicatorMarketplacePage = lazy(() => import('./pages/IndicatorMarketplacePage'));
const PortfolioPage = lazy(() => import('./pages/PortfolioPage'));
const DataPage = lazy(() => import('./pages/DataPage'));
const SettingsPage = lazy(() => import('./pages/SettingsPage'));

const { Content } = Layout;

function AppLayout() {
  const sidebarCollapsed = useAppStore((s) => s.sidebarCollapsed);

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Sidebar />
      <Layout
        style={{
          marginLeft: sidebarCollapsed ? 64 : 200,
          transition: 'margin-left 0.2s',
        }}
      >
        <Header />
        <Content
          style={{
            marginTop: 64,
            padding: 24,
            background: '#f0f2f5',
            minHeight: 'calc(100vh - 64px)',
            overflow: 'auto',
          }}
        >
          <Routes>
            <Route
              path="/"
              element={
                <ProtectedRoute>
                  <Dashboard />
                </ProtectedRoute>
              }
            />
            <Route
              path="/strategy-builder"
              element={
                <ProtectedRoute>
                  <StrategyEditor />
                </ProtectedRoute>
              }
            />
            <Route
              path="/backtest"
              element={
                <ProtectedRoute>
                  <BacktestPage />
                </ProtectedRoute>
              }
            />
            <Route
              path="/results-ai"
              element={
                <ProtectedRoute>
                  <ResultsAIPage />
                </ProtectedRoute>
              }
            />
            <Route
              path="/fuzzy-builder"
              element={
                <ProtectedRoute>
                  <FuzzyBuilderPage />
                </ProtectedRoute>
              }
            />
            <Route
              path="/indicator-marketplace"
              element={
                <ProtectedRoute>
                  <IndicatorMarketplacePage />
                </ProtectedRoute>
              }
            />
            <Route
              path="/portfolio"
              element={
                <ProtectedRoute>
                  <PortfolioPage />
                </ProtectedRoute>
              }
            />
            <Route
              path="/data"
              element={
                <ProtectedRoute>
                  <DataPage />
                </ProtectedRoute>
              }
            />
            <Route
              path="/settings"
              element={
                <ProtectedRoute>
                  <SettingsPage />
                </ProtectedRoute>
              }
            />
          </Routes>
        </Content>
      </Layout>
    </Layout>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />
        <Route path="/*" element={<AppLayout />} />
      </Routes>
    </BrowserRouter>
  );
}
