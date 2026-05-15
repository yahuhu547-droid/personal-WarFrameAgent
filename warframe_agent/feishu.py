"""飞书机器人模块 — WebSocket 长连接模式，无需公网 IP。"""

from __future__ import annotations

import json
import logging
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import lark_oapi as lark
from lark_oapi.api.im.v1 import CreateMessageRequest, CreateMessageRequestBody, ReplyMessageRequest, ReplyMessageRequestBody

from . import config

logger = logging.getLogger(__name__)


@dataclass
class FeishuConfig:
    enabled: bool = False
    app_id: str = ""
    app_secret: str = ""

    def save(self, path: Path = config.FEISHU_CONFIG_PATH):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.__dict__, ensure_ascii=False, indent=2), encoding="utf-8")

    @classmethod
    def load(cls, path: Path = config.FEISHU_CONFIG_PATH) -> "FeishuConfig":
        if not path.exists():
            return cls()
        try:
            data = json.loads(path.read_text(encoding="utf-8-sig"))
            return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
        except Exception:
            return cls()


class FeishuBot:
    def __init__(self, cfg: FeishuConfig, on_message: Callable[[str, str], str] | None = None):
        self.cfg = cfg
        self.on_message = on_message  # (user_text, message_id) -> reply_text
        self._client: lark.Client | None = None
        self._ws_proc: subprocess.Popen | None = None
        self._log_file = None

    @property
    def available(self) -> bool:
        return self.cfg.enabled and bool(self.cfg.app_id) and bool(self.cfg.app_secret)

    def _ensure_client(self) -> lark.Client:
        if self._client is None:
            self._client = lark.Client.builder() \
                .app_id(self.cfg.app_id) \
                .app_secret(self.cfg.app_secret) \
                .log_level(lark.LogLevel.WARNING) \
                .build()
        return self._client

    def reply(self, message_id: str, text: str) -> bool:
        try:
            client = self._ensure_client()
            body = CreateMessageRequestBody.builder() \
                .msg_type("text") \
                .content(json.dumps({"text": text})) \
                .receive_id(message_id) \
                .build()
            request = CreateMessageRequest.builder() \
                .receive_id_type("message_id") \
                .request_body(body) \
                .build()
            response = client.im.v1.message.reply(request)
            if response.success():
                logger.info("飞书回复成功: %s", message_id)
                return True
            logger.warning("飞书回复失败: code=%s msg=%s", response.code, response.msg)
            return False
        except Exception as exc:
            logger.warning("飞书回复异常: %s", exc)
            return False

    def send(self, chat_id: str, text: str) -> bool:
        try:
            client = self._ensure_client()
            body = CreateMessageRequestBody.builder() \
                .msg_type("text") \
                .content(json.dumps({"text": text})) \
                .receive_id(chat_id) \
                .build()
            request = CreateMessageRequest.builder() \
                .receive_id_type("chat_id") \
                .request_body(body) \
                .build()
            response = client.im.v1.message.create(request)
            if response.success():
                logger.info("飞书发送成功: %s", chat_id)
                return True
            logger.warning("飞书发送失败: code=%s msg=%s", response.code, response.msg)
            return False
        except Exception as exc:
            logger.warning("飞书发送异常: %s", exc)
            return False

    def send_card(self, chat_id: str, title: str, elements: list[dict]) -> bool:
        """发送飞书交互式卡片消息。

        Args:
            chat_id: 会话 ID
            title: 卡片标题
            elements: 卡片元素列表，支持:
                - {"tag": "div", "text": {"tag": "plain_text", "content": "文本"}}
                - {"tag": "hr"} — 分割线
                - {"tag": "div", "fields": [{"is_short": True, "text": {"tag": "plain_text", "content": "key: value"}}]}
        """
        try:
            card = {
                "config": {"wide_screen_mode": True},
                "header": {
                    "title": {"tag": "plain_text", "content": title},
                    "template": "blue",
                },
                "elements": elements,
            }
            client = self._ensure_client()
            body = CreateMessageRequestBody.builder() \
                .msg_type("interactive") \
                .content(json.dumps(card, ensure_ascii=False)) \
                .receive_id(chat_id) \
                .build()
            request = CreateMessageRequest.builder() \
                .receive_id_type("chat_id") \
                .request_body(body) \
                .build()
            response = client.im.v1.message.create(request)
            if response.success():
                logger.info("飞书卡片发送成功: %s", chat_id)
                return True
            logger.warning("飞书卡片发送失败: code=%s msg=%s", response.code, response.msg)
            return False
        except Exception as exc:
            logger.warning("飞书卡片发送异常: %s", exc)
            return False

    def reply_card(self, message_id: str, title: str, elements: list[dict]) -> bool:
        """回复飞书卡片消息。"""
        try:
            card = {
                "config": {"wide_screen_mode": True},
                "header": {
                    "title": {"tag": "plain_text", "content": title},
                    "template": "blue",
                },
                "elements": elements,
            }
            client = self._ensure_client()
            body = ReplyMessageRequestBody.builder() \
                .msg_type("interactive") \
                .content(json.dumps(card, ensure_ascii=False)) \
                .build()
            request = ReplyMessageRequest.builder() \
                .message_id(message_id) \
                .request_body(body) \
                .build()
            response = client.im.v1.message.reply(request)
            if response.success():
                logger.info("飞书卡片回复成功: %s", message_id)
                return True
            logger.warning("飞书卡片回复失败: code=%s msg=%s", response.code, response.msg)
            return False
        except Exception as exc:
            logger.warning("飞书卡片回复异常: %s", exc)
            return False

    def _handle_message(self, data) -> None:
        """处理接收到的消息"""
        try:
            msg = data.event.message
            msg_type = msg.message_type
            message_id = msg.message_id

            if msg_type != "text":
                return

            content = json.loads(msg.content)
            user_text = content.get("text", "").strip()
            if not user_text:
                return

            # 去掉 @机器人 的前缀
            if user_text.startswith("@"):
                parts = user_text.split(" ", 1)
                user_text = parts[1].strip() if len(parts) > 1 else ""

            if not user_text:
                return

            logger.info("飞书收到消息: %s", user_text[:50])

            if self.on_message:
                reply_text = self.on_message(user_text, message_id)
                if reply_text:
                    self.reply(message_id, reply_text)

        except Exception as exc:
            logger.warning("飞书消息处理异常: %s", exc)

    def start(self) -> None:
        """启动 WebSocket 长连接（独立子进程）"""
        if not self.available:
            logger.warning("飞书机器人未配置，无法启动")
            return
        # 先杀掉旧的 worker 进程，防止重复
        self._kill_old_workers()
        if self._ws_proc and self._ws_proc.poll() is None:
            return

        script = _FEISHU_WORKER_SCRIPT.format(
            app_id=self.cfg.app_id,
            app_secret=self.cfg.app_secret,
            data_dir=str(config.DATA_DIR).replace("\\", "\\\\"),
        )
        log_path = config.DATA_DIR / "feishu_worker.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        self._log_file = open(log_path, "a", encoding="utf-8")
        self._ws_proc = subprocess.Popen(
            [sys.executable, "-c", script],
            stdout=self._log_file,
            stderr=subprocess.STDOUT,
        )
        logger.info("飞书 WebSocket 子进程已启动 (pid=%s)", self._ws_proc.pid)

    def stop(self) -> None:
        """停止 WebSocket 连接"""
        if self._ws_proc and self._ws_proc.poll() is None:
            self._ws_proc.terminate()
            try:
                self._ws_proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._ws_proc.kill()
        if self._log_file:
            try:
                self._log_file.close()
            except Exception:
                pass
            self._log_file = None
        logger.info("飞书 WebSocket 子进程已停止")

    def _kill_old_workers(self) -> None:
        """杀掉所有旧的飞书 worker 子进程，防止重复响应。"""
        try:
            result = subprocess.run(
                ["wmic", "process", "where", "name='python.exe'", "get", "ProcessId,CommandLine"],
                capture_output=True, text=True, timeout=5,
            )
            current_pid = str(self._ws_proc.pid) if self._ws_proc else ""
            for line in result.stdout.splitlines():
                if "lark_oapi" in line and "P2ImMessageReceiveV1" in line:
                    # 提取 PID（最后一列数字）
                    parts = line.strip().split()
                    if parts:
                        pid = parts[-1]
                        if pid != current_pid and pid.isdigit():
                            subprocess.run(["taskkill", "/F", "/PID", pid], capture_output=True, timeout=5)
                            logger.info("杀掉旧飞书 worker 进程: pid=%s", pid)
        except Exception as exc:
            logger.debug("清理旧进程失败: %s", exc)


