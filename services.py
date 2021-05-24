from models.users import Feedback
import typing
import asyncio
import aiohttp
import math
import asyncpg
import simplejson as json
import aiogram.utils.markdown as md
import random
import itertools

from operator import and_

from exceptions import PairAlreadyExists
from models import db, User, Kata, SolvedKata, Chat, MenteeToMentor
from aiogram.types.inline_keyboard import InlineKeyboardMarkup, InlineKeyboardButton
from datetime import date, datetime
from config import *
from tabulate import tabulate


class UserService:

    async def get_or_create(**kwargs):
        user = await User.query.where(User.tg_id == kwargs.get('tg_id')).gino.first()
        if user is None:
            user = await User.create(**kwargs)
        return user, user != None

    @classmethod
    async def get_daily_message(cls):
        data = await cls.get_users_stats()
        content = ["Here is a list of all of our warriors!",
                   "-----------------------------------"]
        for num, item in enumerate(data, start=1):
            content.append(md.text(num, '--', item.get('cw_username'),
                                   '--', item.get('count')))
        return md.text(*content, sep='\n')

    @classmethod
    async def get_users_stats(cls):
        conn = await asyncpg.connect(POSTGRES_URI)
        records = await conn.fetch("""
            SELECT users.cw_username, COUNT('solved.id')
            FROM solved_katas AS solved
            INNER JOIN users
                ON users.tg_id = solved.user_id
            WHERE solved.kata_id IN (SELECT id FROM katas)
            GROUP BY users.cw_username
            ORDER BY COUNT('solved.id') DESC;
        """)
        values = [dict(record) for record in records]
        solved = json.loads(json.dumps(values).replace("</", "<\\/"))
        await conn.close()
        return solved

    @classmethod
    async def get_missing_katas(cls, user, offset=0):
        conn = await asyncpg.connect(POSTGRES_URI)
        records = await conn.fetch("""
            SELECT name, slug
            FROM katas
            WHERE id in (
                SELECT id
                FROM katas

                EXCEPT

                SELECT kata_id
                FROM solved_katas
                WHERE user_id = $1
            )
            LIMIT 10 OFFSET $2;
        """, user.id, offset)
        count = await conn.fetchrow("""
            SELECT COUNT(*)
            FROM katas
            WHERE id in (
                SELECT id
                FROM katas

                EXCEPT

                SELECT kata_id
                FROM solved_katas
                WHERE user_id = $1
            );
        """, user.id)
        await conn.close()
        markup = InlineKeyboardMarkup()
        for r in records:
            btn = InlineKeyboardButton(text=r.get('name'),
                                       url=f"{CODEWARS_BASE_KATA_URL}/{r.get('slug')}/")
            markup.add(btn)
        buttons = []
        if not count.get('count') - offset <= 10:
            buttons.append(InlineKeyboardButton(
                text='Далее', callback_data=f'next_{offset + 10}'))
        if offset > 0:
            buttons.append(InlineKeyboardButton(
                text='Назад', callback_data=f'next_{offset - 10}'))
        if buttons:
            markup.add(*buttons)
        return markup, count.get('count')

    async def get_total_pages(user):
        async with aiohttp.ClientSession() as session:
            async with session.get(f'{CODEWARS_BASE_URL}/{user.cw_username}/code-challenges/completed?page=0') as resp:
                resp = await resp.json()
                return resp.get('totalPages')

    @classmethod
    async def get_user_solved_katas(cls, user):
        # pages = math.ceil(await cls.get_total_items(user) / 200)
        user = await User.query.where(User.tg_id == user.id).gino.first()
        count = await cls.extract_solved_katas(user)
        return count

    async def get_katas(url):
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                resp = await resp.json()
                return resp.get('data')

    @classmethod
    async def extract_solved_katas(cls, user):
        pages = await cls.get_total_pages(user)
        count = 0
        for page in range(pages):
            url = f"{CODEWARS_BASE_URL}/{user.cw_username}/code-challenges/completed?page={page}"
            katas = await cls.get_katas(url)
            for kata in katas:
                instance = await Kata.query.where(Kata.id == kata.get('id')).gino.first()
                exists = await SolvedKata.query.where(and_(SolvedKata.user_id == user.tg_id, SolvedKata.kata_id == kata.get('id'))).gino.first()
                if exists is None and instance is not None:
                    await SolvedKata.create(kata_id=instance.id, user_id=user.tg_id)
                    count += 1
        return count

    @classmethod
    async def extract_solved_katas_in_bulk(cls):
        users = await User.query.gino.all()
        for user in users:
            await cls.extract_solved_katas(user)


class ChatService:

    async def get_chat():
        return await Chat.query.limit(1).gino.first()

    async def set_chat(chat):
        chat = await Chat.create(id=chat.id, chat_type=chat.type)
        return chat


