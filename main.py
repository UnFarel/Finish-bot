import logging
import json
import os
import glob
import asyncio
from typing import List, Union
from aiogram import Bot, Dispatcher, executor, types
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher.handler import CancelHandler
from aiogram.dispatcher.middlewares import BaseMiddleware


API_TOKEN = 'token'


logging.basicConfig(level=logging.INFO)


bot = Bot(token=API_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

class CloudState(StatesGroup):
    photo = State()
    location = State()


class AlbumMiddleware(BaseMiddleware):
    album_data: dict = {}

    def __init__(self, latency: Union[int, float] = 0.01):
        self.latency = latency
        super().__init__()

    async def on_process_message(self, message: types.Message, data: dict):
        if not message.media_group_id:
            return

        try:
            self.album_data[message.media_group_id].append(message)
            raise CancelHandler()  
        except KeyError:
            self.album_data[message.media_group_id] = [message]
            await asyncio.sleep(self.latency)

            message.conf["is_last"] = True
            data["album"] = self.album_data[message.media_group_id]

    async def on_post_process_message(self, message: types.Message, result: dict, data: dict):
        if message.media_group_id and message.conf.get("is_last"):
            del self.album_data[message.media_group_id]


def write_json(new_data, filename='js_storage.json'):
    with open(filename,'r+') as file:
        file_data = json.load(file)
        file_data["info"].append(new_data)
        file.seek(0)
        json.dump(file_data, file, indent = 4)


@dp.message_handler(commands=['start', 'help'])
async def send_welcome(message: types.Message):
    await CloudState.photo.set()
    await message.reply(f"Доброго времени суток, {message.from_user.full_name}, загрузите, пожалуйста, фотографию.")


@dp.message_handler(content_types=types.ContentType.PHOTO, state=CloudState.photo)
async def download_photo(message: types.Message, state: FSMContext):
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    keyboard.add(types.KeyboardButton('Отправить геолокацию', request_location = True))
    if message.media_group_id == None:
        await message.photo[-1].download(destination_dir="storage/")
        await message.answer("Вау, красивые фотки, где вы их сделали?", reply_markup=keyboard)
    else:
        return await message.answer("Извини, но я работаю только с одной фотографией." + "\nПришли мне только ОДНУ фотография, пожалуйста!")
    await CloudState.next()


@dp.message_handler(content_types = ['location', 'audio', 'text', 'video', 'document', 'game', 'poll', 'dice', 'contact'], state=CloudState.photo)
async def failed_process2(message: types.Message, state: FSMContext):
    return await message.reply("Извини, но это не фотография"+ "\nПопробуй всё-таки загрузить фотографию")


@dp.message_handler(content_types = ['photo', 'audio', 'text', 'video', 'document', 'game', 'poll', 'dice', 'contact'], state=CloudState.location)
async def failed_process1(message: types.Message, state: FSMContext):
    return await message.reply("Извини, но это не локация" + "\nПопробуй всё-таки загрузить локацию")


@dp.message_handler(content_types = ['location', 'audio', 'text', 'video', 'document', 'game', 'poll', 'dice', 'contact'], state=None)
async def failed_process(message: types.Message, state: FSMContext):
    return await message.reply("Извини, но сначала нужно запустить меня" + 'Выбери в меню "запустить" или напиши "/start"')

@dp.message_handler(content_types=['location'], state=CloudState.location)
async def location_graber(message: types.Message, state: FSMContext):
    lat = message.location.latitude
    lon = message.location.longitude
    list_of_files = glob.glob('storage/photos/*')
    latest_file = max(list_of_files, key=os.path.getmtime)
    loc_collection = {
        "user_id": f"{message.from_user.id}",
        "name": f"{message.from_user.full_name}",
        "photo url": f"{latest_file}",
        "latitude": f"{lat}",
        "longitude": f"{lon}",
        "date": f"{message.date}" 
    }
    write_json(loc_collection)
    await message.answer("О, спасибо, я запомню!)" +
                         "\nЯ бы с удовольствием посмотрел еще фотографии!)" + '\nЕсли хочешь пришли ещё фоток, я обязательно их гляну.', reply=False, reply_markup=types.ReplyKeyboardRemove())
    await CloudState.photo.set()



if __name__ == '__main__':
    dp.middleware.setup(AlbumMiddleware())
    executor.start_polling(dp, skip_updates=True)
