"""数独实时解题台：只调用配置的 Jev，保存实际 HTTP 报文，暂停使在途落子失效。"""
from __future__ import annotations

import argparse
import copy
import json
import os
import sys
import threading
import time
import uuid
import webbrowser
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

import httpx2
from typesafe_sdk import RetryPolicy, TypeSafeClient

HERE = Path(__file__).resolve().parent
MAIN = HERE.parents[2]
sys.path.insert(0, str(MAIN))
from notebook_runtime import load_project_env
import sudoku_game as S

CASES = [
    {"id": "warmup", "title": "入门 · 12 空格", "seed": 1, "holes": 12},
    {"id": "standard", "title": "标准 · 40 空格", "seed": 7, "holes": 40},
    {"id": "challenge", "title": "挑战 · 55 空格", "seed": 11, "holes": 55},
]


class InputError(Exception):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


class JevGateway:
    """在 HTTP 读写边界采集报文，避免用 SDK 解析结果替代原始响应。"""
    def __init__(self, *, transport=None):
        load_project_env(MAIN.parent)
        self.key = os.getenv("TYPESAFE_API_KEY", "").strip()
        self.model = os.getenv("TYPESAFE_DEFAULT_MODEL", "jev-1.13.0")
        self.base_url = os.getenv("TYPESAFE_BASE_URL") or "https://api.typesafe.ai"
        self.transport = transport

    def public_config(self):
        return {"model": self.model, "base_url": self.base_url,
                "configured": bool(self.key), "source": "main/.env / 进程环境",
                "cases": CASES}

    def redact(self, value):
        if isinstance(value, str):
            return value.replace(self.key, "[REDACTED]") if self.key else value
        if isinstance(value, dict):
            return {k: self.redact(v) for k, v in value.items()}
        if isinstance(value, (list, tuple)):
            return [self.redact(v) for v in value]
        return value

    def decide(self, request, trace):
        if not self.key:
            raise InputError("请在 main/.env 配置 TYPESAFE_API_KEY；本应用不使用离线替身。", 503)

        def headers(items):
            return [[k, "[REDACTED]" if k.lower() in {"authorization", "cookie", "set-cookie"} else v]
                    for k, v in items.multi_items()]

        def body(raw):
            text = raw.decode("utf-8", errors="replace")
            try:
                parsed = json.loads(text)
            except ValueError:
                parsed = None
            return {"body": parsed, "body_text": text}

        def sent(req):
            trace["request"] = self.redact({"method": req.method, "url": str(req.url),
                "headers": headers(req.headers), **body(req.content)})

        def received(resp):
            resp.read()
            trace["response"] = self.redact({"status": resp.status_code,
                "http_version": resp.http_version, "headers": headers(resp.headers), **body(resp.content)})

        # 不自动重试，页面中一条记录对应一次请求。取消压缩后正文可直接核对。
        with httpx2.Client(transport=self.transport, timeout=30,
                           event_hooks={"request": [sent], "response": [received]}) as http:
            with TypeSafeClient(api_key=self.key, model=self.model, base_url=self.base_url,
                                http_client=http, compression=False,
                                retry=RetryPolicy(max_retries=0)) as client:
                response = client.system_one(request["state"], request["questions"])
                digit = str(response.choices["digit"].choice)
                if digit not in {str(i) for i in S.DIGITS}:
                    raise ValueError("模型未返回 1–9 的合法数字")
                return int(digit)


@dataclass
class Game:
    case: dict
    state: dict
    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    running: bool = False
    busy: bool = False
    epoch: int = 0
    history: list = field(default_factory=list)
    wrong: dict = field(default_factory=dict)
    lock: threading.Lock = field(default_factory=threading.Lock)

    def snapshot(self):
        # solution、givens 的内部校验信息不进入报文；前端只获取公开棋盘。
        return copy.deepcopy({"id": self.id, "case": self.case, "grid": self.state["grid"],
            "givens": self.state["givens"], "holes": sum(not v for row in self.state["givens"] for v in row),
            "steps": self.state["steps"], "score": self.state["score"],
            "mistakes": self.state["mistakes"], "done": self.state["done"],
            "outcome": self.state["outcome"], "running": self.running, "busy": self.busy,
            "next": None if self.state["done"] else S.render_request(self.state), "history": self.history})


