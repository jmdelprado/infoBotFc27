"""Telegram de mentira para --dry-run / preview: guarda los mensajes y genera out/preview.html,
agrupados por sección como se verían en el grupo con temas."""

from __future__ import annotations

import shutil
from datetime import datetime
from html import escape
from pathlib import Path

from .config import OUT_DIR

GENERAL = "📌 General"


class Outbox:
    def __init__(self, out_dir: Path = OUT_DIR):
        self.out_dir = out_dir
        self.img_dir = out_dir / "img"
        self.img_dir.mkdir(parents=True, exist_ok=True)
        self.entries: list[dict] = []
        self.topics: dict[int, str] = {}
        self._next = 1
        self.pinned: set[int] = set()

    def _id(self) -> int:
        self._next += 1
        return self._next

    def _copy(self, p: Path) -> str:
        dest = self.img_dir / p.name
        if p.resolve() != dest.resolve():
            shutil.copy(p, dest)
        return f"img/{p.name}?v={self._next}"

    def _topic(self, thread: int | None) -> str:
        return self.topics.get(thread or 0, GENERAL)

    def is_forum(self) -> bool:
        return True

    def create_topic(self, name: str, icon_color: int | None = None) -> int:
        tid = 1000 + len(self.topics)
        self.topics[tid] = name
        return tid

    def send_album(self, paths: list[Path], caption: str = "", thread: int | None = None) -> list[int]:
        ids = [self._id() for _ in paths[:10]]
        self.entries.append({"type": "album", "imgs": [self._copy(p) for p in paths[:10]], "caption": caption,
                             "id": ids[0], "topic": self._topic(thread)})
        return ids

    def send_photo(self, path: Path, caption: str = "", thread: int | None = None) -> int:
        return self.send_album([path], caption, thread)[0]

    def send_message(self, html: str, reply_to: int | None = None, disable_preview: bool = True,
                     thread: int | None = None) -> int:
        mid = self._id()
        self.entries.append({"type": "text", "html": html, "id": mid, "topic": self._topic(thread)})
        return mid

    def edit_message(self, message_id: int, html: str) -> None:
        for e in self.entries:
            if e["id"] == message_id:
                e["html"] = html

    def edit_photo(self, message_id: int, path: Path, caption: str = "") -> None:
        for e in self.entries:
            if e["id"] == message_id:
                e["imgs"], e["caption"] = [self._copy(path)], caption

    def delete_message(self, message_id: int) -> None:
        self.entries = [e for e in self.entries if e["id"] != message_id]

    def pin(self, message_id: int) -> None:
        self.pinned.add(message_id)

    def notify(self, chat_id: str, text: str) -> None:
        self.entries.append({"type": "text", "html": f"<b>[aviso al propietario]</b> {escape(text)}",
                             "id": self._id(), "topic": GENERAL})

    def _render_entry(self, e: dict) -> str:
        pin = '<span class="pin">📌 FIJADO</span><br>' if e["id"] in self.pinned else ""
        if e["type"] == "album":
            imgs = "".join(f'<img src="{escape(s)}">' for s in e["imgs"])
            cap = f'<div class="txt">{pin}{e["caption"].replace(chr(10), "<br>")}</div>' if e["caption"] or pin else ""
            cls = "album" if len(e["imgs"]) > 1 else "album one"
            return f'<div class="msg"><div class="{cls}">{imgs}</div>{cap}</div>'
        return f'<div class="msg"><div class="txt">{pin}{e["html"].replace(chr(10), "<br>")}</div></div>'

    def write_html(self, title: str = "InfoBot FC 27 — vista previa") -> Path:
        order = [GENERAL] + list(self.topics.values())
        groups: dict[str, list[str]] = {}
        for e in self.entries:
            groups.setdefault(e["topic"], []).append(self._render_entry(e))
        tabs, panes = [], []
        for i, name in enumerate(t for t in order if t in groups):
            tabs.append(f'<a href="#t{i}">{escape(name)} <small>{len(groups[name])}</small></a>')
            panes.append(f'<section id="t{i}"><h2>{escape(name)}</h2>{"".join(groups[name])}</section>')
        html = f"""<!doctype html><html lang="es"><meta charset="utf-8"><title>{escape(title)}</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
body{{margin:0;background:#0e1621;color:#e9eef4;font:15px/1.45 system-ui,-apple-system,"Segoe UI",sans-serif}}
header{{position:sticky;top:0;background:#17212b;padding:12px 16px;font-weight:700;border-bottom:1px solid #000;z-index:2}}
nav{{display:flex;flex-wrap:wrap;gap:6px;margin-top:8px}}
nav a{{background:#22303f;color:#cfe3f7;text-decoration:none;padding:4px 10px;border-radius:999px;font-weight:500;font-size:13px}}
main{{max-width:560px;margin:0 auto;padding:16px}}
h2{{font-size:16px;color:#8fb6dc;border-bottom:1px solid #22303f;padding-bottom:6px;margin:28px 0 12px}}
.msg{{background:#182533;border-radius:14px;margin:0 0 14px;overflow:hidden}}
.txt{{padding:10px 14px}}
.album{{display:grid;grid-template-columns:1fr 1fr;gap:2px}}
.album img{{width:100%;height:180px;object-fit:cover;display:block}}
.album img:first-child{{grid-column:1/-1;height:auto}}
.album.one{{grid-template-columns:1fr}}
blockquote{{margin:8px 0;padding:6px 10px;border-left:3px solid #6ab3f3;background:#1e2c3a;border-radius:6px}}
a{{color:#6ab3f3}} .pin{{color:#f5c542;font-size:12px}}
</style>
<header>{escape(title)} · {datetime.now():%d/%m/%Y %H:%M}<nav>{''.join(tabs)}</nav></header>
<main>{''.join(panes)}</main></html>"""
        path = self.out_dir / "preview.html"
        path.write_text(html, encoding="utf-8")
        return path
