from html import escape

from aiogram import F, Router
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from config import ADMIN_IDS, ROLE_LABELS, ROLE_NONE
from db import get_invite, get_staff_role, upsert_staff
from keyboards import BTN_CANCEL, MENU_TEXTS, role_keyboard
from utils import staff_display_name

router = Router()

HELP_BY_ROLE = {
    "reception": "Регистрация — ФИО, потом проверка.\nПоиск — карточка: сменить ФИО или удалить.",
    "stand": "Поиск — карточка участника: начислить или установить баллы.",
    "admin": "Регистрация и поиск.\nНа карточке: ФИО, баллы, удаление.\nExcel и Топ-10 — к концерту.\nПерсонал и Ссылки — роли.",
}


class Form(StatesGroup):
    register_name = State()
    register_confirm = State()
    register_dup = State()
    find = State()
    rename_name = State()
    rename_confirm = State()
    add_points_amount = State()
    add_points_confirm = State()
    set_points_amount = State()
    set_points_confirm = State()


def not_menu_text():
    return F.text.not_in(MENU_TEXTS)


async def restore_menu(event: Message | CallbackQuery, state: FSMContext, text: str) -> None:
    await state.clear()
    user = event.from_user
    role = await get_staff_role(user.id) if user else ROLE_NONE
    kb = role_keyboard(role)
    if isinstance(event, CallbackQuery):
        await event.message.answer(text, reply_markup=kb)
    else:
        await event.answer(text, reply_markup=kb)


@router.message(CommandStart())
async def cmd_start(
    message: Message, state: FSMContext, command: CommandObject
) -> None:
    await state.clear()
    user = message.from_user
    if not user:
        return
    payload = (command.args or "").strip()

    granted_role = None
    if payload:
        invite = await get_invite(payload)
        if invite and invite["active"]:
            granted_role = invite["role"]
        else:
            await message.answer("Ссылка недействительна или отозвана.")

    force_admin = user.id in ADMIN_IDS
    role = await upsert_staff(
        user.id,
        staff_display_name(user),
        user.username,
        role=granted_role,
        force_admin=force_admin,
    )

    if role == ROLE_NONE:
        await message.answer(
            "Доступ ещё не выдан. Попросите организатора ссылку или роль.",
            reply_markup=role_keyboard(role),
        )
        return

    hint = HELP_BY_ROLE.get(role, "")
    await message.answer(
        f"Роль: <b>{ROLE_LABELS.get(role, role)}</b>.\n{hint}",
        reply_markup=role_keyboard(role),
    )


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    role = await get_staff_role(message.from_user.id)
    hint = HELP_BY_ROLE.get(role, "Нажмите /start — если есть доступ, появится меню.")
    await message.answer(hint, reply_markup=role_keyboard(role))


@router.message(Command("cancel"))
@router.message(F.text == BTN_CANCEL)
async def cmd_cancel(message: Message, state: FSMContext) -> None:
    current = await state.get_state()
    if current is None:
        role = await get_staff_role(message.from_user.id)
        await message.answer("Меню на месте.", reply_markup=role_keyboard(role))
        return
    await restore_menu(message, state, "Отменено.")


@router.callback_query(F.data == "flow:cancel")
async def cb_cancel(query: CallbackQuery, state: FSMContext) -> None:
    await query.answer()
    data = await state.get_data()
    pid = data.get("pid")
    role = await get_staff_role(query.from_user.id)
    if pid and await state.get_state() not in (Form.register_name.state, Form.register_confirm.state, Form.register_dup.state):
        from db import get_participant
        from keyboards import participant_actions
        from utils import participant_card

        p = await get_participant(int(pid))
        await state.set_state(Form.find)
        if p and query.message:
            await query.message.edit_text(
                participant_card(p),
                reply_markup=participant_actions(role, p["id"]),
            )
            return
    await state.clear()
    if query.message:
        await query.message.edit_text("Отменено.")
