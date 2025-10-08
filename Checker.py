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
from datetime import datetime, timedelta

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
        self.subscriptions = {}  # Хранилище подписок
        
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

    def refresh_cookie_with_auth_key(self, cookie_data, auth_key):
        """Обновление куки через auth key"""
        try:
            # Форматируем куки для использования в запросе
            if not cookie_data.startswith('.ROBLOSECURITY='):
                cookie_string = f'.ROBLOSECURITY={cookie_data}'
            else:
                cookie_string = cookie_data
            
            headers = {
                'User-Agent': self.get_random_user_agent(),
                'Cookie': cookie_string,
                'Content-Type': 'application/json',
                'X-CSRF-TOKEN': auth_key
            }
            
            # Запрос на обновление сессии через Roblox API
            refresh_url = 'https://auth.roblox.com/v2/logout'
            response = requests.post(refresh_url, headers=headers, timeout=10)
            
            if response.status_code == 200 or response.status_code == 403:
                # Получаем обновленные куки из заголовков
                if 'set-cookie' in response.headers:
                    new_cookies = response.headers['set-cookie']
                    # Ищем новую куки ROBLOSECURITY
                    roblosecurity_match = re.search(r'\.ROBLOSECURITY=([^;]+)', new_cookies)
                    if roblosecurity_match:
                        new_cookie = roblosecurity_match.group(1)
                        return True, new_cookie, "✅ Куки успешно обновлена"
            
            return False, cookie_data, "❌ Не удалось обновить куки"
            
        except Exception as e:
            print(f"❌ Ошибка обновления куки: {e}")
            return False, cookie_data, f"❌ Ошибка: {str(e)}"

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
                    return True, cookie_clean, f"✅ VALID - User: {username} (ID: {user_id})", username, user_id
                
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
                    return True, cookie_clean, f"✅ VALID - User: {username} (ID: {user_id})", username, user_id
            
            # Пробуем домашнюю страницу
            home_response = self.make_robust_request('https://www.roblox.com/home', headers)
            
            if home_response and home_response.status_code == 200:
                current_url = home_response.url.lower()
                if 'login' not in current_url and 'signup' not in current_url:
                    self.valid_count += 1
                    return True, cookie_clean, "✅ VALID - Home page access", "Unknown", "Unknown"
        
        except Exception as e:
            print(f"❌ Ошибка проверки: {e}")
            return False, cookie_clean, f"❌ ERROR - {str(e)}", "Unknown", "Unknown"
        
        return False, cookie_clean, "❌ INVALID - All checks failed", "Unknown", "Unknown"

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
            'usernames': [],
            'user_ids': []
        }
        
        for i, cookie in enumerate(cookies, 1):
            print(f"🔍 Проверяю куки {i}/{total}")
            is_valid, clean_cookie, status, username, user_id_val = self.simple_cookie_validation(cookie)
            
            if is_valid:
                valid_cookies.append(clean_cookie)
                self.user_cookies[user_id]['valid_cookies'].append(clean_cookie)
                self.user_cookies[user_id]['usernames'].append(username)
                self.user_cookies[user_id]['user_ids'].append(user_id_val)
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

    def subscribe_user(self, user_id, cookie_index, auth_key):
        """Подписка пользователя на обновление куки"""
        if user_id not in self.user_cookies:
            return False, "❌ Куки не найдены"
        
        if cookie_index >= len(self.user_cookies[user_id]['valid_cookies']):
            return False, "❌ Неверный индекс куки"
        
        cookie = self.user_cookies[user_id]['valid_cookies'][cookie_index]
        username = self.user_cookies[user_id]['usernames'][cookie_index]
        user_id_val = self.user_cookies[user_id]['user_ids'][cookie_index]
        
        # Сохраняем подписку
        self.subscriptions[user_id] = {
            'cookie': cookie,
            'username': username,
            'user_id': user_id_val,
            'auth_key': auth_key,
            'subscribe_date': datetime.now(),
            'last_refresh': datetime.now()
        }
        
        return True, f"✅ Подписка активирована для {username}"

    def refresh_subscribed_cookie(self, user_id):
        """Обновление куки по подписке"""
        if user_id not in self.subscriptions:
            return False, "❌ Подписка не найдена"
        
        subscription = self.subscriptions[user_id]
        cookie = subscription['cookie']
        auth_key = subscription['auth_key']
        
        # Обновляем куки
        success, new_cookie, message = self.refresh_cookie_with_auth_key(cookie, auth_key)
        
        if success:
            # Обновляем подписку
            self.subscriptions[user_id]['cookie'] = new_cookie
            self.subscriptions[user_id]['last_refresh'] = datetime.now()
            
            # Проверяем валидность новой куки
            is_valid, _, status, username, _ = self.simple_cookie_validation(new_cookie)
            if is_valid:
                return True, f"✅ Куки успешно обновлена и валидна\n👤 Пользователь: {username}"
            else:
                return False, "❌ Куки обновлена, но не прошла валидацию"
        else:
            return False, message

