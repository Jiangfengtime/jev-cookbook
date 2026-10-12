"""统一旧版 Notebook 的 TypeSafe 配置：从项目 .env 读取密钥、地址与模型。"""
from __future__ import annotations

import re
import json
from pathlib import Path

import nbformat

ROOT = Path(__file__).resolve().parents[1]
TARGETS = [
    *ROOT.glob("01_认识Jev/*.ipynb"),
    *ROOT.glob("02_核心概念/*.ipynb"),
    *ROOT.glob("03_架构模式/*.ipynb"),
    *ROOT.glob("04_实战指南/*.ipynb"),
]
DOTENV_IMPORT = "from dotenv import find_dotenv, load_dotenv"
DOTENV_LOAD = 'load_dotenv(find_dotenv(usecwd=True) or "main/.env")'


def configure(source: str) -> str:
    if "TypeSafeClient(" not in source or "TYPESAFE_API_KEY" not in source:
        return source

    lines = source.splitlines()
    if "_cwd = Path.cwd().resolve()" in source:
        start = next(i for i, line in enumerate(lines) if line.startswith("_cwd ="))
        end = next(i for i, line in enumerate(lines) if line.startswith("RUN_MODE ="))
        lines[start:end] = [
            DOTENV_LOAD,
            'BASE_URL = os.getenv("TYPESAFE_BASE_URL") or None',
            'MODEL = os.getenv("TYPESAFE_DEFAULT_MODEL", "jev-1.13.0")',
        ]
        lines = [line for line in lines if not line.startswith("# 从项目 main/.env")]
        source = "\n".join(lines)
        source = source.replace('print("配置文件：", ENV_FILE or "未找到", "｜模式：", RUN_MODE,',
                                'print("模式：", RUN_MODE,')
        if "Path(" not in source:
            source = source.replace("from pathlib import Path\n", "")

    if DOTENV_IMPORT not in source:
        source = source.replace("import os\n", f"import os\n{DOTENV_IMPORT}\n", 1)
    if DOTENV_LOAD not in source:
        lines = source.splitlines()
        start = next((i for i, line in enumerate(lines)
                      if re.match(r"(?:MODEL|RUN_MODE|API_KEY|BASE_URL)\s*=", line)), None)
        if start is not None:
            lines.insert(start, DOTENV_LOAD)
            source = "\n".join(lines)

    source = re.sub(r'API_KEY = os\.(?:environ\.get|getenv)\("TYPESAFE_API_KEY", ""\)',
                    'API_KEY = os.getenv("TYPESAFE_API_KEY", "")', source)
    source = re.sub(r'BASE_URL = os\.(?:environ\.get|getenv)\("TYPESAFE_BASE_URL"[^\n]*',
                    'BASE_URL = os.getenv("TYPESAFE_BASE_URL") or None', source)
    source = re.sub(r'MODEL = os\.(?:environ\.get|getenv)\("TYPESAFE_DEFAULT_MODEL",',
                    'MODEL = os.getenv("TYPESAFE_DEFAULT_MODEL",', source)
    if not re.search(r"^BASE_URL\s*=", source, re.MULTILINE):
        source = source.replace(DOTENV_LOAD, DOTENV_LOAD +
                                '\nBASE_URL = os.getenv("TYPESAFE_BASE_URL") or None', 1)
    if not re.search(r"^MODEL\s*=", source, re.MULTILINE):
        source = source.replace(DOTENV_LOAD, DOTENV_LOAD +
                                '\nMODEL = os.getenv("TYPESAFE_DEFAULT_MODEL", "jev-latest")', 1)

    source = re.sub(r'model="(?:jev-latest|jev-1\.13\.0)"', "model=MODEL", source)
    source = re.sub(r'(api_key=API_KEY,\s*model=MODEL,)(?!\s*base_url=)',
                    r'\1 base_url=BASE_URL,', source)
    source = re.sub(r'(TypeSafeClient\(api_key=API_KEY,\s*model=MODEL)(\))',
                    r'\1, base_url=BASE_URL\2', source)
    source = source.replace('print("客户端已创建：模型=jev-latest，Key=",',
                            'print("客户端已创建：模型=", MODEL, "，Key=",')
    return source


def get_source(cell: dict) -> str:
    source = cell.get("source", "")
    return source if isinstance(source, str) else "".join(source)


def set_source(cell: dict, source: str) -> None:
    if isinstance(cell.get("source"), str):
        cell["source"] = source
    else:
        cell["source"] = source.splitlines(keepends=True)


def main() -> None:
    updated = 0
    for path in TARGETS:
        notebook = json.loads(path.read_text(encoding="utf-8"))
        changed = False
        for cell in notebook["cells"]:
            if cell["cell_type"] == "code":
                old_source = get_source(cell)
                new_source = configure(old_source)
                if new_source != old_source:
                    set_source(cell, new_source)
                    cell["outputs"] = []
                    cell["execution_count"] = None
                    changed = True
        for cell in notebook["cells"]:
            if cell["cell_type"] == "code" and "%pip install" in get_source(cell):
                old_source = get_source(cell)
                new_source = (re.sub(r"(typesafe-sdk(?:==[\w.]+)?)", r"\1 python-dotenv",
                                     old_source, count=1)
                              if "python-dotenv" not in old_source else old_source)
                new_source = new_source.replace(
                    'if importlib.util.find_spec("typesafe_sdk") is None:',
                    'if importlib.util.find_spec("typesafe_sdk") is None or importlib.util.find_spec("dotenv") is None:',
                )
                if new_source != old_source:
                    set_source(cell, new_source)
                    cell["outputs"] = []
                    cell["execution_count"] = None
                    changed = True
        if changed:
            nbformat.validate(nbformat.reads(json.dumps(notebook, ensure_ascii=False), as_version=4))
            path.write_text(json.dumps(notebook, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
            updated += 1
    print(f"已更新 {updated} 个 Notebook 的环境配置。")


if __name__ == "__main__":
    main()
