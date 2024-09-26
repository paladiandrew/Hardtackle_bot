import asyncio
import requests
import pandas as pd
from aiogram import F
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import FSInputFile
from datetime import datetime
import numpy as np

import random
import string
import aiohttp
import os
import json

from dotenv import load_dotenv
from aiohttp import FormData

load_dotenv()

server = os.getenv("WEB_APP_URL")
bot_token = os.getenv("BOT_TOKEN")
web_url = os.getenv("WEB_URL")


def load_config():
    with open("config.json", "r") as file:
        return json.load(file)


def save_config(config):
    with open("config.json", "w") as file:
        json.dump(config, file, indent=4)


config = load_config()
TOKEN = bot_token
bot = Bot(token=TOKEN)

# Диспетчер
dp = Dispatcher()

admin_ids = config["admin_ids"]
user_props = config.get("user_props", [])
messages_to_delete = {}
user_props_lock = asyncio.Lock()
user_state = {}
registration_open = False


def update_admin_ids(new_admin_ids):
    config["admin_ids"] = new_admin_ids
    save_config(config)


def update_user_props(new_user_props):
    config["user_props"] = new_user_props
    save_config(config)


async def update_stats():
    previous_stats = None
    while True:
        await asyncio.sleep(90)
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(server + "/api/stats") as response:
                    if response.status == 200:
                        result_array = await response.json()
                        if result_array != previous_stats and any(result_array):
                            previous_stats = result_array
                            columns = ["№ участника", "Участник", "Баллы", "Рыбы"] + [
                                f"Баллы" for _ in range(len(result_array[0]) - 4)
                            ]
                            df = pd.DataFrame(result_array, columns=columns)
                            # Проверяем, есть ли в последнем столбце хотя бы одно ненулевое значение
                            if any(row[-1] > 0 for row in result_array):
                                # В последнем этапе есть ненулевые значения, турнир завершен.
                                async with user_props_lock:
                                    config["user_props"] = []
                                    save_config(config)
                                    user_props.clear()
                                    print(
                                        "Регистрация очищена после завершения турнира."
                                    )
                            df.loc[-1] = columns
                            df.index = df.index + 1
                            df = df.sort_index()

                            # Сохранение в Excel файл
                            file_path = "./statistics.xlsx"
                            df.to_excel(file_path, index=False, header=False)
                            document = FSInputFile("./statistics.xlsx")
                            for admin_id in admin_ids:
                                await bot.send_document(
                                    chat_id=admin_id, document=document
                                )
                            os.remove(file_path)
        except aiohttp.ClientError as e:
            print(f"Ошибка: {e}")
            await asyncio.sleep(1)
        except Exception as e:
            print(f"Ошибка: {e}")
            await asyncio.sleep(1)


async def check_registered_users():
    previous_user_count = len(user_props)
    while True:
        await asyncio.sleep(60)
        current_user_count = len(user_props)
        if current_user_count != previous_user_count and current_user_count > 0:
            previous_user_count = current_user_count
            # Создать эксель-файл
            df = pd.DataFrame()
            df["User"] = [user_props[i]["name"] for i in range(len(user_props))]
            df["Code"] = [user_props[i]["code"] for i in range(len(user_props))]
            df["Index"] = [i + 1 for i in range(len(user_props))]
            df["Time"] = [user_props[i]["timestamp"] for i in range(len(user_props))]
            file_path = "./registration.xlsx"
            df.to_excel(file_path, index=False, header=False)
            document = FSInputFile(file_path)
            for admin_id in admin_ids:
                await bot.send_document(chat_id=admin_id, document=document)
            # Удалить файл
            os.remove(file_path)