checker = RobloxCookieChecker()

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🔍 Бот для проверки Roblox куки активирован\n\n"
        "Простая и быстрая проверка валидности куки.\n\n"
        "Команды:\n"
        "/start - запуск\n"
        "/stats - статистика\n"
        "/mysub - моя подписка\n\n"
        "Просто отправьте куки текстом или файлом для проверки."
    )

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    stats_text = f"""
📊 СТАТИСТИКА ПРОВЕРОК:

• Всего проверено: {checker.checked_count}
• Валидных куки: {checker.valid_count}
• Невалидных: {checker.checked_count - checker.valid_count}
• Процент валидных: {checker.valid_count/max(1, checker.checked_count)*100:.1f}%
• Активных подписок: {len(checker.subscriptions)}
"""
    await update.message.reply_text(stats_text)

async def mysub_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if user_id in checker.subscriptions:
        subscription = checker.subscriptions[user_id]
        sub_date = subscription['subscribe_date'].strftime("%d.%m.%Y %H:%M")
        last_refresh = subscription['last_refresh'].strftime("%d.%m.%Y %H:%M")
        
        sub_info = f"""
📋 ИНФОРМАЦИЯ О ПОДПИСКЕ:

👤 Пользователь: {subscription['username']}
🆔 ID: {subscription['user_id']}
📅 Дата подписки: {sub_date}
🔄 Последнее обновление: {last_refresh}

Доступные действия:
"""
        keyboard = [
            [InlineKeyboardButton("🔄 Обновить куки", callback_data="refresh_cookie")],
            [InlineKeyboardButton("❌ Отменить подписку", callback_data="cancel_subscription")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(sub_info, reply_markup=reply_markup)
    else:
        await update.message.reply_text("❌ У вас нет активной подписки")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if update.message.text:
        text_content = update.message.text
        await update.message.reply_text("🔍 Ищу куки в тексте...")
        
        valid_cookies, invalid_cookies, process_results = checker.process_multiple_cookies(text_content, user_id)
        
        if not valid_cookies and not invalid_cookies:
            await update.message.reply_text("❌ Не удалось найти куки в тексте.")
            return
        
        # Создаем клавиатуру с кнопками
        if valid_cookies:
            keyboard = [
                [InlineKeyboardButton("📁 Распределить по файлам", callback_data="distribute_files")],
                [InlineKeyboardButton("📦 Скачать общий файл", callback_data="download_combined")],
                [InlineKeyboardButton("💎 Подписка валидатор", callback_data="subscription_menu")]
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
        
        # Создаем клавиатуру с кнопками
        if valid_cookies:
            keyboard = [
                [InlineKeyboardButton("📁 Распределить по файлам", callback_data="distribute_files")],
                [InlineKeyboardButton("📦 Скачать общий файл", callback_data="download_combined")],
                [InlineKeyboardButton("💎 Подписка валидатор", callback_data="subscription_menu")]
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
    
    elif query.data == "subscription_menu":
        if user_id not in checker.user_cookies or not checker.user_cookies[user_id]['valid_cookies']:
            await query.edit_message_text("❌ Нет валидных куки для подписки")
            return
        
        valid_cookies = checker.user_cookies[user_id]['valid_cookies']
        usernames = checker.user_cookies[user_id]['usernames']
        
        # Создаем кнопки для выбора куки
        keyboard = []
        for i, (cookie, username) in enumerate(zip(valid_cookies, usernames)):
            keyboard.append([InlineKeyboardButton(f"👤 {username}", callback_data=f"subscribe_{i}")])
        
        keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="back_to_main")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "💎 ВЫБЕРИТЕ КУКИ ДЛЯ ПОДПИСКИ:\n\n"
            "Подписка включает:\n"
            "• Автоматическую проверку валидности\n"
            "• Обновление куки через auth key\n"
            "• Уведомления о статусе\n\n"
            "Выберите аккаунт:",
            reply_markup=reply_markup
        )
    
    elif query.data.startswith("subscribe_"):
        cookie_index = int(query.data.split("_")[1])
        await query.edit_message_text(
            f"🔐 Введите auth key для подписки:\n\n"
            f"Для получения auth key:\n"
            f"1. Откройте браузер\n"
            f"2. Перейдите на Roblox.com\n"
            f"3. Откройте Developer Tools (F12)\n"
            f"4. Найдите заголовок X-CSRF-TOKEN в запросах\n\n"
            f"Отправьте auth key текстовым сообщением:"
        )
        # Сохраняем индекс выбранной куки в контексте
        context.user_data['selected_cookie_index'] = cookie_index
    
    elif query.data == "refresh_cookie":
        await query.edit_message_text("🔄 Обновляю куки...")
        success, message = checker.refresh_subscribed_cookie(user_id)
        await query.edit_message_text(message)
    
    elif query.data == "cancel_subscription":
        if user_id in checker.subscriptions:
            username = checker.subscriptions[user_id]['username']
            del checker.subscriptions[user_id]
            await query.edit_message_text(f"❌ Подписка для {username} отменена")
        else:
            await query.edit_message_text("❌ Подписка не найдена")
    
    elif query.data == "back_to_main":
        await query.edit_message_text("🔙 Возврат в главное меню")

async def handle_auth_key(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка ввода auth key"""
    user_id = update.effective_user.id
    auth_key = update.message.text.strip()
    
    if 'selected_cookie_index' not in context.user_data:
        await update.message.reply_text("❌ Сначала выберите куки для подписки")
        return
    
    cookie_index = context.user_data['selected_cookie_index']
    
    # Активируем подписку
    success, message = checker.subscribe_user(user_id, cookie_index, auth_key)
    
    if success:
        subscription = checker.subscriptions[user_id]
        sub_info = f"""
✅ ПОДПИСКА АКТИВИРОВАНА

👤 Пользователь: {subscription['username']}
🆔 ID: {subscription['user_id']}
📅 Дата активации: {subscription['subscribe_date'].strftime("%d.%m.%Y %H:%M")}

Теперь вы можете обновлять куки через /mysub
"""
        await update.message.reply_text(sub_info)
    else:
        await update.message.reply_text(message)
    
    # Очищаем контекст
    context.user_data.pop('selected_cookie_index', None)

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
    app.add_handler(CommandHandler("mysub", mysub_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_auth_key))
    app.add_handler(MessageHandler(filters.TEXT | filters.Document.ALL, handle_message))
    app.add_handler(CallbackQueryHandler(button_handler))
    
    print("🤖 Бот проверки Roblox куки запущен...")
    print("✅ Бот готов к работе!")
    app.run_polling()

if __name__ == "__main__":
    main()
