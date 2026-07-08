#!/usr/bin/env python3
"""Run available project features from a single entry point.

Default behavior:
- starts FastAPI backend
- starts Next.js frontend (if present)

Optional behavior:
- starts Streamlit prototype UI

Use --dry-run to print the commands without starting processes.
"""

import argparse
import os
import signal
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path
from typing import List, Optional, Sequence


def _python_has_module(python_bin: str, module_name: str) -> bool:
    try:
        result = subprocess.run(
            [python_bin, "-c", "import {}".format(module_name)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        return result.returncode == 0
    except Exception:
        return False


def _pick_python(root: Path, required_module: str) -> Optional[str]:
    candidates = []
    venv_python = root / "venv_copilot" / "Scripts" / "python.exe"
    if venv_python.exists():
        candidates.append(str(venv_python))
    candidates.append(sys.executable)

    for candidate in candidates:
        if _python_has_module(candidate, required_module):
            return candidate

    return None


class ManagedProcess:
    def __init__(self, name: str, cmd: Sequence[str], cwd: Path) -> None:
        self.name = name
        self.cmd = list(cmd)
        self.cwd = cwd
        self.proc = None  # type: Optional[subprocess.Popen]

    def start(self) -> None:
        self.proc = subprocess.Popen(
            self.cmd,
            cwd=str(self.cwd),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            bufsize=1,
            universal_newlines=True,
        )

    def is_running(self) -> bool:
        return self.proc is not None and self.proc.poll() is None

    def terminate(self, timeout_sec: float = 8.0) -> None:
        if self.proc is None:
            return
        if self.proc.poll() is not None:
            return

        self.proc.terminate()
        deadline = time.time() + timeout_sec
        while time.time() < deadline:
            if self.proc.poll() is not None:
                return
            time.sleep(0.2)

        self.proc.kill()


def build_backend_command(root: Path, backend_port: int) -> List[str]:
    python_bin = _pick_python(root, "uvicorn")
    if python_bin is None:
        raise RuntimeError("Could not find a Python interpreter with 'uvicorn' installed.")
    return [
        python_bin,
        "-m",
        "uvicorn",
        "api.main:app",
        "--host",
        "0.0.0.0",
        "--port",
        str(backend_port),
        "--reload",
    ]


def build_frontend_command(frontend_port: int) -> List[str]:
    return ["npm", "run", "dev", "--", "--port", str(frontend_port)]


def build_streamlit_command(root: Path, streamlit_port: int) -> List[str]:
    python_bin = _pick_python(root, "streamlit")
    if python_bin is None:
        raise RuntimeError("Could not find a Python interpreter with 'streamlit' installed.")
    return [
        python_bin,
        "-m",
        "streamlit",
        "run",
        "ui/streamlit_app.py",
        "--server.port",
        str(streamlit_port),
    ]


def _pump_output(process: ManagedProcess) -> None:
    if process.proc is None or process.proc.stdout is None:
        return
    for line in process.proc.stdout:
        sys.stdout.write(f"[{process.name}] {line}")


def wait_for_http(url: str, timeout_sec: float = 30.0) -> bool:
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2.0) as response:
                if 200 <= response.status < 500:
                    return True
        except Exception:
            pass
        time.sleep(0.5)
    return False


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run project features from one file")
    parser.add_argument("--root", default=".", help="Project root path")
    parser.add_argument("--backend-port", type=int, default=8000)
    parser.add_argument("--frontend-port", type=int, default=3000)
    parser.add_argument("--streamlit-port", type=int, default=8501)
    parser.add_argument("--no-backend", action="store_true", help="Skip backend")
    parser.add_argument("--no-frontend", action="store_true", help="Skip frontend")
    parser.add_argument("--with-streamlit", action="store_true", help="Also run Streamlit UI")
    parser.add_argument("--dry-run", action="store_true", help="Print commands only")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = Path(args.root).resolve()

    if not (root / "api" / "main.py").exists():
        print(f"[error] Could not find backend entry at {root / 'api' / 'main.py'}")
        return 1

    processes: List[ManagedProcess] = []

    if not args.no_backend:
        try:
            backend_cmd = build_backend_command(root, args.backend_port)
        except RuntimeError as err:
            print("[error] {}".format(err))
            print("[hint] Install backend runtime dependencies before launching.")
            return 1

        processes.append(
            ManagedProcess(
                name="backend",
                cmd=backend_cmd,
                cwd=root,
            )
        )

    frontend_dir = root / "frontend"
    if not args.no_frontend and frontend_dir.exists() and (frontend_dir / "package.json").exists():
        processes.append(
            ManagedProcess(
                name="frontend",
                cmd=build_frontend_command(args.frontend_port),
                cwd=frontend_dir,
            )
        )
    elif not args.no_frontend:
        print("[warn] Frontend folder/package.json not found, skipping frontend.")

    if args.with_streamlit:
        streamlit_entry = root / "ui" / "streamlit_app.py"
        if streamlit_entry.exists():
            try:
                streamlit_cmd = build_streamlit_command(root, args.streamlit_port)
            except RuntimeError as err:
                print("[warn] {}".format(err))
                print("[warn] Skipping streamlit.")
            else:
                processes.append(
                    ManagedProcess(
                        name="streamlit",
                        cmd=streamlit_cmd,
                        cwd=root,
                    )
                )
        else:
            print("[warn] Streamlit UI file not found, skipping streamlit.")

    if not processes:
        print("[error] Nothing to run. Check flags and project structure.")
        return 1

    print("\nPlanned commands:\n")
    for p in processes:
        print(f"[{p.name}] cwd={p.cwd}")
        print("  " + " ".join(p.cmd))

    if args.dry_run:
        return 0

    for p in processes:
        p.start()

    threads: List[threading.Thread] = []
    for p in processes:
        t = threading.Thread(target=_pump_output, args=(p,), daemon=True)
        t.start()
        threads.append(t)

    if not args.no_backend:
        backend_ok = wait_for_http(f"http://127.0.0.1:{args.backend_port}/api/health", timeout_sec=45)
        if backend_ok:
            print(f"\n[ready] Backend healthy at http://127.0.0.1:{args.backend_port}/api/health")
        else:
            print("\n[warn] Backend health endpoint did not respond in time.")

    if not args.no_frontend and frontend_dir.exists() and (frontend_dir / "package.json").exists():
        frontend_ok = wait_for_http(f"http://127.0.0.1:{args.frontend_port}", timeout_sec=90)
        if frontend_ok:
            print(f"[ready] Frontend reachable at http://127.0.0.1:{args.frontend_port}")
        else:
            print("[warn] Frontend did not respond in time.")

    if args.with_streamlit:
        streamlit_ok = wait_for_http(f"http://127.0.0.1:{args.streamlit_port}", timeout_sec=45)
        if streamlit_ok:
            print(f"[ready] Streamlit reachable at http://127.0.0.1:{args.streamlit_port}")
        else:
            print("[warn] Streamlit did not respond in time.")

    print("\nPress Ctrl+C to stop all services.\n")

    try:
        while True:
            any_exited = False
            for p in processes:
                if p.proc is not None and p.proc.poll() is not None:
                    print(f"[exit] {p.name} exited with code {p.proc.returncode}")
                    any_exited = True
            if any_exited:
                break
            time.sleep(1.0)
    except KeyboardInterrupt:
        print("\n[stop] Stopping services...")
    finally:
        for p in processes:
            p.terminate()

    return 0


if __name__ == "__main__":
    if os.name == "nt":
        signal.signal(signal.SIGINT, signal.SIG_DFL)
    raise SystemExit(main())
