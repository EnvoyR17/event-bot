import re

from html import escape

from config import ID_WIDTH


def format_id(pid: int) -> str:
    return str(pid).zfill(ID_WIDTH)


def parse_id(text: str) -> int | None:
    raw = (text or "").strip().replace("№", "").replace("#", "")
    raw = re.sub(r"^(id|ид)\s*[:.]?\s*", "", raw, flags=re.IGNORECASE)
    raw = raw.strip()
    if re.fullmatch(r"\d+", raw):
        return int(raw)
    return None


def staff_display_name(user) -> str:
    parts = [user.first_name or "", user.last_name or ""]
    name = " ".join(p for p in parts if p).strip()
    return name or (f"@{user.username}" if user.username else str(user.id))


def participant_card(p: dict, *, title: str | None = None) -> str:
    lines = []
    if title:
        lines.append(title)
    lines.append(f"<b>{escape(p['full_name'])}</b>")
    lines.append(f"ID  <code>{format_id(p['id'])}</code>")
    lines.append(f"Баллы: <b>{p['points']}</b>")
    return "\n".join(lines)
