import os
import logging
import re
import random
import time
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
import requests
import json
from datetime import datetime

# Конфигурация
BOT_TOKEN = "8204086100:AAFmfYGPLqtBpSpJk1FgyCwU87l6K2ZieTo"

logging.basicConfig(level=logging.INFO)

class RobloxCookieChecker:
    def __init__(self):
        self.valid_count = 0
        self.checked_count = 0
        self.user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/120.0',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Edge/120.0.0.0'
        ]
        self.user_cookies = {}  # Хранилище куки по пользователям
        
    def get_random_user_agent(self):
        """Возвращает случайный User-Agent"""
        return random.choice(self.user_agents)
    
    def make_robust_request(self, url, headers, max_retries=3):
        """Выполняет запрос с повторными попытками и задержками"""
        for attempt in range(max_retries):
            try:
                response = requests.get(url, headers=headers, timeout=15)
                
                # Проверяем на лимит запросов
                if response.status_code == 429:
                    wait_time = (2 ** attempt) + random.uniform(1, 3)
                    print(f"⚠️ Rate limit hit, waiting {wait_time:.1f}s...")
                    time.sleep(wait_time)
                    continue
                    
                return response
                
            except requests.exceptions.RequestException as e:
                print(f"⚠️ Request error (attempt {attempt + 1}): {e}")
                if attempt < max_retries - 1:
                    wait_time = (2 ** attempt) + random.uniform(1, 2)
                    time.sleep(wait_time)
                    
        return None

    def extract_cookies_from_text(self, text):
        """Извлечение куки из текста"""
        cookies = []
        
        # Метод 1: Поиск по стандартному паттерну
        warning_pattern = r'_\|WARNING:-DO-NOT-SHARE-THIS[^\s]+(?:\|[^\s]*)*'
        warning_matches = re.findall(warning_pattern, text)
        
        for match in warning_matches:
            cookie_candidate = match.strip()
            if len(cookie_candidate) > 50:
                cookies.append(cookie_candidate)
                print(f"🔍 Найдена куки: {cookie_candidate[:80]}...")
        
        # Метод 2: Обработка одиночной чистой куки
        if not cookies:
            clean_text = text.strip()
            if (len(clean_text) > 300 and 
                '_|WARNING:-DO-NOT-SHARE-THIS' in clean_text and
                'Sharing-this-will-allow-someone-to-log-in-as-you' in clean_text):
                cookies.append(clean_text)
                print(f"🔍 Найдена чистая куки: {clean_text[:80]}...")
        
        return cookies

    def clean_cookie_string(self, cookie_data):
        """Очистка куки"""
        return cookie_data.strip()

    def simple_cookie_validation(self, cookie_data):
        """Проверка валидности куки"""
        self.checked_count += 1
        
        cookie_clean = self.clean_cookie_string(cookie_data)
        
        # Форматируем для использования в запросе
        if not cookie_clean.startswith('.ROBLOSECURITY='):
            cookie_string = f'.ROBLOSECURITY={cookie_clean}'
        else:
            cookie_string = cookie_clean
        
        # Случайный User-Agent для каждого запроса
        user_agent = self.get_random_user_agent()
        headers = {
            'User-Agent': user_agent,
            'Cookie': cookie_string,
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'en-US,en;q=0.9',
            'Referer': 'https://www.roblox.com/',
            'Origin': 'https://www.roblox.com'
        }
        
        # Добавляем небольшую задержку между запросами
        time.sleep(random.uniform(1, 3))
        
        try:
            # Пробуем основной API
            api_url = 'https://users.roblox.com/v1/users/authenticated'
            response = self.make_robust_request(api_url, headers)
            
            if response and response.status_code == 200:
                user_data = response.json()
                if 'id' in user_data and user_data['id'] > 0:
                    username = user_data.get('name', 'Unknown')
                    user_id = user_data['id']
                    self.valid_count += 1
                    return True, cookie_clean, f"✅ VALID - User: {username} (ID: {user_id})", username
                
            # Пробуем mobile API с другим User-Agent
            mobile_headers = headers.copy()
            mobile_headers['User-Agent'] = 'Roblox/iOS'
            mobile_url = 'https://www.roblox.com/mobileapi/userinfo'
            mobile_response = self.make_robust_request(mobile_url, mobile_headers)
            
            if mobile_response and mobile_response.status_code == 200:
                mobile_data = mobile_response.json()
                if 'UserID' in mobile_data and mobile_data['UserID'] > 0:
                    username = mobile_data.get('UserName', 'Unknown')
                    user_id = mobile_data['UserID']
                    self.valid_count += 1
                    return True, cookie_clean, f"✅ VALID - User: {username} (ID: {user_id})", username
            
            # Пробуем домашнюю страницу
            home_response = self.make_robust_request('https://www.roblox.com/home', headers)
            
            if home_response and home_response.status_code == 200:
                current_url = home_response.url.lower()
                if 'login' not in current_url and 'signup' not in current_url:
                    self.valid_count += 1
                    return True, cookie_clean, "✅ VALID - Home page access", "Unknown"
        
        except Exception as e:
            print(f"❌ Ошибка проверки: {e}")
            return False, cookie_clean, f"❌ ERROR - {str(e)}", "Unknown"
        
        return False, cookie_clean, "❌ INVALID - All checks failed", "Unknown"

    def process_multiple_cookies(self, text, user_id):
        """Обработка множественных куки с сохранением для распределения"""
        cookies = self.extract_cookies_from_text(text)
        valid_cookies = []
        invalid_cookies = []
        results = []
        
        print(f"🔍 Найдено куки в тексте: {len(cookies)}")
        
        total = len(cookies)
        if total == 0:
            return [], [], "❌ В тексте не найдено ни одной куки"
        
        # Сохраняем куки для пользователя
        self.user_cookies[user_id] = {
            'all_cookies': cookies,
            'valid_cookies': [],
            'invalid_cookies': [],
            'usernames': []
        }
        
        for i, cookie in enumerate(cookies, 1):
            print(f"🔍 Проверяю куки {i}/{total}")
            is_valid, clean_cookie, status, username = self.simple_cookie_validation(cookie)
            
            if is_valid:
                valid_cookies.append(clean_cookie)
                self.user_cookies[user_id]['valid_cookies'].append(clean_cookie)
                self.user_cookies[user_id]['usernames'].append(username)
                results.append(f"✅ {i}/{total}: {status}")
            else:
                invalid_cookies.append(clean_cookie)
                self.user_cookies[user_id]['invalid_cookies'].append(clean_cookie)
                results.append(f"❌ {i}/{total}: {status}")
        
        return valid_cookies, invalid_cookies, "\n".join(results)

    def create_individual_files(self, user_id):
        """Создание отдельных файлов для каждой куки"""
        if user_id not in self.user_cookies:
            return None
        
        user_data = self.user_cookies[user_id]
        valid_cookies = user_data['valid_cookies']
        usernames = user_data['usernames']
        
        if not valid_cookies:
            return None
        
        # Создаем ZIP архив с отдельными файлами
        import zipfile
        timestamp = datetime.now().strftime("%H%M%S")
        zip_filename = f"individual_cookies_{user_id}_{timestamp}.zip"
        
        with zipfile.ZipFile(zip_filename, 'w') as zipf:
            for i, (cookie, username) in enumerate(zip(valid_cookies, usernames), 1):
                # Создаем имя файла
                safe_username = re.sub(r'[^\w\-_]', '_', username)
                filename = f"cookie_{i}_{safe_username}.txt"
                
                # Создаем временный файл
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(cookie)
                
                # Добавляем в ZIP
                zipf.write(filename, filename)
                
                # Удаляем временный файл
                os.remove(filename)
        
        return zip_filename

