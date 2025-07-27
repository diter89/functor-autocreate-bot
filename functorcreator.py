import logging
import sqlite3
import random
import re
import time
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from faker import Faker
from pymailtm import MailTm, Account
import requests

API_TOKEN = ''

bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# Configure logging
logging.basicConfig(level=logging.INFO)

class Form(StatesGroup):
    email_locale = State()
    invitation_code = State()
    claim_account = State()

class APIHandler:
    def __init__(self):
        self.ua = UserAgent()
        self.mailtm = MailTm()
        self.current_account = None
        self.faker = Faker()
        self.headers = {
            "User-Agent": self.ua.random,
            "Content-Type": "application/json",
        }
        self.base_urls = {
            "signup": "https://node.securitylabs.xyz/api/v1/auth/signup-user",
            "verify_otp": "https://node.securitylabs.xyz/api/v1/auth/verify-otp-user",
            "user_data": "https://node.securitylabs.xyz/api/v1/users",
            "earn": "https://node.securitylabs.xyz/api/v1/users/earn/",
        }
        self.db_path = "database.db"
        self.init_database()

    def init_database(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS accounts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL,
                password TEXT NOT NULL,
                user_id TEXT NOT NULL,
                access_token TEXT NOT NULL
            )
        """)
        conn.commit()
        conn.close()

    def save_to_database(self, email, password, user_id, access_token):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO accounts (email, password, user_id, access_token)
            VALUES (?, ?, ?, ?)
        """, (email, password, user_id, access_token))
        conn.commit()
        conn.close() 

    def get_accounts_from_database(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT email, password, user_id, access_token FROM accounts")
        accounts = cursor.fetchall()
        conn.close()
        return accounts

    def post(self, endpoint, payload):
        response = requests.post(self.base_urls[endpoint], json=payload, headers=self.headers)
        return response

    def get(self, endpoint, path=None):
        url = self.base_urls[endpoint]
        if path:
            url += str(path)
        response = requests.get(url, headers=self.headers)
        return response

    def set_auth_token(self, token):
        self.headers["Authorization"] = f"Bearer {token}"

    def signup(self, email, password, invitation_code):
        payload = {
            "email": email,
            "password": password,
            "acceptTermsAndConditions": True,
            "authType": "otp",
            "from": "extension",
            "invitationCode": invitation_code,
            "referralCode": "",
        }
        return self.post("signup", payload)

    def verify_otp(self, email, otp):
        payload = {"email": email, "otp": otp}
        return self.post("verify_otp", payload)

    def get_user_data(self):
        return self.get("user_data")

    def get_earn_data(self, user_id):
        return self.get("earn", path=user_id)

    def claim_earn(self, user_id, access_token):
        self.set_auth_token(access_token)
        response = self.get("earn", path=user_id)
        logging.info(f"Claim earn response: {response.status_code}")
        return response

    def create_email_account(self):
        try:
            account = self.mailtm.get_account()
            self.current_account = account
            logging.info(f"Akun email berhasil dibuat: {account.address}")
            return account.address
        except Exception as e:
            logging.error(f"Gagal membuat akun email: {e}")
            return None

    def fetch_email_messages(self):
        if not self.current_account:
            raise Exception("Akun email belum dibuat!")
        try:
            messages = self.current_account.get_messages()
            return messages
        except Exception as e:
            logging.error(f"Gagal mengambil pesan: {e}")
            return []

    def extract_otp_from_message(self, message_text):
        match = re.search(r'code is:\n(\d{6})\n', message_text)
        if match:
            otp = match.group(1)
            return otp
        else:
            logging.warning("OTP tidak ditemukan dalam pesan.")
            return None

    def generate_random_password(self, locale="en_US"):
        self.faker = Faker(locale)
        password = (
            self.faker.name().replace(" ", "").capitalize()
            + str(self.faker.random_int(min=1000, max=9999))
        )
        logging.debug(f"Password acak tergenerate: {password}")
        return password

    def crack_password_animation(self, real_otp):
        logging.info("Memulai proses ekstraksi OTP...")
        chars = "0123456789"
        otp_length = len(real_otp)
        otp = list("*" * otp_length)
        for i in range(otp_length):
            for _ in range(20):
                otp[i] = random.choice(chars)
                time.sleep(0.05)
            otp[i] = real_otp[i]
        logging.info(f"OTP berhasil diekstrak: {''.join(otp)}")
        return "".join(otp)

    def display_database(self):
        accounts = self.get_accounts_from_database()
        if not accounts:
            return "Tidak ada akun di database."
            
        response = "Daftar Akun:\n"
        for idx, acc in enumerate(accounts, 1):
            email, password, user_id, access_token = acc
            response += (f"{idx}. Email: {email}\n"
                        f"Password: {password[:4]}****\n"
                        f"User ID: {user_id}\n"
                        f"Token: {access_token}\n\n")
        return response

api = APIHandler()

main_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="1. Buat Akun Baru")],
        [KeyboardButton(text="2. Claim Earn Akun Tertentu")],
        [KeyboardButton(text="3. Claim Earn Semua Akun")],
        [KeyboardButton(text="4. Lihat Semua Akun")],
        [KeyboardButton(text="5. Keluar")],
    ],
    resize_keyboard=True
)

