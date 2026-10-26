import asyncio
import logging
import os
import re
from urllib.parse import urljoin

import requests
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import BufferedInputFile
from bs4 import BeautifulSoup

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


def extract_image_urls(html: str, base_url: str) -> list[str]:
    soup = BeautifulSoup(html, "lxml")
    urls = set()
    for img in soup.find_all("img"):
        src = img.get("src")
        if src:
            urls.add(urljoin(base_url, src))
        for attr in ("data-src", "data-original", "data-lazy-src"):
            lazy = img.get(attr)
            if lazy:
                urls.add(urljoin(base_url, lazy))
        srcset = img.get("srcset")
        if srcset:
            first = srcset.split(",")[0].strip().split(" ")[0]
            urls.add(urljoin(base_url, first))
    return [u for u in urls if u.startswith("http")]


def download_image(url: str):
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        return resp.content
    except Exception as e:
        logging.warning(f"Не удалось скачать {url}: {e}")
        return None


@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer("Пришлите ссылку на новость с mos.ru — я извлеку все изображения и отправлю их.")


@dp.message()
async def handle_url(message: types.Message):
    url = message.text.strip()
    if not re.search(r"https?://(www\.)?mos\.ru/", url):
        await message.answer("Пожалуйста, пришлите ссылку с домена mos.ru.")
        return

    await message.answer("🔍 Загружаю страницу и ищу изображения…")

    try:
        page = requests.get(url, headers=HEADERS, timeout=20)
        page.raise_for_status()
    except Exception as e:
        await message.answer(f"❌ Не удалось открыть страницу: {e}")
        return

    image_urls = extract_image_urls(page.text, url)
    if not image_urls:
        await message.answer("😕 На этой странице не найдено изображений.")
        return

    await message.answer(f"🖼 Найдено {len(image_urls)} изображений. Отправляю…")

    for idx, img_url in enumerate(image_urls, start=1):
        data = download_image(img_url)
        if not data:
            continue
        ext = img_url.split("?")[0].split(".")[-1].lower()
        if ext not in ("jpg", "jpeg", "png", "webp", "gif"):
            ext = "jpg"
        file = BufferedInputFile(data, filename=f"image_{idx}.{ext}")
        try:
            await message.answer_photo(file, caption=f"#{idx}")
        except Exception as e:
            logging.error(f"Ошибка отправки фото {img_url}: {e}")

    await message.answer("✅ Готово!")


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())