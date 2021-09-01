import asyncio
import logging

import aiogram.utils.markdown as md
import aiohttp
import aioschedule
from aiogram import Bot, Dispatcher, executor, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters import Text
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.types import ParseMode
from aiogram.types.reply_keyboard import KeyboardButton, ReplyKeyboardMarkup
from aiogram.utils.executor import Executor

from config import *
from models import on_shutdown
from models import on_startup as db_startup
from models.users import User
from services import ChatService, MentorService, UserService

# Configure logging
logging.basicConfig(level=logging.INFO)

# Initialize bot and dispatcher
bot = Bot(token=API_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)
runner = Executor(dp)


# States
class Form(StatesGroup):
    name = State()  # Will be represented in storage as 'Form:name'


@dp.message_handler(commands=['start', 'help'])
async def send_welcome(message: types.Message):
    """
    This handler will be called when user sends `/start` or `/help` command
    """
    u = User(tg_id=message.from_user.id, tg_username=message.from_user.username)
    await u.create()
    await message.reply("Hi!\nI'm the CodewarsBot!\nCreated by @dimashmello")


@dp.message_handler(commands=['authorize'])
async def authorize_user(message: types.Message):
    await Form.name.set()

    await message.reply("Don't be shy. Type your Codewars username. I'll wait c:")


@dp.message_handler(commands=['daily_stats'])
async def send_daily_stats(message: types.Message):
    msg = await UserService.get_daily_message()
    await bot.send_message(message.chat.id, text=msg, parse_mode=ParseMode.HTML)


@dp.message_handler(commands=['update_solutions'])
async def update_solutions(message: types.Message):
    solved = await UserService.get_user_solved_katas(message.from_user)
    if solved:
        await bot.send_message(message.chat.id, text=f'Since last update you\'ve solved {solved} katas. Congrats!')
    else:
        await bot.send_message(message.chat.id, text="No katas were solved since last update. What are you waiting for?")


@dp.message_handler(commands=['get_uncompleted'])
async def get_missing_katas(message: types.Message):
    if message.chat.type != 'private':
        await bot.send_message(message.chat.id, "To use this option write it to me in private 👀")
    else:
        markup, count = await UserService.get_missing_katas(message.from_user)
        if count == 0:
            return await bot.send_message(message.chat.id, "So far you've completed every kata. Well done 😎")
        await bot.send_message(message.chat.id, "List of katas yet to be completed", reply_markup=markup)


@dp.message_handler(commands=['set_chat'])
async def set_chat(message: types.Message):
    chat = await ChatService.set_chat(message.chat)
    if chat is not None:
        await bot.send_message(message.chat.id, text="Chat was set. You good to go!")


@dp.message_handler(commands=['shuffle'])
async def shuffle_users(message: types.Message):
    await MentorService.distribute_users()
    table = await MentorService.generate_table()
    await bot.send_message(message.chat.id, table, parse_mode=ParseMode.HTML)


@dp.message_handler(commands=['reshuffle'])
async def reshuffle_users(message: types.Message):
    await MentorService.delete_previous_pairs()
    await MentorService.distribute_users()
    table = await MentorService.generate_table()
    await bot.send_message(message.chat.id, table, parse_mode=ParseMode.HTML)


@dp.message_handler(commands=['pairs'])
async def send_pairs_info(message: types.Message):
    table = await MentorService.generate_table()
    await bot.send_message(message.chat.id, table, parse_mode=ParseMode.HTML)


@dp.message_handler(commands=['mentor'])
async def make_user_mentor(message: types.Message):
    await MentorService.make_me_mentor(message.from_user)


@dp.message_handler(commands=['commands'])
async def get_commands(message: types.Message):
    markup = ReplyKeyboardMarkup(
        resize_keyboard=True, one_time_keyboard=True)
    missed_katas = KeyboardButton("Get list of unsolved katas")
    markup.add(missed_katas)
    await bot.send_message(message.chat.id, text="Here is commands", reply_markup=markup)


@dp.message_handler(state='*', commands='cancel')
@dp.message_handler(Text(equals='cancel', ignore_case=True), state='*')
async def cancel_handler(message: types.Message, state: FSMContext):
    """
    Allow user to cancel any action
    """
    current_state = await state.get_state()
    if current_state is None:
        return

    logging.info('Cancelling state %r', current_state)
    # Cancel state and inform user about it
    await state.finish()
    # And remove keyboard (just in case)
    await message.reply('Cancelled.', reply_markup=types.ReplyKeyboardRemove())


