"""Telegram de mentira para --dry-run / preview: guarda los mensajes y genera out/preview.html."""

from __future__ import annotations

import shutil
from datetime import datetime
from html import escape
from pathlib import Path

from .config import OUT_DIR


class Outbox:
    def __init__(self, out_dir: Path = OUT_DIR):
        self.out_dir = out_dir
        self.img_dir = out_dir / "img"
        self.img_dir.mkdir(parents=True, exist_ok=True)
        self.entries: list[dict] = []
        self._next = 1
        self.pinned: int | None = None

    def _id(self) -> int:
        self._next += 1
        return self._next

    def _copy(self, p: Path) -> str:
        dest = self.img_dir / p.name
        if p.resolve() != dest.resolve():
            shutil.copy(p, dest)
        return f"img/{p.name}"

    def send_album(self, paths: list[Path], caption: str = "") -> list[int]:
        ids = [self._id() for _ in paths[:10]]
        self.entries.append({"type": "album", "imgs": [self._copy(p) for p in paths[:10]], "caption": caption, "id": ids[0]})
        return ids

    def send_photo(self, path: Path, caption: str = "") -> int:
        return self.send_album([path], caption)[0]

    def send_message(self, html: str, reply_to: int | None = None, disable_preview: bool = True) -> int:
        mid = self._id()
        self.entries.append({"type": "text", "html": html, "id": mid})
        return mid

    def edit_message(self, message_id: int, html: str) -> None:
        for e in self.entries:
            if e["id"] == message_id:
                e["html"] = html
                return
        self.entries.append({"type": "text", "html": html, "id": message_id})

    def pin(self, message_id: int) -> None:
        self.pinned = message_id

    def notify(self, chat_id: str, text: str) -> None:
        self.entries.append({"type": "text", "html": f"<b>[aviso al propietario]</b> {escape(text)}", "id": self._id()})

    def write_html(self, title: str = "InfoBot FC 27 — vista previa") -> Path:
        blocks = []
        for e in self.entries:
            pin = ' <span class="pin">📌 FIJADO</span>' if e["id"] == self.pinned else ""
            if e["type"] == "album":
                imgs = "".join(f'<img src="{escape(s)}">' for s in e["imgs"])
                cap = f'<div class="txt">{e["caption"].replace(chr(10), "<br>")}</div>' if e["caption"] else ""
                cls = "album" if len(e["imgs"]) > 1 else "album one"
                blocks.append(f'<div class="msg"><div class="{cls}">{imgs}</div>{cap}</div>')
            else:
                blocks.append(f'<div class="msg"><div class="txt">{pin}{e["html"].replace(chr(10), "<br>")}</div></div>')
        html = f"""<!doctype html><html lang="es"><meta charset="utf-8"><title>{escape(title)}</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
body{{margin:0;background:#0e1621;color:#e9eef4;font:15px/1.45 system-ui,-apple-system,"Segoe UI",sans-serif}}
header{{position:sticky;top:0;background:#17212b;padding:12px 16px;font-weight:700;border-bottom:1px solid #000}}
main{{max-width:560px;margin:0 auto;padding:16px}}
.msg{{background:#182533;border-radius:14px;margin:0 0 14px;overflow:hidden}}
.txt{{padding:10px 14px}}
.album{{display:grid;grid-template-columns:1fr 1fr;gap:2px}}
.album img{{width:100%;height:180px;object-fit:cover;display:block}}
.album img:first-child{{grid-column:1/-1;height:auto}}
.album.one{{grid-template-columns:1fr}}
blockquote{{margin:8px 0;padding:6px 10px;border-left:3px solid #6ab3f3;background:#1e2c3a;border-radius:6px;white-space:normal}}
a{{color:#6ab3f3}} .pin{{color:#f5c542;font-size:12px}}
</style>
<header>{escape(title)} · {datetime.now():%d/%m/%Y %H:%M}</header><main>{''.join(blocks)}</main></html>"""
        path = self.out_dir / "preview.html"
        path.write_text(html, encoding="utf-8")
        return path
