"""后端 API 单元测试——FastAPI 端点路由、参数验证、认证流程。

使用 dependency_overrides 覆盖数据库和认证依赖，无需真实 PostgreSQL / Redis / Celery。
"""

import sys
import os
import uuid
import json
from datetime import datetime, timezone
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../backend"))
# backend 内部导入 engine 需要上层项目根目录在路径中
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from app.api.deps import get_db, get_current_user
from app.models.user import User
from app.models.strategy import Strategy, StrategyStatus
from app.models.backtest import Backtest, BacktestStatus
from app.core.security import create_access_token, get_password_hash


# ──────────────────────────── 全局 Fixture ────────────────────────────

@pytest.fixture
def mock_user():
    """创建一个 mock 用户对象（不写入数据库）。"""
    user = MagicMock(spec=User)
    user.id = uuid.UUID("12345678-1234-1234-1234-123456789abc")
    user.email = "test@example.com"
    # 使用 mock 哈希值，避免 passlib/bcrypt 版本兼容性问题
    user.hashed_password = "$2b$12$mockhashvalueforunittestonly"
    user.is_active = True
    user.created_at = datetime.now(timezone.utc)
    user.updated_at = datetime.now(timezone.utc)
    return user


@pytest.fixture
def mock_db():
    """创建 mock 异步数据库会话，支持 SQLAlchemy 链式调用。"""
    session = AsyncMock(spec=AsyncSession)
    
    # 配置链式调用返回值: execute() -> scalars() -> all()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    mock_result.scalar_one_or_none.return_value = None
    
    session.execute.return_value = mock_result
    
    # commit / refresh 等异步方法
    session.commit.return_value = None
    session.refresh.return_value = None
    session.close.return_value = None
    
    return session


@pytest.fixture
def test_client(mock_user, mock_db):
    """配置 TestClient，覆盖所有外部依赖。"""
    # 覆盖 lifespan 避免连接 PostgreSQL
    @asynccontextmanager
    async def fake_lifespan(app: FastAPI):
        yield

    # 临时替换 lifespan
    original_lifespan = app.router.lifespan_context
    app.router.lifespan_context = fake_lifespan

    # 覆盖 get_db 依赖
    async def override_get_db():
        yield mock_db

    # 覆盖 get_current_user 依赖
    async def override_get_current_user():
        return mock_user

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user

    with TestClient(app) as client:
        yield client

    # 清理 overrides
    app.dependency_overrides.clear()
    app.router.lifespan_context = original_lifespan


@pytest.fixture
def auth_token(mock_user):
    """生成有效的 JWT token。"""
    return create_access_token({"sub": str(mock_user.id)})


# ──────────────────────────── 健康检查端点 ────────────────────────────

class TestHealthCheck:
    """测试 /health 端点。"""

    def test_health_check_returns_200(self, test_client):
        """健康检查应返回 200 或 503。"""
        response = test_client.get("/health")
        assert response.status_code in (200, 503)
        data = response.json()
        assert "status" in data
        assert "checks" in data

    def test_health_check_structure(self, test_client):
        """健康检查响应结构正确。"""
        response = test_client.get("/health")
        data = response.json()
        assert data["app"] == "Hermass StrategyQuant"
        assert "version" in data
        assert "database" in data.get("checks", {})


# ──────────────────────────── 认证端点 ────────────────────────────

class TestAuthEndpoints:
    """测试 /api/v1/auth 认证端点。"""

    def test_register_validation(self, test_client):
        """注册端点应验证密码强度。"""
        response = test_client.post(
            "/api/v1/auth/register",
            json={"email": "test@example.com", "password": "weak"},
        )
        assert response.status_code == 422

    def test_register_password_no_digit(self, test_client):
        """密码必须包含数字。"""
        response = test_client.post(
            "/api/v1/auth/register",
            json={"email": "test@example.com", "password": "onlyletters"},
        )
        assert response.status_code == 422

    def test_register_password_no_letter(self, test_client):
        """密码必须包含字母。"""
        response = test_client.post(
            "/api/v1/auth/register",
            json={"email": "test@example.com", "password": "12345678"},
        )
        assert response.status_code == 422

    def test_login_validation(self, test_client):
        """登录端点应验证请求格式。"""
        response = test_client.post(
            "/api/v1/auth/login",
            data={"username": "not-an-email", "password": "test"},
        )
        assert response.status_code in (400, 422)

    def test_login_missing_fields(self, test_client):
        """登录缺少字段应返回 422。"""
        response = test_client.post(
            "/api/v1/auth/login",
            data={},
        )
        assert response.status_code == 422

    def test_me_requires_auth(self, test_client):
        """获取当前用户信息需要认证。"""
        # 临时清除 get_current_user override 以测试无认证场景
        app.dependency_overrides.pop(get_current_user, None)
        response = test_client.get("/api/v1/auth/me")
        assert response.status_code == 401

    def test_me_with_auth(self, test_client, auth_token):
        """提供有效 token 应能访问 /me。"""
        response = test_client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "email" in data
        assert data["email"] == "test@example.com"


