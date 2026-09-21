from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)

from config import ROLE_ADMIN, ROLE_LABELS, ROLE_NONE, ROLE_RECEPTION, ROLE_STAND
from utils import format_id

BTN_REGISTER = "Регистрация"
BTN_FIND = "Поиск"
BTN_EXCEL = "Excel"
BTN_TOP10 = "Топ-10"
BTN_STAFF = "Персонал"
BTN_INVITES = "Ссылки"
BTN_CANCEL = "Отмена"

MENU_TEXTS = {
    BTN_REGISTER,
    BTN_FIND,
    BTN_EXCEL,
    BTN_TOP10,
    BTN_STAFF,
    BTN_INVITES,
}

POINT_PRESETS = (5, 10, 15, 20, 25, 50, 100)
PAGE_SIZE = 8


def role_keyboard(role: str) -> ReplyKeyboardMarkup | ReplyKeyboardRemove:
    if role == ROLE_NONE:
        return ReplyKeyboardRemove()
    if role == ROLE_RECEPTION:
        rows = [[KeyboardButton(text=BTN_REGISTER), KeyboardButton(text=BTN_FIND)]]
        placeholder = "ФИО или кнопка"
    elif role == ROLE_STAND:
        rows = [[KeyboardButton(text=BTN_FIND)]]
        placeholder = "ID, фамилия или кнопка"
    elif role == ROLE_ADMIN:
        rows = [
            [KeyboardButton(text=BTN_REGISTER), KeyboardButton(text=BTN_FIND)],
            [KeyboardButton(text=BTN_EXCEL), KeyboardButton(text=BTN_TOP10)],
            [KeyboardButton(text=BTN_STAFF), KeyboardButton(text=BTN_INVITES)],
        ]
        placeholder = "Команда или кнопка"
    else:
        return ReplyKeyboardRemove()
    return ReplyKeyboardMarkup(
        keyboard=rows,
        resize_keyboard=True,
        is_persistent=True,
        input_field_placeholder=placeholder,
    )


def participant_actions(role: str, pid: int) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    if role in (ROLE_RECEPTION, ROLE_ADMIN):
        rows.append(
            [InlineKeyboardButton(text="Изменить ФИО", callback_data=f"act:name:{pid}")]
        )
    if role in (ROLE_STAND, ROLE_ADMIN):
        rows.append(
            [InlineKeyboardButton(text="Начислить баллы", callback_data=f"act:add:{pid}")]
        )
        rows.append(
            [
                InlineKeyboardButton(
                    text="Установить баллы", callback_data=f"act:set:{pid}"
                )
            ]
        )
    if role in (ROLE_RECEPTION, ROLE_ADMIN):
        rows.append(
            [InlineKeyboardButton(text="Удалить", callback_data=f"act:del:{pid}")]
        )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def dup_confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Да, ещё один", callback_data="dup:yes"),
                InlineKeyboardButton(text="Нет", callback_data="dup:no"),
            ]
        ]
    )


def delete_confirm_keyboard(pid: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Удалить навсегда", callback_data=f"del:yes:{pid}"),
                InlineKeyboardButton(text="Нет", callback_data="del:no"),
            ]
        ]
    )


def register_confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Всё верно", callback_data="reg:yes"),
                InlineKeyboardButton(text="Отмена", callback_data="reg:no"),
            ]
        ]
    )


def confirm_keyboard(*, yes: str = "Да, начислить") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=yes, callback_data="confirm:yes"),
                InlineKeyboardButton(text="Нет", callback_data="confirm:no"),
            ]
        ]
    )


def amount_keyboard() -> InlineKeyboardMarkup:
    row1 = [
        InlineKeyboardButton(text=str(n), callback_data=f"amt:{n}")
        for n in POINT_PRESETS[:4]
    ]
    row2 = [
        InlineKeyboardButton(text=str(n), callback_data=f"amt:{n}")
        for n in POINT_PRESETS[4:]
    ]
    row3 = [InlineKeyboardButton(text="Отмена", callback_data="flow:cancel")]
    return InlineKeyboardMarkup(inline_keyboard=[row1, row2, row3])


