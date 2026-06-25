import axios from 'axios';
import type { AxiosInstance, AxiosError } from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_URL || '/api/v1';

class ApiClient {
  private client: AxiosInstance;

  constructor() {
    this.client = axios.create({
      baseURL: API_BASE_URL,
      timeout: 30000,
      headers: {
        'Content-Type': 'application/json',
      },
    });

    // Request interceptor - add auth token
    this.client.interceptors.request.use((config) => {
      const token = localStorage.getItem('token');
      if (token) {
        config.headers.Authorization = `Bearer ${token}`;
      }
      return config;
    });

    // Response interceptor - handle errors
    this.client.interceptors.response.use(
      (response) => response,
      (error: AxiosError) => {
        if (error.response?.status === 401) {
          localStorage.removeItem('token');
          window.location.href = '/login';
        }
        return Promise.reject(error);
      }
    );
  }

  // ─────────────────── Auth ───────────────────
  async login(email: string, password: string) {
    const response = await this.client.post('/auth/login', { email, password });
    return response.data;
  }

  async getCurrentUser() {
    const response = await this.client.get('/auth/me');
    return response.data;
  }

  async register(email: string, password: string) {
    const response = await this.client.post('/auth/register', {
      email,
      password,
    });
    return response.data;
  }

  // ─────────────────── Strategies ───────────────────
  async getStrategies() {
    const response = await this.client.get('/strategies');
    return response.data;
  }

  async getStrategy(id: string) {
    const response = await this.client.get(`/strategies/${id}`);
    return response.data;
  }

  async createStrategy(strategy: any) {
    const response = await this.client.post('/strategies', strategy);
    return response.data;
  }

  async updateStrategy(id: string, strategy: any) {
    const response = await this.client.put(`/strategies/${id}`, strategy);
    return response.data;
  }

  async deleteStrategy(id: string) {
    const response = await this.client.delete(`/strategies/${id}`);
    return response.data;
  }

  // ─────────────────── Backtests ───────────────────
  async runBacktest(strategyId: string, config: any) {
    const response = await this.client.post('/backtests', {
      strategy_id: strategyId,
      config,
    });
    return response.data;
  }

  async getBacktestResults() {
    const response = await this.client.get('/backtests');
    return response.data;
  }

  async getBacktestResult(id: string) {
    const response = await this.client.get(`/backtests/${id}`);
    return response.data;
  }

  // ─────────────────── Data ───────────────────
  async downloadData(params: any) {
    const response = await this.client.post('/data/download', params);
    return response.data;
  }

  async getDataStatus() {
    const response = await this.client.get('/data/status');
    return response.data;
  }

  // ─────────────────── Code Generation ───────────────────
  async generateCode(strategyId: string, templateName: string) {
    const response = await this.client.post(`/strategies/${strategyId}/generate-code`, {
      template_name: templateName,
    });
    return response.data;
  }

  // ─────────────────── Results AI ───────────────────
  async analyzeResultsAI(payload: any) {
    const response = await this.client.post('/ai/results-ai/analyze', payload);
    return response.data;
  }

  // ─────────────────── Fuzzy Logic ───────────────────
  async generateFuzzyStrategy(payload: any) {
    const response = await this.client.post('/fuzzy/generate', payload);
    return response.data;
  }

  // ─────────────────── Indicator Marketplace ───────────────────
  async getMarketplaceIndicators(params?: { category?: string; search?: string }) {
    const response = await this.client.get('/indicator-marketplace', { params });
    return response.data;
  }

  async createMarketplaceIndicator(payload: any) {
    const response = await this.client.post('/indicator-marketplace', payload);
    return response.data;
  }

  async installMarketplaceIndicator(indicatorId: string) {
    const response = await this.client.post(`/indicator-marketplace/${indicatorId}/install`);
    return response.data;
  }
}

export const api = new ApiClient();