@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    if message.from_user.id in admin_ids:
        builder = InlineKeyboardBuilder()
        builder.row(
            InlineKeyboardButton(text="Прислать жеребьевку", callback_data="send_draw")
        )
        builder.row(InlineKeyboardButton(text="Узнать ID", callback_data="get_id"))
        builder.row(
            InlineKeyboardButton(text="Добавить админа", callback_data="add_admin")
        )
        builder.row(
            InlineKeyboardButton(
                text="Начать регистрацию", callback_data="start_registration"
            )
        )
        builder.row(
            InlineKeyboardButton(
                text="Закрыть регистрацию", callback_data="close_registration"
            )
        )
        builder.row(
            InlineKeyboardButton(
                text="Получить ссылку для зрителей", callback_data="get_email"
            )
        )
        builder.row(
            InlineKeyboardButton(
                text="Неготовые игроки", callback_data="get_unready_players"
            )
        )
        builder.row(
            InlineKeyboardButton(
                text="Обновить счет игрока", callback_data="update_player_score"
            )
        )
        builder.row(
            InlineKeyboardButton(
                text="Обновить угловые сектора", callback_data="update_corner_sectors"
            )
        )
        builder.row(
            InlineKeyboardButton(
                text="Очистить регистрацию", callback_data="clear_registration"
            )
        )
        builder.row(
            InlineKeyboardButton(text="Новый фон сайта", callback_data="new_background")
        )
        # Add the new button here

        await message.answer("Панель управления", reply_markup=builder.as_markup())
    else:
        await message.answer("Пожалуйста, отправьте свою Фамилию и имя.")


@dp.callback_query(F.data == "start_registration")
async def process_start_registration(callback_query: types.CallbackQuery):
    global registration_open
    registration_open = True
    await callback_query.answer("Регистрация начата.")


@dp.callback_query(F.data == "close_registration")
async def process_close_registration(callback_query: types.CallbackQuery):
    global registration_open
    registration_open = False
    await callback_query.answer("Регистрация закрыта.")


@dp.callback_query(F.data == "get_email")
async def process_callback_button(callback_query: types.CallbackQuery):
    await callback_query.message.answer(text=web_url)


@dp.callback_query(F.data == "clear_registration")
async def process_callback_button(callback_query: types.CallbackQuery):
    async with user_props_lock:
        config["user_props"] = []
        save_config(config)
        user_props.clear()
        await callback_query.answer("Регистрация очищена!")


@dp.callback_query(F.data == "update_player_score")
async def update_player_score(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    user_state[user_id] = "awaiting_score_update"
    request_message = await callback_query.message.answer(
        "Пожалуйста, присылайте 3 числа через пробел, где первое число - номер этапа, второе - номер игрока, третье - новый счет.",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="Назад", callback_data="back")]]
        ),
    )
    messages_to_delete[callback_query.message.chat.id] = [request_message.message_id]
    await callback_query.answer()


@dp.message(
    lambda message: user_state.get(message.from_user.id) == "awaiting_score_update"
)
async def handle_score_update(message: types.Message):
    user_id = message.from_user.id
    if user_state.get(user_id) == "awaiting_score_update":
        numbers = message.text.strip().split()
        if len(numbers) == 3:
            try:
                stage_number = int(numbers[0])
                player_number = int(numbers[1])
                new_score = int(numbers[2])

                # Send these numbers to the server
                data = {
                    "stage_number": stage_number,
                    "player_number": player_number,
                    "new_score": new_score,
                }
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        server + "/api/update_player_score", json=data
                    ) as response:
                        if response.status == 200:
                            await message.answer("Счет игрока обновлен.")
                        else:
                            await message.answer("Ошибка при обновлении счета игрока.")

            except ValueError:
                await message.answer(
                    "Ошибка: пожалуйста, отправьте 3 ЧИСЛА через пробел."
                )
        else:
            await message.answer("Ошибка: пожалуйста, отправьте 3 числа через пробел.")
        # Reset user state
        user_state[user_id] = None


