from pathlib import Path

from openpyxl import Workbook

from config import DATA_DIR
from db import list_participants_by_points
from utils import format_id


async def build_excel() -> Path:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    path = DATA_DIR / "report.xlsx"
    rows = await list_participants_by_points()
    wb = Workbook()
    ws = wb.active
    ws.title = "Участники"
    ws.append(["ФИО", "ID", "Баллы"])
    for r in rows:
        ws.append([r["full_name"], format_id(r["id"]), r["points"]])
    wb.save(path)
    return path


def _md_cell(value: str) -> str:
    text = " ".join((value or "").split())
    return text.replace("|", "/")


async def top10_markdown() -> str | None:
    rows = await list_participants_by_points()
    top = rows[:10]
    if not top:
        return None
    lines = [
        "## Топ-10",
        "",
        f"Всего участников: **{len(rows)}**",
        "",
        "| № | ID | Баллы | ФИО |",
        "|:--|:---|------:|:----|",
    ]
    for i, row in enumerate(top, 1):
        lines.append(
            f"| {i} | {format_id(row['id'])} | {row['points']} | {_md_cell(row['full_name'])} |"
        )
    return "\n".join(lines)
