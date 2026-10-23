"""Cliente mínimo de la Bot API de Telegram (canales y grupos con temas)."""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any

import httpx

log = logging.getLogger(__name__)


class TelegramError(RuntimeError):
    pass


class Telegram:
    def __init__(self, token: str, chat_id: str, client: httpx.Client | None = None):
        if not token or not chat_id:
            raise TelegramError("Faltan TELEGRAM_BOT_TOKEN o TELEGRAM_CHANNEL")
        self.base = f"https://api.telegram.org/bot{token}"
        self.chat_id = chat_id
        self.client = client or httpx.Client(timeout=60)

    def _call(self, method: str, data: dict[str, Any] | None = None, files: dict | None = None) -> Any:
        for _ in range(5):
            r = self.client.post(f"{self.base}/{method}", data=data, files=files)
            body = r.json()
            if body.get("ok"):
                return body["result"]
            retry = (body.get("parameters") or {}).get("retry_after")
            if r.status_code == 429 and retry:
                log.info("Telegram pide esperar %ss", retry)
                time.sleep(int(retry) + 1)
                continue
            raise TelegramError(f"{method}: {body.get('description')}")
        raise TelegramError(f"{method}: demasiados reintentos")

    def _base(self, thread: int | None) -> dict[str, Any]:
        data: dict[str, Any] = {"chat_id": self.chat_id}
        if thread:
            data["message_thread_id"] = thread
        return data

    # --- información ---
    def get_chat(self) -> dict[str, Any]:
        return self._call("getChat", {"chat_id": self.chat_id})

    def is_forum(self) -> bool:
        return bool(self.get_chat().get("is_forum"))

    # --- temas ---
    def create_topic(self, name: str, icon_color: int | None = None) -> int:
        data: dict[str, Any] = {"chat_id": self.chat_id, "name": name}
        if icon_color:
            data["icon_color"] = icon_color
        return self._call("createForumTopic", data)["message_thread_id"]

    # --- envío ---
    def send_message(self, html: str, reply_to: int | None = None, disable_preview: bool = True,
                     thread: int | None = None) -> int:
        data = self._base(thread) | {
            "text": html,
            "parse_mode": "HTML",
            "link_preview_options": json.dumps({"is_disabled": disable_preview}),
        }
        if reply_to:
            data["reply_parameters"] = json.dumps({"message_id": reply_to, "allow_sending_without_reply": True})
        return self._call("sendMessage", data)["message_id"]

    def send_photo(self, path: Path, caption: str = "", thread: int | None = None) -> int:
        with open(path, "rb") as fh:
            res = self._call(
                "sendPhoto",
                self._base(thread) | {"caption": caption, "parse_mode": "HTML"},
                files={"photo": (path.name, fh, "image/png")},
            )
        return res["message_id"]

    def send_album(self, paths: list[Path], caption: str = "", thread: int | None = None) -> list[int]:
        """Envía hasta 10 imágenes como álbum; el caption va en la primera."""
        paths = paths[:10]
        if len(paths) == 1:
            return [self.send_photo(paths[0], caption, thread)]
        media, files, handles = [], {}, []
        try:
            for i, p in enumerate(paths):
                key = f"f{i}"
                fh = open(p, "rb")
                handles.append(fh)
                files[key] = (p.name, fh, "image/jpeg")
                entry = {"type": "photo", "media": f"attach://{key}"}
                if i == 0 and caption:
                    entry |= {"caption": caption, "parse_mode": "HTML"}
                media.append(entry)
            res = self._call("sendMediaGroup", self._base(thread) | {"media": json.dumps(media)}, files=files)
        finally:
            for fh in handles:
                fh.close()
        return [m["message_id"] for m in res]

    # --- edición ---
    def edit_message(self, message_id: int, html: str) -> None:
        try:
            self._call("editMessageText", {
                "chat_id": self.chat_id, "message_id": message_id, "text": html, "parse_mode": "HTML",
                "link_preview_options": json.dumps({"is_disabled": True}),
            })
        except TelegramError as e:
            if "message is not modified" not in str(e):
                raise

    def edit_photo(self, message_id: int, path: Path, caption: str = "") -> None:
        media = {"type": "photo", "media": "attach://f0", "caption": caption, "parse_mode": "HTML"}
        with open(path, "rb") as fh:
            try:
                self._call("editMessageMedia",
                           {"chat_id": self.chat_id, "message_id": message_id, "media": json.dumps(media)},
                           files={"f0": (path.name, fh, "image/png")})
            except TelegramError as e:
                if "message is not modified" not in str(e):
                    raise

    def delete_message(self, message_id: int) -> None:
        self._call("deleteMessage", {"chat_id": self.chat_id, "message_id": message_id})

    def pin(self, message_id: int) -> None:
        self._call("pinChatMessage", {"chat_id": self.chat_id, "message_id": message_id, "disable_notification": True})

    def notify(self, chat_id: str, text: str) -> None:
        self._call("sendMessage", {"chat_id": chat_id, "text": text[:4000]})
