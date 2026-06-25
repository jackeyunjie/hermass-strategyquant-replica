"""
Frontend-Backend Integration Test
====================================
验证前后端联调链路：
1. 前端 dev server 能启动并返回页面
2. Vite 代理正确转发 /api/* 到后端
3. 后端认证中间件正确拦截未认证请求（401）
4. 后端在无数据库时优雅降级启动

用法：
    cd /Users/lv111101/Documents/kimi/workspace/hermass-strategyquant-replica
    python3 tests/integration/test_frontend_backend.py
"""
import subprocess
import sys
import time
import urllib.request
import urllib.error
import json
import os


def start_backend():
    """启动后端 uvicorn 服务（无数据库模式）。"""
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app",
         "--host", "0.0.0.0", "--port", "8000", "--no-access-log"],
        cwd="backend",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    # 等待启动
    for _ in range(30):
        time.sleep(0.5)
        try:
            urllib.request.urlopen("http://localhost:8000/health", timeout=1)
            return proc
        except urllib.error.HTTPError as e:
            if e.code == 503:  # degraded but running
                return proc
        except Exception:
            pass
    proc.terminate()
    raise RuntimeError("Backend failed to start within 15s")


def start_frontend():
    """启动前端 Vite dev server。"""
    proc = subprocess.Popen(
        ["npm", "run", "dev"],
        cwd="frontend",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    # 等待启动
    for _ in range(30):
        time.sleep(0.5)
        try:
            urllib.request.urlopen("http://localhost:3000/", timeout=1)
            return proc
        except Exception:
            pass
    proc.terminate()
    raise RuntimeError("Frontend failed to start within 15s")


def fetch(url, headers=None, timeout=5):
    """发送 HTTP 请求并返回 (status, body)。"""
    req = urllib.request.Request(url, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8")


def main():
    backend_proc = None
    frontend_proc = None
    failed = False

    try:
        print("[1/5] 启动后端服务...")
        backend_proc = start_backend()
        print("      ✓ Backend running on http://localhost:8000")

        print("[2/5] 启动前端 dev server...")
        frontend_proc = start_frontend()
        print("      ✓ Frontend running on http://localhost:3000")

        print("[3/5] 测试前端页面加载...")
        status, body = fetch("http://localhost:3000/")
        assert status == 200, f"Expected 200, got {status}: {body[:200]}"
        assert "<html" in body.lower() or "<!doctype" in body.lower(), "Not an HTML page"
        print("      ✓ Frontend page loads (200)")

        print("[4/5] 测试 API 代理转发（无认证）...")
        status, body = fetch("http://localhost:3000/api/v1/strategies")
        assert status == 401, f"Expected 401, got {status}: {body[:200]}"
        data = json.loads(body)
        assert data.get("detail") == "Not authenticated", f"Unexpected body: {body[:200]}"
        print("      ✓ Proxy forwards correctly, auth returns 401")

        print("[5/5] 测试 API 代理转发（伪造 token）...")
        status, body = fetch(
            "http://localhost:3000/api/v1/strategies",
            headers={"Authorization": "Bearer faketoken"}
        )
        assert status == 401, f"Expected 401, got {status}: {body[:200]}"
        data = json.loads(body)
        assert "Could not validate credentials" in data.get("detail", "")
        print("      ✓ JWT validation rejects fake token")

        print("\n" + "=" * 50)
        print("  All frontend-backend integration tests PASSED")
        print("=" * 50)

    except Exception as e:
        failed = True
        print(f"\n✗ FAILED: {e}")

    finally:
        if frontend_proc:
            frontend_proc.terminate()
            try:
                frontend_proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                frontend_proc.kill()
        if backend_proc:
            backend_proc.terminate()
            try:
                backend_proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                backend_proc.kill()

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
