import secrets
from datetime import datetime
from html import escape

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, FSInputFile, InputRichMessage, Message

from config import ROLE_ADMIN, ROLE_LABELS
from db import (
    create_invite,
    get_invite,
    get_staff,
    get_staff_role,
    list_invites,
    list_participants_by_points,
    list_staff,
    set_invite_active,
    set_staff_role,
)
from export import build_excel, top10_markdown
from keyboards import (
    BTN_EXCEL,
    BTN_INVITES,
    BTN_STAFF,
    BTN_TOP10,
    invite_list_keyboard,
    invites_menu_keyboard,
    role_keyboard,
    staff_list_keyboard,
    staff_role_keyboard,
)

router = Router()


def _is_admin(role: str) -> bool:
    return role == ROLE_ADMIN


@router.message(F.text == BTN_EXCEL)
async def send_excel(message: Message, state: FSMContext) -> None:
    await state.clear()
    if not _is_admin(await get_staff_role(message.from_user.id)):
        await message.answer("Эта кнопка не для вашей роли.")
        return
    rows = await list_participants_by_points()
    if not rows:
        await message.answer("Пока некого выгружать — участников нет.")
        return
    path = await build_excel()
    await message.answer_document(
        FSInputFile(path, filename=f"uchastniki_{datetime.now():%Y%m%d_%H%M}.xlsx"),
        caption=f"Все участники: {len(rows)}",
    )


@router.message(F.text == BTN_TOP10)
async def send_top(message: Message, state: FSMContext) -> None:
    await state.clear()
    if not _is_admin(await get_staff_role(message.from_user.id)):
        await message.answer("Эта кнопка не для вашей роли.")
        return
    markdown = await top10_markdown()
    if not markdown:
        await message.answer("Пока нет участников.")
        return
    await message.bot.send_rich_message(
        message.chat.id,
        InputRichMessage(markdown=markdown),
    )


@router.message(F.text == BTN_STAFF)
async def show_staff(message: Message, state: FSMContext) -> None:
    await state.clear()
    if not _is_admin(await get_staff_role(message.from_user.id)):
        await message.answer("Эта кнопка не для вашей роли.")
        return
    staff = await list_staff()
    if not staff:
        await message.answer("Пока никто не заходил в бота.")
        return
    await message.answer(
        f"Персонал ({len(staff)}). Выберите:",
        reply_markup=staff_list_keyboard(staff, 0),
    )


@router.callback_query(F.data.startswith("staffp:"))
async def staff_page(query: CallbackQuery) -> None:
    if not _is_admin(await get_staff_role(query.from_user.id)):
        await query.answer("Нет доступа", show_alert=True)
        return
    page = int(query.data.split(":")[1])
    await query.answer()
    staff = await list_staff()
    await query.message.edit_reply_markup(reply_markup=staff_list_keyboard(staff, page))


@router.callback_query(F.data == "staff:back")
async def staff_back(query: CallbackQuery) -> None:
    if not _is_admin(await get_staff_role(query.from_user.id)):
        await query.answer("Нет доступа", show_alert=True)
        return
    await query.answer()
    staff = await list_staff()
    await query.message.edit_text(
        f"Персонал ({len(staff)}). Выберите:",
        reply_markup=staff_list_keyboard(staff, 0),
    )


@router.callback_query(F.data.startswith("staff:"))
async def staff_one(query: CallbackQuery) -> None:
    if not _is_admin(await get_staff_role(query.from_user.id)):
        await query.answer("Нет доступа", show_alert=True)
        return
    await query.answer()
    tg_id = int(query.data.split(":")[1])
    person = await get_staff(tg_id)
    if not person:
        await query.message.edit_text("Пользователь не найден.")
        return
    uname = f" @{person['username']}" if person.get("username") else ""
    text = (
        f"{escape(person.get('full_name') or 'без имени')}{uname}\n"
        f"id: <code>{person['tg_user_id']}</code>\n"
        f"роль: {ROLE_LABELS.get(person['role'], person['role'])}"
    )
    await query.message.edit_text(text, reply_markup=staff_role_keyboard(tg_id))