@dp.message_handler(state=Form.name)
async def process_name(message: types.Message, state: FSMContext):
    """
    Process Codewars username
    """
    data = {
        'tg_id': message.from_user.id,
        'tg_username': message.from_user.username,
        'cw_username': message.text
    }

    async with aiohttp.ClientSession() as session:
        async with session.head(f"{CODEWARS_BASE_URL}/{data['cw_username']}") as resp:
            if resp.status in range(200, 300):
                markup = types.ReplyKeyboardRemove()
                obj, created = await UserService.get_or_create(tg_id=message.from_user.id)
                await obj.update(**data).apply()
                if created:
                    await bot.send_message(
                        message.chat.id,
                        md.text('Welcome on board,',
                                md.bold(data['cw_username'])),
                        reply_markup=markup,
                        parse_mode=ParseMode.MARKDOWN,
                    )
                else:
                    await bot.send_message(
                        message.chat.id,
                        "Something went wrong"
                    )

            else:
                await bot.send_message(
                    message.chat.id,
                    md.text("The user with username", md.bold(
                        data['name']), "was not found"),
                    parse_mode=ParseMode.MARKDOWN
                )

    # Finish conversation
    await state.finish()


@dp.callback_query_handler(lambda msg: msg.data.startswith('user'))
async def process_callback_on_user(callback_query: types.CallbackQuery):
    _, username = callback_query.data.split('_', maxsplit=1)
    await bot.answer_callback_query(callback_query.id)
    async with aiohttp.ClientSession() as session:
        async with session.get(f'{CODEWARS_BASE_URL}/{username}/code-challenges/completed?page=0') as resp:
            resp = await resp.json()

            await bot.send_message(
                callback_query.message.chat.id,
                md.text(md.text("Total completed -"), md.bold(
                    resp.get('totalItems'))),
                parse_mode=ParseMode.MARKDOWN
            )


@dp.callback_query_handler(lambda msg: msg.data.startswith('next'))
async def process_callback_on_user(callback_query: types.CallbackQuery):
    _, offset = callback_query.data.split('_', maxsplit=1)
    markup, count = await UserService.get_missing_katas(callback_query.message.from_user, int(offset))

    await callback_query.message.edit_reply_markup(reply_markup=markup)


@dp.callback_query_handler(lambda msg: msg.data.startswith('rate'))
async def process_callback_on_user(callback_query: types.CallbackQuery):
    rate = int(callback_query.data.split('_', maxsplit=1).pop())
    mentee = await MentorService.get_mentee(callback_query.message.chat.id)
    mentor = await MentorService.get_current_mentor(mentee)

    await MentorService.rate_mentor(mentee.tg_id, mentor.tg_id, rate)
    await callback_query.message.edit_reply_markup(reply_markup=None)
    await callback_query.message.edit_text("Thanks for your feedback 💚")


async def send_daily_updates():
    chat = await ChatService.get_chat()
    msg = await UserService.get_daily_message()
    await dp.bot.send_message(chat.id, text=msg)


async def send_daily_reminder_to_rate():
    markup = await MentorService.generate_rate_markup()
    mentees = await MentorService.list_mentees()
    for mentee in mentees:
        text = await MentorService.get_reminder_message(mentee)
        await dp.bot.send_message(mentee.tg_id, text, reply_markup=markup, parse_mode=ParseMode.HTML)


async def scheduler():
    aioschedule.every().day.at("11:00").do(send_daily_updates)
    aioschedule.every().monday.at("23:00").do(send_daily_reminder_to_rate)

    while True:
        await aioschedule.run_pending()
        await asyncio.sleep(1)


async def on_startup(dispatcher: Dispatcher):
    # await dispatcher.bot.set_webhook(WEBHOOK_URL)
    await db_startup(dispatcher)
    asyncio.create_task(scheduler())


if __name__ == '__main__':
    executor.start_polling(
        dp,
        on_startup=on_startup,
        on_shutdown=on_shutdown,
        skip_updates=True
    )
    # executor.start_webhook(
    #     dispatcher=dp,
    #     webhook_path=WEBHOOK_PATH,
    #     on_startup=on_startup,
    #     on_shutdown=on_shutdown,
    #     skip_updates=True,
    #     host=WEBAPP_HOST,
    #     port=WEBAPP_PORT,
    # )
