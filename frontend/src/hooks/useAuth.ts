import { useCallback, useState, useEffect } from 'react';
import { message } from 'antd';
import { api } from '../services/api';
import type { User, AuthResponse } from '../types';

export function useAuth() {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(localStorage.getItem('token'));
  const [isLoading, setIsLoading] = useState(false);
  const [isAuthenticated, setIsAuthenticated] = useState(!!localStorage.getItem('token'));

  useEffect(() => {
    const storedToken = localStorage.getItem('token');
    if (storedToken) {
      setToken(storedToken);
      setIsAuthenticated(true);
      // Try to parse user info from storage
      try {
        const storedUser = localStorage.getItem('user');
        if (storedUser) {
          setUser(JSON.parse(storedUser) as User);
        }
      } catch {
        // Invalid user JSON, ignore
      }
    }
  }, []);

  const login = useCallback(async (email: string, password: string): Promise<boolean> => {
    setIsLoading(true);
    try {
      const response: AuthResponse = await api.login(email, password);
      const { access_token } = response;
      localStorage.setItem('token', access_token);
      const user = await api.getCurrentUser();
      localStorage.setItem('user', JSON.stringify(user));
      setToken(access_token);
      setUser(user);
      setIsAuthenticated(true);
      message.success('登录成功');
      return true;
    } catch (err: unknown) {
      const error = err as { response?: { data?: { detail?: string } } };
      message.error(error?.response?.data?.detail || '登录失败，请检查邮箱和密码');
      return false;
    } finally {
      setIsLoading(false);
    }
  }, []);

  const register = useCallback(async (email: string, password: string): Promise<boolean> => {
    setIsLoading(true);
    try {
      await api.register(email, password);
      message.success('注册成功');
      // Auto-login after registration
      return await login(email, password);
    } catch (err: unknown) {
      const error = err as { response?: { data?: { detail?: string } } };
      message.error(error?.response?.data?.detail || '注册失败');
      return false;
    } finally {
      setIsLoading(false);
    }
  }, [login]);

  const logout = useCallback(() => {
    localStorage.removeItem('token');
    localStorage.removeItem('user');
    setToken(null);
    setUser(null);
    setIsAuthenticated(false);
    message.success('已退出登录');
    window.location.href = '/login';
  }, []);

  const checkAuth = useCallback(() => {
    const storedToken = localStorage.getItem('token');
    return !!storedToken;
  }, []);

  return {
    user,
    token,
    isAuthenticated,
    isLoading,
    login,
    register,
    logout,
    checkAuth,
  };
}