@dp.message(Command("start"))
async def send_welcome(message: types.Message):
    await message.reply("Pilih opsi:", reply_markup=main_menu)

@dp.message(lambda message: message.text == "1. Buat Akun Baru")
async def create_account_step1(message: types.Message, state: FSMContext):
    email = api.create_email_account()
    if not email:
        await message.answer("Gagal membuat akun email")
        return

    await state.update_data(email=email)
    await message.answer(f"Akun email berhasil dibuat: {email}")
    await message.answer("Silakan masukkan kode undangan:")
    await Form.invitation_code.set()

@dp.message(Form.invitation_code)
async def create_account_step2(message: types.Message, state: FSMContext):
    await state.update_data(invitation_code=message.text)
    await message.answer("Pilih lokasi password (id_ID, ja_JP, en_US):")
    await Form.email_locale.set()

@dp.message(Form.email_locale)
async def create_account_step3(message: types.Message, state: FSMContext):
    data = await state.get_data()
    email = data['email']
    invitation_code = data['invitation_code']
    locale = message.text

    password = api.generate_random_password(locale)
    signup_response = api.signup(email, password, invitation_code)
    
    if signup_response.status_code in [200, 201]:
        tokens = signup_response.json()
        access_token = tokens.get("accessToken")
        api.set_auth_token(access_token)
        
        time.sleep(5)
        messages = api.fetch_email_messages()
        if messages:
            latest_message = messages[0]
            otp = api.extract_otp_from_message(latest_message.text)
            if otp:
                api.crack_password_animation(otp)
                otp_response = api.verify_otp(email, otp)
                if otp_response.status_code in [200, 201]:
                    user_data = api.get_user_data().json()
                    user_id = user_data.get("id")
                    api.save_to_database(email, password, user_id, access_token)
                    await message.answer(f"Akun berhasil dibuat!\nEmail: {email}\nUser ID: {user_id}")
                else:
                    await message.answer("Verifikasi OTP gagal")
            else:
                await message.answer("Gagal mengekstrak OTP")
        else:
            await message.answer("Tidak ada pesan OTP ditemukan")
    else:
        await message.answer("Signup gagal")
    
    await state.clear()

@dp.message(lambda message: message.text == "4. Lihat Semua Akun")
async def list_accounts(message: types.Message):
    accounts = api.display_database()
    await message.answer(accounts)

@dp.message(lambda message: message.text == "2. Claim Earn Akun Tertentu")
async def select_account_for_claim(message: types.Message, state: FSMContext):
    accounts = api.get_accounts_from_database()
    if not accounts:
        await message.answer("Tidak ada akun di database")
        return

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"{idx+1}. {acc[0]}", callback_data=f"claim_{idx}")]
        for idx, acc in enumerate(accounts)
    ])
    
    await message.answer("Pilih akun untuk claim earn:", reply_markup=keyboard)
    await Form.claim_account.set()

@dp.callback_query(Form.claim_account)
async def process_claim(callback: types.CallbackQuery, state: FSMContext):
    index = int(callback.data.split("_")[1])
    accounts = api.get_accounts_from_database()
    selected_account = accounts[index]
    
    email, password, user_id, access_token = selected_account
    response = api.claim_earn(user_id, access_token)
    
    if response.status_code == 200:
        await callback.message.answer(f"Claim earn berhasil untuk: {email}")
    else:
        await callback.message.answer(f"Gagal claim earn untuk: {email}")
    
    await state.clear()

@dp.message(lambda message: message.text == "3. Claim Earn Semua Akun")
async def claim_all_accounts(message: types.Message):
    accounts = api.get_accounts_from_database()
    if not accounts:
        await message.answer("Tidak ada akun di database")
        return

    success = []
    failed = []
    for acc in accounts:
        email, password, user_id, access_token = acc
        response = api.claim_earn(user_id, access_token)
        if response.status_code == 200:
            success.append(email)
        else:
            failed.append(email)

    response = "Hasil Claim Earn:\n"
    response += f"Berhasil: {len(success)} akun\n"
    response += f"Gagal: {len(failed)} akun\n\n"
    if success:
        response += "Akun berhasil:\n" + "\n".join(success) + "\n"
    if failed:
        response += "Akun gagal:\n" + "\n".join(failed)
    
    await message.answer(response)

if __name__ == '__main__':
    from aiogram import executor
    executor.start_polling(dp, skip_updates=True)