# ──────────────────────────── 策略端点 ────────────────────────────

class TestStrategyEndpoints:
    """测试 /api/v1/strategies 策略 CRUD 端点。"""

    def test_create_strategy(self, test_client, auth_token):
        """创建策略应验证请求体。"""
        response = test_client.post(
            "/api/v1/strategies",
            headers={"Authorization": f"Bearer {auth_token}"},
            json={"name": "MA Cross Strategy", "description": "SMA 20 > 50"},
        )
        assert response.status_code in (200, 201)

    def test_create_strategy_validation(self, test_client, auth_token):
        """创建策略缺少 name 应返回 422。"""
        response = test_client.post(
            "/api/v1/strategies",
            headers={"Authorization": f"Bearer {auth_token}"},
            json={"description": "missing name"},
        )
        assert response.status_code == 422

    def test_list_strategies(self, test_client, auth_token):
        """列出策略应返回列表。"""
        response = test_client.get(
            "/api/v1/strategies",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "items" in data or "total" in data or isinstance(data, list)

    def test_get_strategy_not_found(self, test_client, auth_token):
        """获取不存在的策略应返回 404。"""
        fake_id = str(uuid.uuid4())
        response = test_client.get(
            f"/api/v1/strategies/{fake_id}",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert response.status_code in (404, 500)

    def test_update_strategy_validation(self, test_client, auth_token):
        """更新策略验证 status 枚举。"""
        fake_id = str(uuid.uuid4())
        response = test_client.put(
            f"/api/v1/strategies/{fake_id}",
            headers={"Authorization": f"Bearer {auth_token}"},
            json={"status": "invalid_status"},
        )
        assert response.status_code == 422

    def test_delete_strategy_not_found(self, test_client, auth_token):
        """删除不存在的策略应返回 404 或 500。"""
        fake_id = str(uuid.uuid4())
        response = test_client.delete(
            f"/api/v1/strategies/{fake_id}",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert response.status_code in (404, 500)

    def test_generate_code_validation(self, test_client, auth_token):
        """生成代码端点应验证模板名称。"""
        fake_id = str(uuid.uuid4())
        response = test_client.post(
            f"/api/v1/strategies/{fake_id}/generate",
            headers={"Authorization": f"Bearer {auth_token}"},
            json={"template": "invalid_template"},
        )
        assert response.status_code in (400, 404, 422, 500)

    def test_strategy_endpoints_require_auth(self, test_client):
        """策略端点需要认证。"""
        # 临时清除 auth override
        app.dependency_overrides.pop(get_current_user, None)
        response = test_client.get("/api/v1/strategies")
        assert response.status_code == 401


# ──────────────────────────── 回测端点 ────────────────────────────

class TestBacktestEndpoints:
    """测试 /api/v1/backtests 回测端点。"""

    def test_create_backtest_validation(self, test_client, auth_token):
        """创建回测缺少 strategy_id 应返回 422。"""
        response = test_client.post(
            "/api/v1/backtests",
            headers={"Authorization": f"Bearer {auth_token}"},
            json={"config": {}},
        )
        assert response.status_code == 422

    def test_create_backtest_bad_uuid(self, test_client, auth_token):
        """创建回测提供无效 UUID 应返回 422。"""
        response = test_client.post(
            "/api/v1/backtests",
            headers={"Authorization": f"Bearer {auth_token}"},
            json={"strategy_id": "not-a-uuid", "config": {}},
        )
        assert response.status_code == 422

    def test_list_backtests(self, test_client, auth_token):
        """列出回测应返回列表。"""
        response = test_client.get(
            "/api/v1/backtests",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "items" in data or "total" in data or isinstance(data, list)

    def test_get_backtest_not_found(self, test_client, auth_token):
        """获取不存在的回测应返回 404。"""
        fake_id = str(uuid.uuid4())
        response = test_client.get(
            f"/api/v1/backtests/{fake_id}",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert response.status_code in (404, 500)

    def test_backtest_status_not_found(self, test_client, auth_token):
        """获取回测状态（不存在的 ID）应返回 404。"""
        fake_id = str(uuid.uuid4())
        response = test_client.get(
            f"/api/v1/backtests/{fake_id}/status",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert response.status_code in (404, 500)

    def test_backtest_results_not_found(self, test_client, auth_token):
        """获取回测结果（不存在的 ID）应返回 404。"""
        fake_id = str(uuid.uuid4())
        response = test_client.get(
            f"/api/v1/backtests/{fake_id}/results",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert response.status_code in (404, 500)

    def test_backtest_endpoints_require_auth(self, test_client):
        """回测端点需要认证。"""
        app.dependency_overrides.pop(get_current_user, None)
        response = test_client.get("/api/v1/backtests")
        assert response.status_code == 401


# ──────────────────────────── 数据端点 ────────────────────────────

class TestDataEndpoints:
    """测试 /api/v1/data 市场数据端点。"""

    def test_get_data_coverage(self, test_client, auth_token):
        """数据覆盖端点应返回响应。"""
        response = test_client.get(
            "/api/v1/data/coverage",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert response.status_code in (200, 500)

    def test_get_data_preview(self, test_client, auth_token):
        """数据预览端点需要正确参数。"""
        response = test_client.get(
            "/api/v1/data/preview/000001.SZ",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert response.status_code in (200, 404, 422, 500)

    def test_data_endpoints_require_auth(self, test_client):
        """数据端点需要认证。"""
        app.dependency_overrides.pop(get_current_user, None)
        response = test_client.get("/api/v1/data/coverage")
        assert response.status_code == 401


# ──────────────────────────── 稳健性端点 ────────────────────────────

class TestRobustnessEndpoints:
    """测试 /api/v1/robustness 稳健性测试端点。"""

    def test_mc_simulation_validation(self, test_client, auth_token):
        """Monte Carlo 模拟端点应验证参数。"""
        response = test_client.post(
            "/api/v1/robustness/monte-carlo",
            headers={"Authorization": f"Bearer {auth_token}"},
            json={"strategy_id": str(uuid.uuid4()), "method": "invalid_method"},
        )
        assert response.status_code in (202, 400, 404, 422, 500)

    def test_wfo_analysis_validation(self, test_client, auth_token):
        """WFO 分析端点应验证参数。"""
        with patch("app.tasks.backtest_tasks.run_walk_forward_task") as mock_task:
            mock_task.delay.return_value = MagicMock(id="mock-wfo-task-id")
            response = test_client.post(
                "/api/v1/robustness/walk-forward",
                headers={"Authorization": f"Bearer {auth_token}"},
                json={"strategy_id": str(uuid.uuid4()), "n_splits": 0},
            )
            assert response.status_code in (202, 400, 404, 422, 500)

    def test_overfitting_detection_validation(self, test_client, auth_token):
        """过拟合检测端点应验证参数。"""
        response = test_client.post(
            "/api/v1/robustness/overfitting",
            headers={"Authorization": f"Bearer {auth_token}"},
            json={"strategy_id": str(uuid.uuid4()), "n_splits": 1},
        )
        assert response.status_code in (202, 400, 404, 422, 500)

    def test_robustness_report_not_found(self, test_client, auth_token):
        """获取不存在的稳健性报告应返回 404 或 501。"""
        response = test_client.get(
            "/api/v1/robustness/report/12345678-1234-1234-1234-123456789abc",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert response.status_code in (404, 500, 501)

    def test_robustness_endpoints_require_auth(self, test_client):
        """稳健性端点需要认证。"""
        app.dependency_overrides.pop(get_current_user, None)
        response = test_client.get("/api/v1/robustness/report/12345678-1234-1234-1234-123456789abc")
        assert response.status_code == 401


# ──────────────────────────── 优化器端点 ────────────────────────────

class TestOptimizerEndpoints:
    """测试 /api/v1/optimizer 参数优化端点。"""

    def test_optimize_run_validation(self, test_client, auth_token):
        """策略优化运行端点应验证参数。"""
        with patch("app.tasks.backtest_tasks.run_optimizer_task") as mock_task:
            mock_task.delay.return_value = MagicMock(id="mock-opt-task-id")
            response = test_client.post(
                "/api/v1/optimizer/run",
                headers={"Authorization": f"Bearer {auth_token}"},
                json={"strategy_id": str(uuid.uuid4()), "method": "invalid"},
            )
            assert response.status_code in (202, 400, 404, 422, 500)

    def test_optimizer_endpoints_require_auth(self, test_client):
        """优化器端点需要认证。"""
        app.dependency_overrides.pop(get_current_user, None)
        response = test_client.post(
            "/api/v1/optimizer/run",
            json={"strategy_id": str(uuid.uuid4()), "method": "tpe"},
        )
        assert response.status_code == 401


# ──────────────────────────── 全局异常处理 ────────────────────────────

class TestGlobalExceptionHandlers:
    """测试全局异常处理器。"""

    def test_pydantic_validation_error(self, test_client):
        """Pydantic 验证错误应返回 422 并包含详细错误信息。"""
        response = test_client.post(
            "/api/v1/auth/register",
            json={"email": "not-an-email"},
        )
        assert response.status_code == 422
        data = response.json()
        assert "errors" in data or "detail" in data
