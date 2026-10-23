"""扩展实验的项目路径与 .env 加载；不打印或保存密钥。"""
from __future__ import annotations

import atexit
import os
import json
import importlib.util
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

from dotenv import dotenv_values


def project_root(start: Path | None = None) -> Path:
    start = (start or Path.cwd()).resolve()
    for parent in (start, *start.parents):
        if (parent / "main/notebook_runtime.py").is_file():
            return parent
    raise FileNotFoundError("请从 jev-cookbook 仓库或其子目录运行 Notebook")


def load_project_env(root: Path | None = None) -> dict:
    config = dotenv_values((root or project_root()) / "main/.env")
    for key, value in config.items():
        if value is not None and (key.startswith(("TYPESAFE_", "DEEPSEEK_", "OPENAI_", "STEPFUN_"))
                                  or key == "ANSWER_MODEL"):
            os.environ[key] = value
    return config


def jev_mem_root(root: Path) -> Path:
    configured = os.getenv("JEV_MEM_ROOT")
    candidates = ([Path(configured).expanduser()] if configured else []) + [
        root.parent / "Jev-Mem", root / "Jev-Mem", root / "main/08_前沿研究/Jev-Mem"]
    for path in candidates:
        if (path / "jev_mem").is_dir():
            return path.resolve()
    raise FileNotFoundError("缺少 Jev-Mem 外部项目：请克隆 https://github.com/libingzheren/Jev-Mem，"
                            "并将 JEV_MEM_ROOT 设置为该项目的绝对路径")


def benchmark_workspace(root: Path) -> Path:
    """在独立目录组装仓库已有题库；避免覆盖既有实验或依赖缺失的聚合文件。"""
    workspace = Path(tempfile.mkdtemp(prefix="jev-benchmark-"))
    tasks = workspace / "tasks"
    shutil.copytree(root / "main/06_模型评测/benchmark/tasks", tasks)
    records = []
    converter_path = root / "main/06_模型评测/benchmark/scripts/convert_jevbench.py"
    spec = importlib.util.spec_from_file_location("jevbench_conversion", converter_path)
    converter = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(converter)
    for name in ("easy", "original", "hard"):
        raw = [json.loads(line) for line in (tasks / f"{name}.jsonl").read_text().splitlines() if line.strip()]
        converted = [converter.convert(row) if "question" in row else row for row in raw]
        (tasks / f"{name}.jsonl").write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in converted))
        records.extend(converted)
    if len({row["id"] for row in records}) != len(records):
        raise ValueError("题库包含重复 ID")
    (tasks / "public_all.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records))
    smoke = [next(r for r in records if r["question_type"] == kind) for kind in ("choice", "noul", "score")]
    (tasks / "smoke.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in smoke))
    return workspace


def start_smart_home(app: Path, port: int) -> str:
    """复用已运行的服务；只在内核退出时停止本内核创建的进程。"""
    base = f"http://127.0.0.1:{port}"

    def healthy():
        try:
            with urllib.request.urlopen(base + "/api/health", timeout=1) as response:
                return response.status == 200
        except OSError:
            return False

    if healthy():
        return base
    load_project_env()
    log = tempfile.TemporaryFile()
    proc = subprocess.Popen([sys.executable, str(app / "serve_smart_home.py"),
                             "--port", str(port), "--host", "127.0.0.1", "--no-open"],
                            cwd=app, env=os.environ.copy(), stdout=log, stderr=log)

    def stop():
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
        log.close()

    atexit.register(stop)
    for _ in range(50):
        if healthy():
            return base
        if proc.poll() is not None:
            stop()
            raise RuntimeError("智能家居服务启动失败，请在当前 Python 环境直接运行 serve_smart_home.py 检查依赖")
        time.sleep(0.2)
    stop()
    raise TimeoutError("智能家居服务启动超过 10 秒")
