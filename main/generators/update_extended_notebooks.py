"""修正目录重组后扩展 Notebook 的路径和配置入口；可重复运行。"""
import json
import re
from pathlib import Path
import nbformat

ROOT = Path(__file__).resolve().parents[2]
BOOT = '''# project notebook bootstrap
import os, sys, json
from pathlib import Path
COOKBOOK_ROOT = next(p for p in (Path.cwd().resolve(), *Path.cwd().resolve().parents)
                     if (p / "main/notebook_runtime.py").is_file())
sys.path.insert(0, str(COOKBOOK_ROOT / "main"))
from notebook_runtime import load_project_env
load_project_env(COOKBOOK_ROOT)
'''
SMART = BOOT + '''from notebook_runtime import start_smart_home
import urllib.request
PORT = int(os.getenv("SMART_HOME_PORT", "{port}"))
BASE = start_smart_home(COOKBOOK_ROOT / "{app}", PORT)
'''

def update(path):
    name = str(path.relative_to(ROOT))
    original_text = path.read_text()
    indent = 2 if '\n  "cells"' in original_text else 1
    nb = json.loads(original_text)
    changed = False
    for cell in nb['cells']:
        if cell['cell_type'] != 'code':
            continue
        old = ''.join(cell.get('source', []))
        source = old
        if 'jev_mem/' in name:
            source = source.replace('System-One (Jev 决策) : jev-latest @ https://api.typesafe.ai',
                                    "System-One (Jev 决策) : {os.getenv('TYPESAFE_DEFAULT_MODEL', 'jev-latest')} @ {os.getenv('TYPESAFE_BASE_URL', 'https://api.typesafe.ai')}")
            source = source.replace('"真 Jev (jev-latest)"', 'f"真 Jev ({config.jev_model})"')
            source = source.replace('../Jev-Mem/.env 填入 DEEPSEEK_API_KEY', 'main/.env 填入 DEEPSEEK_API_KEY')
            source = source.replace('print("全部完成，原始结果已存 /tmp/jev_mem_exp/results.json")',
                                    'print("全部完成，原始结果已存", exp_cache / "results.json")')
        if '# project notebook bootstrap' in source:
            if '10_本地模型/notebooks/' in name and 'finetuning.ipynb' in name and '# CUDA prerequisite' not in source:
                source += '\n# CUDA prerequisite: check before installing packages or downloading weights\nimport torch\nif not torch.cuda.is_available():\n    raise RuntimeError("当前微调实验需要 NVIDIA CUDA GPU；本机可运行数据构建和模型 API 教程，但不能执行此训练。")'
            elif name.endswith('jev_mem_scaling.ipynb') and '# Answer model prerequisite' not in source:
                source += '\n# Answer model prerequisite\nif not HAS_DEEPSEEK:\n    raise RuntimeError("缩放对比需要聊天模型 Key，请在 main/.env 配置 DEEPSEEK_API_KEY 或 OPENAI_API_KEY。")'
            elif source == old:
                continue
        if '10_本地模型/notebooks/' in name:
            if 'RUN_REAL_EXTRACTION = True' in source:
                source = source.replace('RUN_REAL_EXTRACTION = True', 'RUN_REAL_EXTRACTION = RAW_PATH.is_file()')
                source += '\nif not RUN_REAL_EXTRACTION:\n    print("跳过真实数据筛选：请先提供 RAW_PATH 指向的 ShareGPT 数据，或开启上一格 DOWNLOAD_SOURCE_IF_MISSING。")'
            source = source.replace('ROOT / "laya"', 'LAYA_DIR')
            source = source.replace('from laya.client import', 'from client import')
            if 'ROOT = next(' in source:
                anchor = 'LAYA_DIR = ' if 'full_v2' in name else ('DATA_PATH = ' if 'zh_head' in name else 'EXAMPLE_SPEC = ')
                remaining = source[source.index(anchor):]
                if 'full_v2' in name:
                    remaining = remaining[remaining.index('\n') + 1:]
                source = BOOT + 'from datetime import datetime\nimport uuid\nROOT = COOKBOOK_ROOT\nLAYA_DIR = ROOT / "main/10_本地模型"\nsys.path.insert(0, str(LAYA_DIR))\n' + remaining
        elif 'jev_mem/' in name:
            source = source.replace('from memory.jev_client import JevClient',
                                    'from jev_mem_compat import NotebookJevClient as JevClient')
            if 'from memory.jev_mem_config import JevMemConfig' in source and 'from jev_mem_compat import' not in source:
                source = source.replace('from memory.jev_mem_config import JevMemConfig',
                                        'from memory.jev_mem_config import JevMemConfig\nfrom jev_mem_compat import NotebookJevClient as JevClient')
            source = source.replace('trg_memory=trg_exp, jev_config=exp_config)',
                                    'trg_memory=trg_exp, jev_config=exp_config, jev_client=JevClient(exp_config))')
            source = source.replace('trg_memory=trg, jev_config=config)',
                                    'trg_memory=trg, jev_config=config, jev_client=JevClient(config))')
            source = source.replace('CACHE = Path("/tmp/jev_mem_walkthrough"); shutil.rmtree(CACHE, ignore_errors=True); CACHE.mkdir(parents=True)',
                                    'import tempfile\nCACHE = Path(tempfile.mkdtemp(prefix="jev_mem_walkthrough-"))')
            source = source.replace('exp_cache = Path("/tmp/jev_mem_exp"); exp_cache.mkdir(exist_ok=True)',
                                    'exp_cache = Path(tempfile.mkdtemp(prefix="jev_mem_exp-"))')
            source = source.replace('open("/tmp/jev_mem_exp/results.json", "w")', 'open(exp_cache / "results.json", "w")')
            source = source.replace('"/tmp/jev_mem_exp/compare.png"', 'exp_cache / "compare.png"')
            if 'REPO = Path("../Jev-Mem").resolve()' in source:
                source = source.replace('REPO = Path("../Jev-Mem").resolve()', BOOT + 'from notebook_runtime import jev_mem_root\nREPO = jev_mem_root(COOKBOOK_ROOT)')
            if 'JevMemConfig(jev_model=' not in source:
                source = source.replace('JevMemConfig(', 'JevMemConfig(jev_model=os.getenv("TYPESAFE_DEFAULT_MODEL", "jev-latest"), jev_base_url=os.getenv("TYPESAFE_BASE_URL", "https://api.typesafe.ai"), ')
        elif '09_Agent集成/01_' in name and 'NOTEBOOK_ROOT =' in source:
            start = source.index('ROOT = Path.cwd().resolve()')
            end = source.index('PI_EXE =', start)
            source = source[:start] + BOOT + 'ROOT = COOKBOOK_ROOT\nEXTENSION = ROOT / "main/09_Agent集成/pi_jev_demo/pi_jev_demo_extension.ts"\n' + source[end:]
        elif '09_Agent集成/02_' in name and 'CANDIDATES =' in source:
            start = source.index('CANDIDATES =')
            end = source.index('APP = ', start)
            source = source[:start] + BOOT + 'ROOT = COOKBOOK_ROOT\n' + source[end:]
        elif '05_智能家居实验/' in name and 'def up():' in source:
            source = SMART.format(port='8843', app='main/05_智能家居实验/smart_home_demo') + 'print(json.loads(urllib.request.urlopen(BASE + "/api/health").read()))'
        elif 'smart_home_walkthrough.ipynb' in name:
            if 'payload = {' in source:
                source = SMART.format(port='8810', app='main/07_实战应用/app/smart-home') + source.replace('"http://127.0.0.1:8810/api/jev"', 'BASE + "/api/jev"')
            elif 'def server_up():' in source:
                source = 'health = json.loads(urllib.request.urlopen(BASE + "/api/health").read())\nprint("服务状态：", health)'
        elif '06_模型评测/' in name:
            if name.endswith('jevbench_intro.ipynb'):
                source = source.replace('if not LAYA_ALIVE:\n    cfg.runners = [r for r in cfg.runners if r.adapter != "laya_local"]\nmanifest = run_multi(cfg)', 'manifest = run_multi(cfg)')
            source = source.replace('"TYPESAFE_API_KEY":  "https://api.typesafe.ai",',
                                    '"TYPESAFE_API_KEY":  os.getenv("TYPESAFE_BASE_URL", "https://api.typesafe.ai"),')
            source = source.replace('os.environ.get(key_env + "_BASE_URL", "")',
                                    'os.environ.get("TYPESAFE_BASE_URL" if key_env == "TYPESAFE_API_KEY" else key_env + "_BASE_URL", "")')
            source = source.replace('os.environ.get(p["key_env"] + "_BASE_URL", "")',
                                    'os.environ.get("TYPESAFE_BASE_URL" if p["key_env"] == "TYPESAFE_API_KEY" else p["key_env"] + "_BASE_URL", "")')
            if name.endswith('jevbench_intro.ipynb') and 'def detect_platform()' in source:
                source = BOOT + '''from notebook_runtime import benchmark_workspace
sys.path.insert(0, str(COOKBOOK_ROOT / "main/06_模型评测/benchmark"))
PROJ = benchmark_workspace(COOKBOOK_ROOT)
os.chdir(PROJ)
PLATFORM = "jupyter_local"
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
'''
            elif 'COOKBOOK_ROOT = None' in source:
                source = BOOT + '''from notebook_runtime import benchmark_workspace
sys.path.insert(0, str(COOKBOOK_ROOT / "main/06_模型评测/benchmark"))
PROJ = benchmark_workspace(COOKBOOK_ROOT)
os.chdir(PROJ)
import subprocess, time, statistics, hashlib, shutil
print("独立评测输出目录：", PROJ)
'''
            if not name.endswith('jevbench_intro.ipynb') and 'manifest = run_multi(cfg)' in source and 'cfg.runners = [r for r' not in source:
                source = source.replace('manifest = run_multi(cfg)', 'if not LAYA_ALIVE:\n    cfg.runners = [r for r in cfg.runners if r.adapter != "laya_local"]\nmanifest = run_multi(cfg)')
            if 'cfg = MultiRunConfig(' in source and 'max_input_tokens=65536' not in source:
                source = re.sub(r'(?m)^(\s*)(cap_usd=(?:2\.0|CAP_USD),)$',
                                r'\1\2\n\1max_input_tokens=65536,  # 长上下文题不能沿用 2000 token 的预留假设', source)
            if '# === cleanup ===' in source or "pid_file = Path('runs/laya_serve.pid')" in source:
                marker = source.index("pid_file = Path('runs/laya_serve.pid')")
                source = source[:marker] + 'print("本 Notebook 未启动 Laya 服务，因此不终止已有进程。")'
        if source != old:
            cell['source'] = source.splitlines(keepends=True)
            cell['outputs'] = []
            cell['execution_count'] = None
            changed = True
    if changed:
        nbformat.validate(nbformat.from_dict(nb))
        path.write_text(json.dumps(nb, ensure_ascii=False, indent=indent) + '\n')
    return changed

if __name__ == '__main__':
    paths = [p for p in (ROOT / 'main').rglob('*.ipynb') if p.parts[len(ROOT.parts)+1].startswith(('05_', '06_', '07_', '08_', '09_', '10_')) and '.ipynb_checkpoints' not in p.parts]
    print('Updated extended notebooks:', sum(update(p) for p in paths))