@dp.message(lambda message: message.photo)
async def handle_photo(message: types.Message):
    user_id = message.from_user.id
    if user_state.get(user_id) == "awaiting_background_image":
        photo = message.photo[-1]
        file_id = photo.file_id
        file_path = await bot.get_file(file_id)
        file_url = f"https://api.telegram.org/file/bot{TOKEN}/{file_path.file_path}"
        async with aiohttp.ClientSession() as session:
            async with session.get(file_url) as response:
                file_data = await response.read()
        async with aiohttp.ClientSession() as session:
            form_data = FormData()
            form_data.add_field("photo", file_data, filename="photo.png")
            async with session.post(
                server + "/api/upload_photo",
                data=form_data,
            ) as response:
                if response.status == 200:
                    print("Фото отправлено на сервер")
                    await message.answer("Фото отправлено на сервер!")
        chat_id = message.chat.id
        message_id = messages_to_delete[chat_id][0]
        await bot.delete_message(chat_id=chat_id, message_id=message_id)
        user_state[user_id] = None


@dp.message(lambda message: message.text and message.from_user.id not in admin_ids)
async def handle_user_info(message: types.Message):
    global registration_open

    if registration_open:
        async with user_props_lock:
            # Проверка, существует ли уже пользователь с таким именем
            if not any(user["name"] == message.text for user in user_props):
                user_info = {
                    "id": message.from_user.id,
                    "code": (
                        str(len(user_props) + 1)
                        + "".join(
                            random.choices(string.ascii_letters + string.digits, k=3)
                        )
                    ),
                    "name": message.text,
                    "timestamp": str(datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
                }
                user_props.append(user_info)
                update_user_props(user_props)
                await message.answer("Спасибо, ваши данные сохранены. Ниже ваш код")
                await message.answer(f"{user_info['code']}")
            else:
                await message.answer("Пользователь с таким именем уже зарегистрирован.")
    else:
        await message.answer("Регистрация в данный момент закрыта.")


@dp.callback_query(F.data == "update_corner_sectors")
async def update_corner_sectors(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    user_state[user_id] = "awaiting_corner_sectors"
    request_message = await callback_query.message.answer(
        "Пожалуйста, присылайте номера всех угловых секторов через пробел.",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="Назад", callback_data="back")]]
        ),
    )
    messages_to_delete[callback_query.message.chat.id] = [request_message.message_id]
    await callback_query.answer()


@dp.callback_query(F.data == "send_draw")
async def process_callback_button(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    user_state[user_id] = "awaiting_excel_file"
    request_message = await callback_query.message.answer(
        "Пожалуйста, отправьте Excel файл.",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="Назад", callback_data="back")]]
        ),
    )
    messages_to_delete[callback_query.message.chat.id] = [request_message.message_id]

    await callback_query.answer()


@dp.message(
    lambda message: message.document
    and message.document.mime_type
    == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)
async def handle_excel(message: types.Message):
    user_id = message.from_user.id
    if user_state.get(user_id) == "awaiting_excel_file":
        document_id = message.document.file_id
        file = await bot.get_file(document_id)
        file_path = file.file_path
        file_data = await bot.download_file(file_path)
        df = pd.read_excel(file_data, header=None)
        data = df.values.tolist()

        first_row = [x for x in data[0] if isinstance(x, int)]
        response = requests.post(server + "/api/cornerSectors", json=first_row)

        data = data[1:]
        num_rows = len(data)
        num_cols = len(data[0])

        for j in range(3, num_cols):
            sector_dict = {}
            for i in range(num_rows):
                sector = data[i][j]
                player_number = data[i][2]
                if sector in sector_dict:
                    first_index = sector_dict[sector]
                    first_player_number = data[first_index][2]
                    first_sector = data[first_index][j]

                    data[first_index][j] = [player_number, sector]
                    data[i][j] = [first_player_number, first_sector]
                else:
                    sector_dict[sector] = i

        result_string = "\n".join([", ".join(map(str, row)) for row in data])

        response = requests.post(server + "/api/data", json=data)
        if response.status_code == 200:
            result_string = "Excel файл успешно отправлен на сервер."
        else:
            result_string = "Ошибка!!!"

        sent_message = await message.answer(
            text=result_string,
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="Назад", callback_data="back")]
                ]
            ),
        )

        if user_id in messages_to_delete:
            messages_to_delete[user_id].append(sent_message.message_id)
        else:
            messages_to_delete[user_id] = [sent_message.message_id]
        user_state[user_id] = None
    messages_to_delete[sent_message.message_id] = message.message_id