class MentorService:

    model = User

    async def make_me_mentor(user):
        instance = await User.query.where(User.tg_id == user.id).gino.first()
        if instance is None:
            await User.create(tg_id=user.id, tg_username=user.username, is_mentor=True)
        else:
            await instance.update(is_mentor=True).apply()

    async def get_mentors():
        return await User.query.where(User.is_mentor == True).gino.all()

    async def list_mentees():
        return await User.query.where(User.is_mentor == False).gino.all()

    async def get_number_of_mentees(mentor: User):
        query = db.text(
            """
            SELECT mentor.tg_username AS mentor, COUNT(mentee.tg_id)
            FROM pairs
            INNER JOIN users AS mentor
                ON pairs.mentor_id = mentor.tg_id
            INNER JOIN users AS mentee
                ON pairs.mentee_id = mentee.tg_id
            WHERE mentor.tg_id = :mentor_id AND pairs.created_at::date = (
                SELECT MAX(created_at::date)
                FROM pairs
            )
            GROUP BY mentor.tg_username;
            """
        )
        data = await db.first(query, mentor_id=mentor.tg_id)
        return data.count if data is not None else 0

    @classmethod
    async def get_random_mentor(cls):
        mentors = await cls.get_mentors()
        query = db.text("""
            SELECT COUNT(*)
            FROM users
            WHERE is_mentor = false;
        """)
        total = await db.first(query)
        weights = [
            abs(total.count - await cls.get_number_of_mentees(mentor)) for mentor in mentors]
        return random.choices(mentors, weights).pop()

    @classmethod
    async def get_random_mentee(cls):
        conn = await asyncpg.connect(POSTGRES_URI)
        query = await conn.fetch("""
            SELECT tg_id
            FROM users
            WHERE users.tg_id not in (SELECT mentee_id FROM pairs WHERE created_at::date = (SELECT MAX(created_at::date) FROM pairs)) AND is_mentor = false;
        """)
        await conn.close()
        mentees = [record.get('tg_id') for record in query]
        return await User.query.where(User.tg_id == random.choice(mentees)).gino.first()

    @classmethod
    async def find_pair(cls, mentor: User, mentee: User):
        return await MenteeToMentor.query.where(MenteeToMentor.mentor_id == mentor.tg_id and MenteeToMentor.mentee_id == mentee.tg_id).gino.first()

    @classmethod
    async def delete_previous_pairs(cls):
        max_date = await db.func.max(MenteeToMentor.created_at).gino.scalar()
        await MenteeToMentor.delete.where(db.cast(MenteeToMentor.created_at, db.Date) == max_date).gino.status()

    @classmethod
    async def is_mentor_available(cls, mentor: User):
        today = datetime.now().date()
        return await MenteeToMentor.query.where(db.cast(MenteeToMentor.created_at, db.Date) == today and MenteeToMentor.mentor_id == mentor.tg_id).gino.first() is None

    @staticmethod
    async def number_of_available_mentors():
        query = db.text("""
            SELECT COUNT(*)
            FROM users
            WHERE is_mentor = true AND tg_id in (SELECT mentor_id FROM pairs WHERE created_at::date = CURRENT_DATE);
        """)
        total = await db.first(query)
        return total.count

    @classmethod
    async def distribute_users(cls):
        # TODO
        # 1) add limit on amount of mentees
        # 2) add probability system
        mentees = await cls.list_mentees()
        mentors = await cls.get_mentors()

        random.shuffle(mentors)

        for mentee in mentees:
            _mentor = None
            for mentor in mentors:
                pair = await cls.find_pair(mentor, mentee)
                if pair is not None:
                    continue
                elif cls.is_mentor_available(mentor):
                    _mentor = mentor
                    break
            else:
                _mentor = await cls.get_random_mentor()
            await MenteeToMentor.create(mentor_id=_mentor.tg_id, mentee_id=mentee.tg_id)

    @classmethod
    async def get_latest_list(cls):
        conn = await asyncpg.connect(POSTGRES_URI)
        query = await conn.fetch("""
            SELECT mentor.tg_username AS mentor, mentee.tg_username AS mentee
            FROM pairs
            INNER JOIN users AS mentor
                ON pairs.mentor_id = mentor.tg_id
            INNER JOIN users AS mentee
                ON pairs.mentee_id = mentee.tg_id
            WHERE pairs.created_at::date = (
                SELECT MAX(created_at::date)
                FROM pairs
            );
        """)
        await conn.close()
        return [(num, record.get('mentor'), record.get('mentee'))
                for num, record in enumerate(query, start=1)]

    @classmethod
    async def generate_table(cls):
        headers = ["#", "Mentor", "Mentee"]
        table = await cls.get_latest_list()
        pairs = tabulate(table, headers, tablefmt="pretty")
        return f'<pre>{pairs}</pre>'

    @staticmethod
    async def generate_rate_markup():
        markup = InlineKeyboardMarkup()

        markup.row(*[InlineKeyboardButton(text=num, callback_data=f"rate_{num}")
                     for num in range(MIN_RATE, MAX_RATE + 1)])
        return markup

    @staticmethod
    async def get_current_mentor(mentee: User) -> User:
        query = db.text("""
            SELECT mentor.tg_id, mentor.tg_username
            FROM pairs
            INNER JOIN users AS mentor
                ON mentor.tg_id = pairs.mentor_id
            WHERE pairs.mentee_id = :mentee_id AND pairs.created_at::date = (
                SELECT MAX(created_at::date)
                FROM pairs
            );
        """)
        mentor = await db.first(query, mentee_id=mentee.tg_id)
        return mentor

    @classmethod
    async def get_reminder_message(cls, mentee: User) -> str:
        mentor = await cls.get_current_mentor(mentee)
        base = f"Please, rate @{mentor.tg_username}'s work"
        return md.text(base, "<pre>Don't worry.\nIt's all confidential</pre>", sep='\n\n')

    @staticmethod
    async def rate_mentor(mentee_id: int, mentor_id: int, rate: int):
        await Feedback.create(
            mentee_id=mentee_id,
            mentor_id=mentor_id,
            rate=rate)

    @staticmethod
    async def get_mentee(mentee_id: int):
        return await User.query.where(User.tg_id == mentee_id).gino.first()
