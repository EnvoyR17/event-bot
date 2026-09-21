from html import escape

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from config import ROLE_ADMIN, ROLE_RECEPTION, ROLE_STAND
from db import (
    create_participant,
    find_exact_name,
    get_participant,
    get_staff_role,
    search_participants,
)
from handlers.common import Form, not_menu_text, restore_menu
from keyboards import (
    BTN_FIND,
    BTN_REGISTER,
    dup_confirm_keyboard,
    participant_actions,
    pick_participants_keyboard,
    register_confirm_keyboard,
    role_keyboard,
)
from utils import format_id, parse_id, participant_card

router = Router()


def _can_find(role: str) -> bool:
    return role in (ROLE_RECEPTION, ROLE_STAND, ROLE_ADMIN)


def _can_edit_person(role: str) -> bool:
    return role in (ROLE_RECEPTION, ROLE_ADMIN)


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


@router.message(F.text == BTN_REGISTER)
async def start_register(message: Message, state: FSMContext) -> None:
    role = await get_staff_role(message.from_user.id)
    if not _can_edit_person(role):
        await message.answer("Эта кнопка не для вашей роли.")
        return
    await state.clear()
    await state.set_state(Form.register_name)
    sent = await message.answer(
        "ФИО одним сообщением. Перед записью покажу данные на проверку.",
        reply_markup=role_keyboard(role),
    )
    await state.update_data(prompt_chat=sent.chat.id, prompt_id=sent.message_id)


@router.message(Form.register_name, not_menu_text(), F.text)
async def finish_register(message: Message, state: FSMContext) -> None:
    name = " ".join((message.text or "").split())
    if len(name) < 2:
        await message.answer("Слишком коротко. Напишите ФИО целиком.")
        return
    twins = await find_exact_name(name)
    if twins:
        await state.update_data(pending_name=name)
        await state.set_state(Form.register_dup)
        ids = ", ".join(format_id(t["id"]) for t in twins)
        await _fresh_below(
            message,
            state,
            f"Уже есть «{escape(name)}», ID: <code>{ids}</code>.\n"
            "Это другой человек — зарегистрировать ещё одного?",
            dup_confirm_keyboard(),
        )
        return
    await state.update_data(pending_name=name)
    await state.set_state(Form.register_confirm)
    await _fresh_below(
        message,
        state,
        f"Проверьте данные:\n<b>{escape(name)}</b>",
        register_confirm_keyboard(),
    )


@router.callback_query(Form.register_confirm, F.data.startswith("reg:"))
async def register_confirm(query: CallbackQuery, state: FSMContext) -> None:
    await query.answer()
    data = await state.get_data()
    name = data.get("pending_name")
    if query.data == "reg:no" or not name:
        await state.set_state(Form.register_name)
        await query.message.edit_text("Следующее ФИО.")
        return
    participant = await create_participant(name)
    await state.set_state(Form.register_name)
    await query.message.edit_text(
        participant_card(participant, title="Зарегистрирован")
        + "\n\nСледующее ФИО — следующий участник."
    )
    await state.update_data(prompt_chat=None, prompt_id=None)


@router.callback_query(Form.register_dup, F.data == "dup:yes")
async def dup_yes(query: CallbackQuery, state: FSMContext) -> None:
    await query.answer()
    data = await state.get_data()
    name = data.get("pending_name")
    if not name:
        await restore_menu(query, state, "Сессия сбросилась, начните регистрацию снова.")
        return
    participant = await create_participant(name)
    await state.set_state(Form.register_name)
    await query.message.edit_text(
        participant_card(participant, title="Зарегистрирован")
        + "\n\nСледующее ФИО — следующий участник."
    )
    await state.update_data(prompt_chat=None, prompt_id=None)


@router.callback_query(Form.register_dup, F.data == "dup:no")
async def dup_no(query: CallbackQuery, state: FSMContext) -> None:
    await query.answer()
    await state.set_state(Form.register_name)
    await query.message.edit_text("Следующее ФИО.")


@router.message(F.text == BTN_FIND)
async def start_find(message: Message, state: FSMContext) -> None:
    role = await get_staff_role(message.from_user.id)
    if not _can_find(role):
        await message.answer("Эта кнопка не для вашей роли.")
        return
    await state.clear()
    await state.set_state(Form.find)
    await message.answer(
        "Фамилия, часть ФИО или ID. Можно сразу следующего.",
        reply_markup=role_keyboard(role),
    )


@router.message(Form.find, not_menu_text(), F.text)
async def finish_find(message: Message, state: FSMContext) -> None:
    query = (message.text or "").strip()
    role = await get_staff_role(message.from_user.id)
    pid = parse_id(query)
    if pid is not None:
        p = await get_participant(pid)
        if not p:
            await message.answer("Такого ID нет. Другой запрос.")
            return
        await message.answer(participant_card(p), reply_markup=participant_actions(role, p["id"]))
        return
    rows = await search_participants(query)
    if not rows:
        await message.answer("Никого не нашли. Другая фамилия или ID.")
        return
    if len(rows) == 1:
        await message.answer(participant_card(rows[0]), reply_markup=participant_actions(role, rows[0]["id"]))
        return
    await state.update_data(find_query=query)
    await message.answer(
        f"Нашёл {len(rows)}. Выберите:",
        reply_markup=pick_participants_keyboard(rows, 0),
    )


@router.callback_query(Form.find, F.data.startswith("pickp:"))
async def find_page(query: CallbackQuery, state: FSMContext) -> None:
    await query.answer()
    page = int(query.data.split(":")[1])
    data = await state.get_data()
    rows = await search_participants(data.get("find_query") or "")
    await query.message.edit_reply_markup(reply_markup=pick_participants_keyboard(rows, page))


@router.callback_query(Form.find, F.data.startswith("pick:"))
async def find_pick(query: CallbackQuery, state: FSMContext) -> None:
    await query.answer()
    pid = int(query.data.split(":")[1])
    p = await get_participant(pid)
    role = await get_staff_role(query.from_user.id)
    if not p:
        await query.message.edit_text("Участник не найден.")
        return
    await query.message.edit_text(
        participant_card(p),
        reply_markup=participant_actions(role, p["id"]),
    )
