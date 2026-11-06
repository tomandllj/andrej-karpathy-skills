#!/usr/bin/env python3
"""一键启动前后端开发服务（仅 Windows），前后端均热加载。

用法示例：
  python run.py
  python run.py --backend-port 8001 --frontend-port 5174
  python run.py -b 8001 -f 5174
也可直接改下方 DEFAULT_* 默认端口。

热加载说明：
  - 后端：uvicorn --reload，改 backend/app 下 .py 自动重启 API
  - 前端：Vite HMR，改 Vue/CSS/JS 浏览器自动热更新
  - Windows 下子进程独立控制台会话，避免重载时的 CTRL_C 误停本脚本
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import threading
import time
from pathlib import Path
from shutil import which

ROOT = Path(__file__).resolve().parent
BACKEND_DIR = ROOT / "backend"
FRONTEND_DIR = ROOT / "frontend"
BACKEND_APP_DIR = BACKEND_DIR / "app"

# 改这里即可换默认端口；命令行参数优先
DEFAULT_BACKEND_PORT = 8123
DEFAULT_FRONTEND_PORT = 5373

# CREATE_NO_WINDOW：子进程不挂到当前控制台，避免 uvicorn 热重载 CTRL_C 误杀 run.py
_CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
_CHILD_FLAGS = subprocess.CREATE_NEW_PROCESS_GROUP | _CREATE_NO_WINDOW


def parse_args() -> argparse.Namespace:
    """解析命令行端口参数。"""
    p = argparse.ArgumentParser(description="一键启动 MD 批注前后端（Windows · 热加载）")
    p.add_argument(
        "-b",
        "--backend-port",
        type=int,
        default=DEFAULT_BACKEND_PORT,
        help=f"后端端口（默认 {DEFAULT_BACKEND_PORT}）",
    )
    p.add_argument(
        "-f",
        "--frontend-port",
        type=int,
        default=DEFAULT_FRONTEND_PORT,
        help=f"前端端口（默认 {DEFAULT_FRONTEND_PORT}）",
    )
    return p.parse_args()


def resolve_venv_python() -> Path:
    """返回 backend\\.venv 里的 python.exe。"""
    candidate = BACKEND_DIR / ".venv" / "Scripts" / "python.exe"
    if not candidate.is_file():
        raise FileNotFoundError(
            f"未找到虚拟环境：{candidate}\n"
            "请先执行：cd backend && python -m venv .venv && "
            "pip install -r requirements.txt"
        )
    return candidate


def resolve_npm() -> str:
    """返回 npm.cmd 完整路径。"""
    found = which("npm.cmd") or which("npm")
    if not found:
        raise FileNotFoundError("未找到 npm，请先安装 Node.js：https://nodejs.org/")
    return found


def ensure_frontend_deps(npm: str) -> None:
    """若缺少 node_modules 则自动 npm install。"""
    if (FRONTEND_DIR / "node_modules").is_dir():
        return
    print("[frontend] 未检测到 node_modules，正在 npm install …")
    code = subprocess.call([npm, "install"], cwd=str(FRONTEND_DIR), shell=True)
    if code != 0:
        raise RuntimeError("npm install 失败")


def pipe_output(proc: subprocess.Popen, prefix: str) -> None:
    """把子进程输出按行转发到当前控制台。"""
    if proc.stdout is None:
        return
    for line in iter(proc.stdout.readline, ""):
        if line == "":
            break
        print(f"[{prefix}] {line}", end="")
        sys.stdout.flush()


def write_dev_port(port: int) -> None:
    """把后端端口写到根目录 .dev-port，供 Vite 代理读取。"""
    (ROOT / ".dev-port").write_text(str(port), encoding="utf-8")


def port_is_listening(port: int) -> bool:
    """查看本机是否已有进程监听该 TCP 端口。"""
    try:
        out = subprocess.check_output(
            ["netstat", "-ano", "-p", "tcp"],
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except (OSError, subprocess.CalledProcessError):
        return False
    token = f":{port}"
    return any("LISTENING" in line and token in line for line in out.splitlines())


def choose_backend_port(preferred: int) -> int:
    """优先用指定端口；清不掉的旧进程占着时，改用后面的空端口。"""
    free_listen_port(preferred)
    if not port_is_listening(preferred):
        return preferred
    for port in range(preferred + 1, min(preferred + 20, 65536)):
        if not port_is_listening(port):
            print(f"[backend] 端口 {preferred} 仍被占用，改用 {port}")
            return port
    print(f"[backend] 端口 {preferred} 仍被占用，继续使用该端口。")
    return preferred


def free_listen_port(port: int) -> None:
    """结束仍占用该端口的旧进程，避免旧后端挡住新服务。"""
    try:
        out = subprocess.check_output(
            ["netstat", "-ano", "-p", "tcp"],
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except (OSError, subprocess.CalledProcessError):
        return
    pids: set[int] = set()
    for line in out.splitlines():
        if "LISTENING" not in line or f":{port}" not in line:
            continue
        parts = line.split()
        if parts and parts[-1].isdigit():
            pids.add(int(parts[-1]))
    for pid in pids:
        if pid == os.getpid():
            continue
        print(f"[backend] 端口 {port} 被 pid={pid} 占用，正在结束旧进程…")
        subprocess.call(
            ["taskkill", "/PID", str(pid), "/T", "/F"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )


def start_backend(python_exe: Path, port: int) -> subprocess.Popen:
    """启动 FastAPI，并监视 app 目录热重载。"""
    cmd = [
        str(python_exe),
        "-m",
        "uvicorn",
        "app.main:app",
        "--host",
        "0.0.0.0",
        "--port",
        str(port),
        "--reload",
        "--reload-dir",
        str(BACKEND_APP_DIR),
    ]
    print(f"[backend] {' '.join(cmd)}")
    proc = subprocess.Popen(
        cmd,
        cwd=str(BACKEND_DIR),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
        creationflags=_CHILD_FLAGS,
    )
    threading.Thread(target=pipe_output, args=(proc, "backend"), daemon=True).start()
    return proc


def start_frontend(npm: str, frontend_port: int, backend_port: int) -> subprocess.Popen:
    """启动 Vite 开发服（自带 HMR），并把后端端口传给代理。"""
    # npm.cmd 需经 cmd /c；CREATE_NO_WINDOW 时仍可正常拉起 Vite
    cmd = [
        "cmd",
        "/c",
        npm,
        "run",
        "dev",
        "--",
        "--host",
        "0.0.0.0",
        "--port",
        str(frontend_port),
    ]
    env = {
        **os.environ,
        "BACKEND_PORT": str(backend_port),
        "FRONTEND_PORT": str(frontend_port),
    }
    print(f"[frontend] {' '.join(cmd)}  (BACKEND_PORT={backend_port})")
    proc = subprocess.Popen(
        cmd,
        cwd=str(FRONTEND_DIR),
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
        creationflags=_CHILD_FLAGS,
    )
    threading.Thread(target=pipe_output, args=(proc, "frontend"), daemon=True).start()
    return proc


def terminate_process(proc: subprocess.Popen | None, name: str) -> None:
    """用 taskkill 结束整棵进程树。"""
    if proc is None or proc.poll() is not None:
        return
    print(f"[{name}] 正在停止 (pid={proc.pid}) …")
    subprocess.call(
        ["taskkill", "/PID", str(proc.pid), "/T", "/F"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def main() -> int:
    """同时拉起后端与前端（热加载），Ctrl+C 时一并退出。"""
    if sys.platform != "win32":
        print("本脚本仅支持 Windows。", file=sys.stderr)
        return 1

    args = parse_args()
    backend_port = args.backend_port
    frontend_port = args.frontend_port

    if not (1 <= backend_port <= 65535 and 1 <= frontend_port <= 65535):
        print("端口必须在 1–65535 之间。", file=sys.stderr)
        return 1
    if backend_port == frontend_port:
        print("前后端端口不能相同。", file=sys.stderr)
        return 1

    if not BACKEND_DIR.is_dir() or not FRONTEND_DIR.is_dir():
        print("请在项目根目录运行：python run.py", file=sys.stderr)
        return 1

    try:
        python_exe = resolve_venv_python()
        npm = resolve_npm()
        ensure_frontend_deps(npm)
    except (FileNotFoundError, RuntimeError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    backend: subprocess.Popen | None = None
    frontend: subprocess.Popen | None = None

    try:
        backend_port = choose_backend_port(backend_port)
        write_dev_port(backend_port)
        backend = start_backend(python_exe, backend_port)
        time.sleep(0.8)
        frontend = start_frontend(npm, frontend_port, backend_port)

        print()
        print("=" * 48)
        print(f"  前端：http://127.0.0.1:{frontend_port}  （Vite HMR）")
        print(f"  后端：http://127.0.0.1:{backend_port}/api/health  （--reload）")
        print("  改前端/后端代码会自动生效，无需重启 run.py")
        print("  按 Ctrl+C 停止全部服务")
        print("=" * 48)
        print()

        while True:
            if backend.poll() is not None:
                print(f"[backend] 已退出，code={backend.returncode}")
                return backend.returncode or 1
            if frontend.poll() is not None:
                print(f"[frontend] 已退出，code={frontend.returncode}")
                return frontend.returncode or 1
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\n收到中断，正在关闭 …")
        return 0
    finally:
        terminate_process(frontend, "frontend")
        terminate_process(backend, "backend")


if __name__ == "__main__":
    sys.exit(main())