class SudokuApp:
    def __init__(self, gateway):
        self.gateway = gateway
        self.games = {}
        self.lock = threading.Lock()
        # 引擎的确定性生成器有共享 RNG 临时状态，生成必须串行。
        self.generation_lock = threading.Lock()

    def game(self, game_id):
        with self.lock:
            game = self.games.get(game_id)
        if game is None:
            raise InputError("此对局不存在，请重新选择题目。", 404)
        return game

    def create(self, data):
        case = next((dict(c) for c in CASES if c["id"] == data.get("case_id", "warmup")), None)
        if data.get("case_id") == "custom":
            seed, holes = data.get("seed"), data.get("holes")
            if type(seed) is not int or not 0 <= seed <= 2**32 - 1 or type(holes) is not int or not 1 <= holes <= 55:
                raise InputError("自定义 seed 需为 0–4294967295 的整数，空格数需为 1–55 的整数。")
            case = {"id": "custom", "title": f"自定义 · seed {seed}", "seed": seed, "holes": holes}
        if case is None:
            raise InputError("未知数独 case")
        previous = data.get("previous_game")
        if previous:
            self.control(previous, {"action": "pause"})
        with self.generation_lock:
            state = S.make_sudoku(case["seed"], case["holes"])
        game = Game(case=case, state=state)
        with self.lock:
            if len(self.games) >= 64:
                # 只释放已暂停且没有在途请求的旧会话。
                disposable = next((g.id for g in self.games.values() if not g.busy and not g.running), None)
                if disposable is None:
                    raise InputError("对局过多，请暂停旧对局后再创建。", 409)
                del self.games[disposable]
            self.games[game.id] = game
        return game.snapshot()

    def control(self, game_id, data):
        game = self.game(game_id)
        action = data.get("action")
        if action not in {"run", "pause"}:
            raise InputError("操作只能是 run 或 pause")
        with game.lock:
            if action == "run" and game.state["done"]:
                raise InputError("本局已结束，请切换题目或重新开局。", 409)
            game.running = action == "run"
            if action == "pause":
                game.epoch += 1  # 已发出的 HTTP 请求仍会返回，但不得再修改棋盘。
            return game.snapshot()

    def advance(self, game_id, data):
        game = self.game(game_id)
        with game.lock:
            if game.busy or game.state["done"]:
                raise InputError("正在请求或本局已结束", 409)
            if data.get("expected_steps") != game.state["steps"]:
                raise InputError("棋盘已变化，请刷新后重试。", 409)
            if not game.running and data.get("single") is not True:
                raise InputError("对局已暂停", 409)
            if not self.gateway.key:
                raise InputError("请在 main/.env 配置 TYPESAFE_API_KEY；没有离线回退。", 503)
            game.busy = True
            epoch = game.epoch
            request = S.render_request(game.state)
            r, c = request["cell"]
            tried = game.wrong.get((r, c), [])
            if tried:
                request["state"] += "\n此格已经尝试且证错的数字：" + ", ".join(map(str, tried)) + "，请勿重复。"
            trace = {"id": len(game.history) + 1, "cell": request["cell"],
                     "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                     "request": None, "response": None, "applied": False}
        started = time.perf_counter()
        digit, error = None, None
        try:
            digit = self.gateway.decide(request, trace)
        except Exception as exc:
            # 错误响应原文保存在 trace；简短状态文字不回显 SDK 异常携带的敏感信息。
            error = "请求失败（" + type(exc).__name__ + "），请检查下方实际响应。"
        with game.lock:
            game.busy = False
            trace["latency_ms"] = round((time.perf_counter() - started) * 1000, 1)
            trace["digit"] = digit
            if error:
                trace["error"] = error
                game.running = False
            elif game.epoch != epoch:
                trace["note"] = "请求期间已暂停或切换题目，此响应保留供查看，未落子。"
            else:
                old_score = game.state["score"]
                game.state = S.step(game.state, digit)
                trace.update(applied=True, correct=game.state["score"] > old_score)
                if not trace["correct"]:
                    game.wrong.setdefault((r, c), []).append(digit)
                if game.state["done"]:
                    game.running = False
            game.history.append(self.gateway.redact(trace))
            return game.snapshot()


def handler_for(app):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def reply(self, status, data, content_type="application/json; charset=utf-8"):
            raw = data if isinstance(data, bytes) else json.dumps(data, ensure_ascii=False).encode()
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(raw)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(raw)

        def do_GET(self):
            path = urlsplit(self.path).path
            if path in {"/", "/sudoku_replay.html"}:
                self.reply(200, (HERE / "sudoku_replay.html").read_bytes(), "text/html; charset=utf-8")
            elif path in {"/sudoku.js", "/sudoku.css"}:
                self.reply(200, (HERE / path[1:]).read_bytes(), "text/javascript; charset=utf-8" if path.endswith(".js") else "text/css; charset=utf-8")
            elif path == "/api/config":
                self.reply(200, app.gateway.public_config())
            elif path.startswith("/api/games/"):
                try:
                    game = app.game(path.split("/")[-1])
                    with game.lock:
                        self.reply(200, game.snapshot())
                except InputError as exc:
                    self.reply(exc.status, {"error": str(exc)})
            else:
                self.reply(404, {"error": "页面不存在"})

        def do_POST(self):
            try:
                origin = self.headers.get("Origin")
                if origin and urlsplit(origin).netloc != self.headers.get("Host"):
                    raise InputError("请从本应用页面发起操作。", 403)
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= 8192:
                    raise InputError("请求大小无效")
                data = json.loads(self.rfile.read(length))
                if not isinstance(data, dict):
                    raise InputError("请求必须是 JSON 对象")
                parts = urlsplit(self.path).path.strip("/").split("/")
                if parts == ["api", "games"]:
                    result = app.create(data)
                elif len(parts) == 4 and parts[:2] == ["api", "games"] and parts[3] in {"control", "step"}:
                    result = (app.control if parts[3] == "control" else app.advance)(parts[2], data)
                else:
                    raise InputError("接口不存在", 404)
                self.reply(200, result)
            except InputError as exc:
                self.reply(exc.status, {"error": str(exc)})
            except (ValueError, TypeError):
                self.reply(400, {"error": "请求格式无效"})
            except Exception:
                self.reply(500, {"error": "服务内部错误，请查看运行环境。"})
    return Handler


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8803)
    parser.add_argument("--no-open", action="store_true")
    args = parser.parse_args()
    app = SudokuApp(JevGateway())
    server = ThreadingHTTPServer((args.host, args.port), handler_for(app))
    print(f"数独实时解题台：http://{args.host}:{server.server_port} · 模型 {app.gateway.model}", flush=True)
    if not args.no_open:
        webbrowser.open(f"http://{args.host}:{server.server_port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