def pick_participants_keyboard(rows: list[dict], page: int = 0) -> InlineKeyboardMarkup:
    start = page * PAGE_SIZE
    chunk = rows[start : start + PAGE_SIZE]
    buttons = []
    for r in chunk:
        label = f"{format_id(r['id'])} · {r['full_name']}"
        if len(label) > 64:
            label = label[:61] + "…"
        buttons.append(
            [InlineKeyboardButton(text=label, callback_data=f"pick:{r['id']}")]
        )
    nav = []
    if start > 0:
        nav.append(InlineKeyboardButton(text="←", callback_data=f"pickp:{page - 1}"))
    if start + PAGE_SIZE < len(rows):
        nav.append(InlineKeyboardButton(text="→", callback_data=f"pickp:{page + 1}"))
    if nav:
        buttons.append(nav)
    buttons.append([InlineKeyboardButton(text="Отмена", callback_data="flow:cancel")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def staff_list_keyboard(staff: list[dict], page: int = 0) -> InlineKeyboardMarkup:
    total = len(staff)
    start = page * PAGE_SIZE
    chunk = staff[start : start + PAGE_SIZE]
    buttons = []
    for s in chunk:
        name = s.get("full_name") or "без имени"
        role = ROLE_LABELS.get(s["role"], s["role"])
        label = f"{name} — {role}"
        if len(label) > 60:
            label = label[:57] + "…"
        buttons.append(
            [InlineKeyboardButton(text=label, callback_data=f"staff:{s['tg_user_id']}")]
        )
    nav = []
    if start > 0:
        nav.append(InlineKeyboardButton(text="←", callback_data=f"staffp:{page - 1}"))
    if start + PAGE_SIZE < total:
        nav.append(InlineKeyboardButton(text="→", callback_data=f"staffp:{page + 1}"))
    if nav:
        buttons.append(nav)
    return InlineKeyboardMarkup(inline_keyboard=buttons or [])


def staff_role_keyboard(tg_user_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Ресепшен", callback_data=f"setrole:{tg_user_id}:reception"
                ),
                InlineKeyboardButton(
                    text="Стенд", callback_data=f"setrole:{tg_user_id}:stand"
                ),
            ],
            [
                InlineKeyboardButton(
                    text="Админ", callback_data=f"setrole:{tg_user_id}:admin"
                ),
                InlineKeyboardButton(
                    text="Снять доступ", callback_data=f"setrole:{tg_user_id}:none"
                ),
            ],
            [InlineKeyboardButton(text="← К списку", callback_data="staff:back")],
        ]
    )


def invites_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Ссылка: ресепшен", callback_data="invite:new:reception"
                )
            ],
            [
                InlineKeyboardButton(
                    text="Ссылка: стенд", callback_data="invite:new:stand"
                )
            ],
            [
                InlineKeyboardButton(
                    text="Ссылка: админ", callback_data="invite:new:admin"
                )
            ],
            [InlineKeyboardButton(text="Список ссылок", callback_data="invite:list")],
        ]
    )


def invite_list_keyboard(invites: list[dict], page: int = 0) -> InlineKeyboardMarkup:
    start = page * PAGE_SIZE
    chunk = invites[start : start + PAGE_SIZE]
    rows = []
    for inv in chunk:
        status = "активна" if inv["active"] else "отозвана"
        action = "Отозвать" if inv["active"] else "Включить"
        toggle = 0 if inv["active"] else 1
        role = ROLE_LABELS.get(inv["role"], inv["role"])
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"{role} · {status}",
                    callback_data=f"invite:show:{inv['code']}",
                ),
                InlineKeyboardButton(
                    text=action,
                    callback_data=f"invite:toggle:{inv['code']}:{toggle}",
                ),
            ]
        )
    nav = []
    if start > 0:
        nav.append(InlineKeyboardButton(text="←", callback_data=f"invp:{page - 1}"))
    if start + PAGE_SIZE < len(invites):
        nav.append(InlineKeyboardButton(text="→", callback_data=f"invp:{page + 1}"))
    if nav:
        rows.append(nav)
    rows.append([InlineKeyboardButton(text="← Назад", callback_data="invite:menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)