@router.callback_query(F.data.startswith("setrole:"))
async def staff_set_role(query: CallbackQuery) -> None:
    if not _is_admin(await get_staff_role(query.from_user.id)):
        await query.answer("Нет доступа", show_alert=True)
        return
    _, tg_s, role = query.data.split(":")
    tg_id = int(tg_s)
    await set_staff_role(tg_id, role)
    await query.answer("Роль обновлена")
    try:
        await query.bot.send_message(
            tg_id,
            f"Вам выдана роль: <b>{ROLE_LABELS.get(role, role)}</b>. Меню ниже.",
            reply_markup=role_keyboard(role),
        )
    except Exception:
        pass
    person = await get_staff(tg_id)
    uname = f" @{person['username']}" if person and person.get("username") else ""
    name = escape((person or {}).get("full_name") or "без имени")
    await query.message.edit_text(
        f"{name}{uname}\nid: <code>{tg_id}</code>\nроль: {ROLE_LABELS.get(role, role)}",
        reply_markup=staff_role_keyboard(tg_id),
    )


@router.message(F.text == BTN_INVITES)
async def invites_menu(message: Message, state: FSMContext) -> None:
    await state.clear()
    if not _is_admin(await get_staff_role(message.from_user.id)):
        await message.answer("Эта кнопка не для вашей роли.")
        return
    await message.answer("Приглашения:", reply_markup=invites_menu_keyboard())


@router.callback_query(F.data == "invite:menu")
async def invites_menu_cb(query: CallbackQuery) -> None:
    if not _is_admin(await get_staff_role(query.from_user.id)):
        await query.answer("Нет доступа", show_alert=True)
        return
    await query.answer()
    await query.message.edit_text("Приглашения:", reply_markup=invites_menu_keyboard())


@router.callback_query(F.data.startswith("invite:new:"))
async def invite_new(query: CallbackQuery) -> None:
    if not _is_admin(await get_staff_role(query.from_user.id)):
        await query.answer("Нет доступа", show_alert=True)
        return
    role = query.data.split(":")[2]
    code = "inv_" + secrets.token_hex(4)
    await create_invite(code, role, query.from_user.id)
    bot_info = await query.bot.get_me()
    link = f"https://t.me/{bot_info.username}?start={code}"
    await query.answer()
    await query.message.answer(
        f"Ссылка «{ROLE_LABELS.get(role, role)}» — многоразовая, пока не отзовёте:\n{link}"
    )


@router.callback_query(F.data.startswith("invp:"))
async def invite_page(query: CallbackQuery) -> None:
    if not _is_admin(await get_staff_role(query.from_user.id)):
        await query.answer("Нет доступа", show_alert=True)
        return
    page = int(query.data.split(":")[1])
    await query.answer()
    invites = await list_invites()
    await query.message.edit_reply_markup(reply_markup=invite_list_keyboard(invites, page))


@router.callback_query(F.data == "invite:list")
async def invite_list(query: CallbackQuery) -> None:
    if not _is_admin(await get_staff_role(query.from_user.id)):
        await query.answer("Нет доступа", show_alert=True)
        return
    await query.answer()
    invites = await list_invites()
    if not invites:
        await query.message.edit_text("Ссылок ещё нет.", reply_markup=invites_menu_keyboard())
        return
    await query.message.edit_text(
        "Нажмите роль — пришлю ссылку ещё раз.",
        reply_markup=invite_list_keyboard(invites),
    )


@router.callback_query(F.data.startswith("invite:show:"))
async def invite_show(query: CallbackQuery) -> None:
    if not _is_admin(await get_staff_role(query.from_user.id)):
        await query.answer("Нет доступа", show_alert=True)
        return
    code = query.data.split(":")[2]
    inv = await get_invite(code)
    await query.answer()
    if not inv:
        await query.message.answer("Ссылка не найдена.")
        return
    bot_info = await query.bot.get_me()
    link = f"https://t.me/{bot_info.username}?start={code}"
    status = "активна" if inv["active"] else "отозвана"
    await query.message.answer(
        f"{ROLE_LABELS.get(inv['role'], inv['role'])} · {status}\n{link}"
    )


@router.callback_query(F.data.startswith("invite:toggle:"))
async def invite_toggle(query: CallbackQuery) -> None:
    if not _is_admin(await get_staff_role(query.from_user.id)):
        await query.answer("Нет доступа", show_alert=True)
        return
    parts = query.data.split(":")
    code = parts[2]
    active = parts[3] == "1"
    await set_invite_active(code, active)
    await query.answer("Обновили")
    invites = await list_invites()
    await query.message.edit_reply_markup(reply_markup=invite_list_keyboard(invites))