@dp.callback_query(F.data == "get_id")
async def get_id(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    await callback_query.message.answer(f"Ваш ID: {user_id}")
    await callback_query.answer()


@dp.callback_query(F.data == "get_unready_players")
async def get_unready_players(callback_query: types.CallbackQuery):
    response = requests.get(server + "/api/unready_players")
    if response.status_code == 200:
        unready_players = response.json()
        result_string = "\n".join([str(player) for player in unready_players])
        if len(unready_players) == 0 and result_string != "message":
            await callback_query.message.answer("Все игроки готовы")
        elif result_string != "message":
            await callback_query.message.answer(f"Неготовые игроки:\n{result_string}")
        else:
            await callback_query.message.answer(f"Проверьте, начался ли турнир")
    else:
        await callback_query.message.answer(
            f"Не удалось получить данные с сервера.\n Проверьте, идет ли турнир"
        )
    await callback_query.answer()


@dp.callback_query(F.data == "add_admin")
async def add_admin(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    user_state[user_id] = "awaiting_admin_id"

    request_message = await callback_query.message.answer(
        "Пожалуйста, отправьте ID нового админа.",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="Назад", callback_data="back")]]
        ),
    )
    messages_to_delete[callback_query.message.chat.id] = [request_message.message_id]
    await callback_query.answer()


@dp.message(lambda message: message.text.isdigit())
async def handle_admin_id(message: types.Message):
    user_id = message.from_user.id
    if user_state.get(user_id) == "awaiting_admin_id":
        new_admin_id = int(message.text)
        if new_admin_id not in admin_ids:
            admin_ids.append(new_admin_id)
            update_admin_ids(admin_ids)
            await message.answer(f"Новый админ добавлен, ID: {new_admin_id}")
        else:
            await message.answer(f"Этот админ уже добавлен, ID: {new_admin_id}")
        user_state[user_id] = None


@dp.message(
    lambda message: user_state.get(message.from_user.id) == "awaiting_corner_sectors"
)
async def handle_corner_sectors(message: types.Message):
    user_id = message.from_user.id
    text = message.text.strip()
    try:
        # Парсим числа из сообщения
        numbers = [int(num) for num in text.split()]
        if not numbers:
            raise ValueError("No numbers provided")
        # Отправляем на сервер
        data = numbers
        async with aiohttp.ClientSession() as session:
            async with session.post(
                server + "/api/cornerSectorsNew", json=data
            ) as response:
                if response.status == 200:
                    await message.answer("Данные успешно отправлены на сервер.")
                else:
                    await message.answer("Ошибка при отправке данных на сервер.")
    except ValueError:
        await message.answer(
            "Ошибка: пожалуйста, отправьте числа, разделенные пробелами."
        )
    finally:
        # Сбрасываем состояние пользователя
        user_state[user_id] = None


@dp.callback_query(lambda query: query.data == "back")
async def process_back_button(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    user_state[user_id] = None
    message_ids_to_delete = messages_to_delete.get(callback_query.message.chat.id, [])

    for message_id in message_ids_to_delete:
        await bot.delete_message(callback_query.message.chat.id, message_id)

    await bot.delete_message(
        callback_query.message.chat.id, callback_query.message.message_id
    )

    messages_to_delete[callback_query.message.chat.id] = []

    await callback_query.answer()


async def main():
    asyncio.create_task(check_registered_users())
    asyncio.create_task(update_stats())
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