checker = RobloxCookieChecker()

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🔍 Бот для проверки Roblox куки активирован\n\n"
        "Простая и быстрая проверка валидности куки.\n\n"
        "Команды:\n"
        "/start - запуск\n"
        "/stats - статистика\n\n"
        "Просто отправьте куки текстом или файлом для проверки."
    )

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    stats_text = f"""
📊 СТАТИСТИКА ПРОВЕРОК:

• Всего проверено: {checker.checked_count}
• Валидных куки: {checker.valid_count}
• Невалидных: {checker.checked_count - checker.valid_count}
• Процент валидных: {checker.valid_count/max(1, checker.checked_count)*100:.1f}%
"""
    await update.message.reply_text(stats_text)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if update.message.text:
        text_content = update.message.text
        await update.message.reply_text("🔍 Ищу куки в тексте...")
        
        valid_cookies, invalid_cookies, process_results = checker.process_multiple_cookies(text_content, user_id)
        
        if not valid_cookies and not invalid_cookies:
            await update.message.reply_text("❌ Не удалось найти куки в тексте.")
            return
        
        # Создаем клавиатуру с кнопкой распределения
        if valid_cookies:
            keyboard = [
                [InlineKeyboardButton("📁 Распределить по файлам", callback_data="distribute_files")],
                [InlineKeyboardButton("📦 Скачать общий файл", callback_data="download_combined")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            summary = f"""
📋 РЕЗУЛЬТАТЫ:

• Всего обработано: {len(valid_cookies) + len(invalid_cookies)}
• ✅ Валидных: {len(valid_cookies)}
• ❌ Невалидных: {len(invalid_cookies)}
• 📊 Успех: {len(valid_cookies)/(len(valid_cookies) + len(invalid_cookies))*100:.1f}%

Выберите действие:
"""
            await update.message.reply_text(summary, reply_markup=reply_markup)
        else:
            await send_results(update, user_id, valid_cookies, invalid_cookies, process_results)

    elif update.message.document:
        file = await update.message.document.get_file()
        file_path = f"temp_{user_id}.txt"
        await file.download_to_drive(file_path)
        
        with open(file_path, 'r', encoding='utf-8') as f:
            file_content = f.read()
        
        await update.message.reply_text("🔍 Обрабатываю файл...")
        
        valid_cookies, invalid_cookies, process_results = checker.process_multiple_cookies(file_content, user_id)
        
        if not valid_cookies and not invalid_cookies:
            await update.message.reply_text("❌ В файле не найдено куки")
            os.remove(file_path)
            return
        
        # Создаем клавиатуру с кнопкой распределения
        if valid_cookies:
            keyboard = [
                [InlineKeyboardButton("📁 Распределить по файлам", callback_data="distribute_files")],
                [InlineKeyboardButton("📦 Скачать общий файл", callback_data="download_combined")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            summary = f"""
📋 РЕЗУЛЬТАТЫ:

• Всего обработано: {len(valid_cookies) + len(invalid_cookies)}
• ✅ Валидных: {len(valid_cookies)}
• ❌ Невалидных: {len(invalid_cookies)}
• 📊 Успех: {len(valid_cookies)/(len(valid_cookies) + len(invalid_cookies))*100:.1f}%

Выберите действие:
"""
            await update.message.reply_text(summary, reply_markup=reply_markup)
        else:
            await send_results(update, user_id, valid_cookies, invalid_cookies, process_results)
        os.remove(file_path)

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик нажатий кнопок"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    if query.data == "distribute_files":
        await query.edit_message_text("📁 Создаю отдельные файлы для каждой куки...")
        
        zip_filename = checker.create_individual_files(user_id)
        
        if zip_filename and os.path.exists(zip_filename):
            with open(zip_filename, 'rb') as zip_file:
                await query.message.reply_document(
                    document=zip_file,
                    caption=f"📁 Архив с {len(checker.user_cookies[user_id]['valid_cookies'])} отдельными файлами куки"
                )
            os.remove(zip_filename)
        else:
            await query.message.reply_text("❌ Не удалось создать файлы распределения")
    
    elif query.data == "download_combined":
        await send_results(query, user_id, 
                          checker.user_cookies[user_id]['valid_cookies'], 
                          checker.user_cookies[user_id]['invalid_cookies'], 
                          "")

async def send_results(update, user_id, valid_cookies, invalid_cookies, process_results):
    """Отправка результатов проверки"""
    timestamp = datetime.now().strftime("%H%M%S")
    
    # Сводка
    total = len(valid_cookies) + len(invalid_cookies)
    summary = f"""
📋 РЕЗУЛЬТАТЫ:

• Всего обработано: {total}
• ✅ Валидных: {len(valid_cookies)}
• ❌ Невалидных: {len(invalid_cookies)}
• 📊 Успех: {len(valid_cookies)/total*100:.1f}%
"""
    if hasattr(update, 'message'):
        await update.message.reply_text(summary)
    else:
        await update.edit_message_text(summary)
    
    if valid_cookies:
        valid_filename = f"valid_{user_id}_{timestamp}.txt"
        with open(valid_filename, 'w', encoding='utf-8') as f:
            for cookie in valid_cookies:
                f.write(cookie + '\n\n')
        
        caption = f"✅ ВАЛИДНЫЕ КУКИ: {len(valid_cookies)} шт."
        if hasattr(update, 'message'):
            await update.message.reply_document(
                document=open(valid_filename, 'rb'),
                caption=caption
            )
        else:
            await update.message.reply_document(
                document=open(valid_filename, 'rb'),
                caption=caption
            )
        os.remove(valid_filename)
    
    if invalid_cookies:
        invalid_filename = f"invalid_{user_id}_{timestamp}.txt"
        with open(invalid_filename, 'w', encoding='utf-8') as f:
            for cookie in invalid_cookies:
                f.write(cookie + '\n\n')
        
        if hasattr(update, 'message'):
            await update.message.reply_document(
                document=open(invalid_filename, 'rb'),
                caption=f"❌ НЕВАЛИДНЫЕ КУКИ: {len(invalid_cookies)} шт."
            )
        else:
            await update.message.reply_document(
                document=open(invalid_filename, 'rb'),
                caption=f"❌ НЕВАЛИДНЫЕ КУКИ: {len(invalid_cookies)} шт."
            )
        os.remove(invalid_filename)

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("stats", stats_command))
    app.add_handler(MessageHandler(filters.TEXT | filters.Document.ALL, handle_message))
    app.add_handler(CallbackQueryHandler(button_handler))
    
    print("🤖 Бот проверки Roblox куки запущен...")
    print("✅ Бот готов к работе!")
    app.run_polling()

if __name__ == "__main__":
    main()

if __name__ == "__main__":
    main()
