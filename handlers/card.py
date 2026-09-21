from html import escape

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from config import ROLE_ADMIN, ROLE_RECEPTION, ROLE_STAND
from db import (
    add_points,
    delete_participant,
    get_participant,
    get_staff_role,
    rename_participant,
    set_points,
)
from handlers.common import Form, not_menu_text
from keyboards import (
    amount_keyboard,
    confirm_keyboard,
    delete_confirm_keyboard,
    participant_actions,
    register_confirm_keyboard,
)
from utils import format_id, participant_card

router = Router()


def _can_people(role: str) -> bool:
    return role in (ROLE_RECEPTION, ROLE_ADMIN)


def _can_points(role: str) -> bool:
    return role in (ROLE_STAND, ROLE_ADMIN)


async def _edit(message: Message, text: str, reply_markup=None) -> None:
    await message.edit_text(text, reply_markup=reply_markup)


async def _fresh_below(message: Message, state: FSMContext, text: str, reply_markup=None) -> None:
    data = await state.get_data()
    chat_id = data.get("prompt_chat")
    mid = data.get("prompt_id")
    if chat_id and mid:
        try:
            await message.bot.edit_message_reply_markup(
                chat_id=chat_id, message_id=mid, reply_markup=None
            )
        except Exception:
            pass
    sent = await message.answer(text, reply_markup=reply_markup)
    await state.update_data(prompt_chat=sent.chat.id, prompt_id=sent.message_id)


def _remember(query: CallbackQuery, state_data: dict) -> dict:
    if query.message:
        state_data["prompt_chat"] = query.message.chat.id
        state_data["prompt_id"] = query.message.message_id
    return state_data


@router.callback_query(F.data.startswith("act:name:"))
async def act_rename(query: CallbackQuery, state: FSMContext) -> None:
    role = await get_staff_role(query.from_user.id)
    if not _can_people(role):
        await query.answer("Нет доступа", show_alert=True)
        return
    pid = int(query.data.split(":")[2])
    p = await get_participant(pid)
    await query.answer()
    if not p:
        await query.message.answer("Участник не найден.")
        return
    await state.set_state(Form.rename_name)
    await state.update_data(**_remember(query, {"pid": pid}))
    await _edit(
        query.message,
        f"Новое ФИО для ID <code>{format_id(pid)}</code>.\nСейчас: {escape(p['full_name'])}",
    )


@router.message(Form.rename_name, not_menu_text(), F.text)
async def rename_name(message: Message, state: FSMContext) -> None:
    name = " ".join((message.text or "").split())
    if len(name) < 2:
        await message.answer("Слишком коротко. Напишите ФИО целиком.")
        return
    await state.update_data(pending_name=name)
    await state.set_state(Form.rename_confirm)
    await _fresh_below(
        message,
        state,
        f"Проверьте данные:\n<b>{escape(name)}</b>",
        register_confirm_keyboard(),
    )


@router.callback_query(Form.rename_confirm, F.data.startswith("reg:"))
async def rename_confirm(query: CallbackQuery, state: FSMContext) -> None:
    await query.answer()
    role = await get_staff_role(query.from_user.id)
    data = await state.get_data()
    await state.set_state(Form.find)
    if query.data == "reg:no" or not data.get("pending_name"):
        p = await get_participant(data.get("pid") or 0)
        if p:
            await _edit(query.message, participant_card(p), participant_actions(role, p["id"]))
        return
    updated = await rename_participant(data["pid"], data["pending_name"])
    if not updated:
        await _edit(query.message, "Участник не найден.")
        return
    await _edit(
        query.message,
        participant_card(updated, title="ФИО изменено"),
        participant_actions(role, updated["id"]),
    )


@router.callback_query(F.data.startswith("act:add:"))
async def act_add(query: CallbackQuery, state: FSMContext) -> None:
    role = await get_staff_role(query.from_user.id)
    if not _can_points(role):
        await query.answer("Нет доступа", show_alert=True)
        return
    pid = int(query.data.split(":")[2])
    p = await get_participant(pid)
    await query.answer()
    if not p:
        await query.message.answer("Участник не найден.")
        return
    await state.set_state(Form.add_points_amount)
    await state.update_data(**_remember(query, {"pid": p["id"], "name": p["full_name"], "points": p["points"]}))
    await _edit(
        query.message,
        participant_card(p) + "\n\nВыберите кнопку или введите количество баллов.",
        amount_keyboard(),
    )


@router.callback_query(Form.add_points_amount, F.data.startswith("amt:"))
async def add_amount_btn(query: CallbackQuery, state: FSMContext) -> None:
    await query.answer()
    await _ask_add_confirm(query.message, state, int(query.data.split(":")[1]), edit=True)


@router.message(Form.add_points_amount, not_menu_text(), F.text)
async def add_amount_text(message: Message, state: FSMContext) -> None:
    raw = (message.text or "").strip()
    if not raw.isdigit() or int(raw) <= 0:
        await message.answer("Нужно целое число больше 0 — кнопка или свой ввод.")
        return
    await _ask_add_confirm(message, state, int(raw), edit=False)


async def _ask_add_confirm(target: Message, state: FSMContext, amount: int, *, edit: bool) -> None:
    await state.update_data(amount=amount)
    data = await state.get_data()
    await state.set_state(Form.add_points_confirm)
    text = (
        f"Начислить <b>{amount}</b> → {escape(data['name'])} "
        f"(ID <code>{format_id(data['pid'])}</code>)?"
    )
    markup = confirm_keyboard()
    if edit:
        await _edit(target, text, markup)
    else:
        await _fresh_below(target, state, text, markup)