_FEISHU_WORKER_SCRIPT = '''
import json
import sys
import time
import threading
from pathlib import Path
import lark_oapi as lark
from lark_oapi.api.im.v1 import ReplyMessageRequest, ReplyMessageRequestBody, CreateMessageRequest, CreateMessageRequestBody
from lark_oapi.api.im.v1.model import P2ImMessageReceiveV1

APP_ID = "{app_id}"
APP_SECRET = "{app_secret}"
API_URL = "http://127.0.0.1:8000/api/chat"
DATA_DIR = r"{data_dir}"

_client = None
_service_start_ms = int(time.time() * 1000)  # 服务启动时间（毫秒）

# 消息去重：持久化到磁盘，重启后仍有效
_processed_lock = threading.Lock()
_DEDUP_TTL = 600  # 10 分钟
_DEDUP_FILE = Path(DATA_DIR) / "feishu_processed_ids.json"

def _load_processed_ids() -> dict[str, float]:
    try:
        if _DEDUP_FILE.exists():
            data = json.loads(_DEDUP_FILE.read_text(encoding="utf-8"))
            # 清理过期条目
            now = time.time()
            return {{k: v for k, v in data.items() if now - v < _DEDUP_TTL}}
    except Exception:
        pass
    return {{}}

def _save_processed_ids(ids: dict[str, float]) -> None:
    try:
        _DEDUP_FILE.parent.mkdir(parents=True, exist_ok=True)
        _DEDUP_FILE.write_text(json.dumps(ids), encoding="utf-8")
    except Exception:
        pass

_processed_ids: dict[str, float] = _load_processed_ids()

def _is_duplicate(message_id: str, create_time_ms: int = 0) -> bool:
    # 关键：拒绝启动前创建的旧消息
    if create_time_ms > 0 and create_time_ms < _service_start_ms:
        return True
    now = time.time()
    with _processed_lock:
        # 清理过期条目
        expired = [k for k, t in _processed_ids.items() if now - t > _DEDUP_TTL]
        for k in expired:
            del _processed_ids[k]
        if message_id in _processed_ids:
            return True
        _processed_ids[message_id] = now
        # 定期持久化（每 10 条）
        if len(_processed_ids) % 10 == 0:
            _save_processed_ids(_processed_ids)
        return False

def get_client():
    global _client
    if _client is None:
        _client = lark.Client.builder().app_id(APP_ID).app_secret(APP_SECRET).log_level(lark.LogLevel.WARNING).build()
    return _client

def on_message(data: P2ImMessageReceiveV1):
    try:
        msg = data.event.message
        message_id = msg.message_id
        create_time_ms = int(msg.create_time or "0")

        # 消息去重 + 旧消息过滤
        if _is_duplicate(message_id, create_time_ms):
            return

        # 过滤机器人自身消息
        sender = getattr(data.event, 'sender', None)
        if sender and getattr(sender, 'sender_type', '') == 'app':
            return

        # 保存 chat_id 用于主动推送
        chat_id = msg.chat_id
        if chat_id:
            try:
                chat_id_path = DATA_DIR / "feishu_chat_id.txt"
                chat_id_path.parent.mkdir(parents=True, exist_ok=True)
                chat_id_path.write_text(chat_id, encoding="utf-8")
            except Exception:
                pass
        if msg.message_type != "text":
            return
        content = json.loads(msg.content)
        user_text = content.get("text", "").strip()
        if user_text.startswith("@"):
            parts = user_text.split(" ", 1)
            user_text = parts[1].strip() if len(parts) > 1 else ""
        if not user_text:
            return
        print(f"[feishu] 收到: {{user_text[:50]}}", flush=True)
        import requests
        resp = requests.post(API_URL, json={{"message": user_text}}, timeout=120)
        reply_text = resp.json().get("reply", "处理异常")
        reply(message_id, reply_text)
    except Exception as e:
        print(f"[feishu] 异常: {{e}}", flush=True)

def reply(message_id, text):
    try:
        client = get_client()
        body = ReplyMessageRequestBody.builder().msg_type("text").content(json.dumps({{"text": text}})).build()
        req = ReplyMessageRequest.builder().message_id(message_id).request_body(body).build()
        resp = client.im.v1.message.reply(req)
        if resp.success():
            print(f"[feishu] 回复成功: {{message_id}}", flush=True)
        else:
            print(f"[feishu] 回复失败: {{resp.msg}}", flush=True)
    except Exception as e:
        print(f"[feishu] 回复异常: {{e}}", flush=True)

def send(chat_id, text):
    try:
        client = get_client()
        body = CreateMessageRequestBody.builder().msg_type("text").content(json.dumps({{"text": text}})).receive_id(chat_id).build()
        req = CreateMessageRequest.builder().receive_id_type("chat_id").request_body(body).build()
        resp = client.im.v1.message.create(req)
        if resp.success():
            print(f"[feishu] 发送成功: {{chat_id}}", flush=True)
        else:
            print(f"[feishu] 发送失败: {{resp.msg}}", flush=True)
    except Exception as e:
        print(f"[feishu] 发送异常: {{e}}", flush=True)

def _on_raw(data):
    """调试：捕获所有事件"""
    print(f"[feishu] 收到原始事件: {{type(data).__name__}}", flush=True)
    on_message(data)

handler = lark.EventDispatcherHandler.builder("", "").register_p2_im_message_receive_v1(_on_raw).build()
ws = lark.ws.Client(app_id=APP_ID, app_secret=APP_SECRET, event_handler=handler, log_level=lark.LogLevel.DEBUG)
print("[feishu] WebSocket 启动...", flush=True)
ws.start()
'''


def build_price_card(title: str, fields: dict[str, str], footer: str = "") -> list[dict]:
    """构建价格查询卡片元素。

    Args:
        title: 物品名
        fields: {"最低卖价": "45p", "最高收价": "35p", ...}
        footer: 底部附加文本
    """
    elements = []
    # 字段（每行两个）
    field_list = []
    for key, value in fields.items():
        field_list.append({
            "is_short": True,
            "text": {"tag": "lark_md", "content": f"**{key}**\n{value}"},
        })
    # 每 2 个字段一组
    for i in range(0, len(field_list), 2):
        chunk = field_list[i:i + 2]
        elements.append({"tag": "div", "fields": chunk})
    if footer:
        elements.append({"tag": "hr"})
        elements.append({"tag": "div", "text": {"tag": "lark_md", "content": footer}})
    return elements