@router.callback_query(Form.add_points_confirm, F.data.startswith("confirm:"))
async def add_confirm(query: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    if not data.get("pid") or data.get("amount") is None:
        await query.answer("Уже неактуально", show_alert=True)
        return
    await query.answer()
    role = await get_staff_role(query.from_user.id)
    await state.set_state(Form.find)
    if query.data == "confirm:no":
        p = await get_participant(data["pid"])
        if p:
            await _edit(query.message, participant_card(p), participant_actions(role, p["id"]))
        return
    updated = await add_points(data["pid"], data["amount"], query.from_user.id)
    if not updated:
        await _edit(query.message, "Участник не найден.")
        return
    await _edit(
        query.message,
        participant_card(updated, title=f"Начислено +{data['amount']}"),
        participant_actions(role, updated["id"]),
    )


@router.callback_query(F.data.startswith("act:set:"))
async def act_set(query: CallbackQuery, state: FSMContext) -> None:
    role = await get_staff_role(query.from_user.id)
    if not _can_points(role):
        await query.answer("Нет доступа", show_alert=True)
        return
    pid = int(query.data.split(":")[2])
    p = await get_participant(pid)
    await query.answer()
    if not p:
        await _edit(query.message, "Участник не найден.")
        return
    await state.set_state(Form.set_points_amount)
    await state.update_data(
        **_remember(query, {"pid": p["id"], "name": p["full_name"], "points": p["points"]})
    )
    await _edit(
        query.message,
        participant_card(p) + "\n\nСколько баллов должно стать? Кнопка или число.",
        amount_keyboard(),
    )


@router.callback_query(Form.set_points_amount, F.data.startswith("amt:"))
async def set_amount_btn(query: CallbackQuery, state: FSMContext) -> None:
    await query.answer()
    await _ask_set_confirm(query.message, state, int(query.data.split(":")[1]), edit=True)


@router.message(Form.set_points_amount, not_menu_text(), F.text)
async def set_amount_text(message: Message, state: FSMContext) -> None:
    raw = (message.text or "").strip()
    if not raw.isdigit():
        await message.answer("Нужно целое число от 0. Кнопка или свой ввод.")
        return
    await _ask_set_confirm(message, state, int(raw), edit=False)


async def _ask_set_confirm(target: Message, state: FSMContext, points: int, *, edit: bool) -> None:
    await state.update_data(new_points=points)
    data = await state.get_data()
    await state.set_state(Form.set_points_confirm)
    text = (
        f"Установить <b>{points}</b> баллов у {escape(data['name'])} "
        f"(ID <code>{format_id(data['pid'])}</code>)?\nСейчас: {data['points']}."
    )
    markup = confirm_keyboard(yes="Всё верно")
    if edit:
        await _edit(target, text, markup)
    else:
        await _fresh_below(target, state, text, markup)


@router.callback_query(Form.set_points_confirm, F.data.startswith("confirm:"))
async def set_confirm(query: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    if not data.get("pid") or data.get("new_points") is None:
        await query.answer("Уже неактуально", show_alert=True)
        return
    await query.answer()
    role = await get_staff_role(query.from_user.id)
    await state.set_state(Form.find)
    if query.data == "confirm:no":
        p = await get_participant(data["pid"])
        if p:
            await _edit(query.message, participant_card(p), participant_actions(role, p["id"]))
        return
    updated = await set_points(data["pid"], data["new_points"], query.from_user.id)
    if not updated:
        await _edit(query.message, "Участник не найден.")
        return
    await _edit(
        query.message,
        participant_card(updated, title="Баллы установлены"),
        participant_actions(role, updated["id"]),
    )


@router.callback_query(F.data.startswith("act:del:"))
async def act_delete(query: CallbackQuery, state: FSMContext) -> None:
    role = await get_staff_role(query.from_user.id)
    if not _can_people(role):
        await query.answer("Нет доступа", show_alert=True)
        return
    pid = int(query.data.split(":")[2])
    p = await get_participant(pid)
    await query.answer()
    if not p:
        await _edit(query.message, "Участник не найден.")
        return
    await state.update_data(pid=pid)
    await _edit(
        query.message,
        participant_card(p, title="Удалить эту запись?")
        + "\n\nID больше не выдастся повторно. Баллы тоже пропадут.",
        delete_confirm_keyboard(pid),
    )


@router.callback_query(F.data == "del:no")
async def delete_no(query: CallbackQuery, state: FSMContext) -> None:
    await query.answer()
    role = await get_staff_role(query.from_user.id)
    data = await state.get_data()
    await state.set_state(Form.find)
    p = await get_participant(data.get("pid") or 0)
    if p:
        await _edit(query.message, participant_card(p), participant_actions(role, p["id"]))


@router.callback_query(F.data.startswith("del:yes:"))
async def delete_yes(query: CallbackQuery, state: FSMContext) -> None:
    role = await get_staff_role(query.from_user.id)
    if not _can_people(role):
        await query.answer("Нет доступа", show_alert=True)
        return
    pid = int(query.data.split(":")[2])
    removed = await delete_participant(pid)
    await query.answer()
    await state.set_state(Form.find)
    if not removed:
        await _edit(query.message, "Уже нет такой записи.")
        return
    await _edit(
        query.message,
        f"Удалён: {escape(removed['full_name'])}, ID {format_id(removed['id'])}, "
        f"было баллов {removed['points']}.",
    )

