#!/usr/bin/python3
import requests
from fake_useragent import UserAgent
from rich.table import Table
from rich import box
from rich.panel import Panel 
from rich.console import Console 
from pymailtm import MailTm, Account
from rich.status import Status 
import os
import re
import time
import sqlite3
import itertools 
import random
from faker import Faker  # Import Faker
from InquirerPy import inquirer
from InquirerPy.separator import Separator
from prompt_toolkit.shortcuts import prompt
from prompt_toolkit import PromptSession
from prompt_toolkit.completion import FuzzyWordCompleter, WordCompleter 
from rich.align import Align

console = Console()

class APIHandler:
    def __init__(self):
        self.ua = UserAgent()
        self.mailtm = MailTm()
        self.current_account = None  # Store the created email account
        self.faker = Faker()  # Initialize Faker
        self.headers = {
            "User-Agent": self.ua.random,
            "Content-Type": "application/json",
        }
        self.base_urls = {
            "signup": "https://node.securitylabs.xyz/api/v1/auth/signup-user",
            "verify_otp": "https://node.securitylabs.xyz/api/v1/auth/verify-otp-user",
            "user_data": "https://node.securitylabs.xyz/api/v1/users",
            "earn": "https://node.securitylabs.xyz/api/v1/users/earn/",  # Endpoint earn
        }
        self.db_path = "database.db"  # Path to SQLite database
        self.init_database()

    def init_database(self):
        """Initialize the SQLite database and create a table if it doesn't exist."""
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
        """Save account details to the SQLite database."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO accounts (email, password, user_id, access_token)
            VALUES (?, ?, ?, ?)
        """, (email, password, user_id, access_token))
        conn.commit()
        conn.close() 

    def get_accounts_from_database(self):
        """Retrieve all accounts from the SQLite database."""
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
            url += str(path)  # Append ID or additional path to the base URL
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
        """Claim earn using user ID and access token."""
        self.set_auth_token(access_token)
        response = self.get("earn", path=user_id)
        if response.status_code == 200:
            earn_data = response.json()
            console.log(f"(DEBUG) [green bold]claim earn berhasil untuk user ID {user_id}: {earn_data}")
        else:
            console.log(f"(DEBUG) [red bold]gagal claim earn untuk user ID {user_id}: {response.json()}")

    def create_email_account(self):
        """Create a new temporary email account using pymailtm."""
        try:
            # Get a new temporary email account
            account = self.mailtm.get_account()
            self.current_account = account
            console.log(f"Akun email berhasil dibuat: {account.address}")
            return account.address
        except Exception as e:
            print(f"Gagal membuat akun email: {e}")
            return None

    def fetch_email_messages(self):
        """Fetch messages from the current email account."""
        if not self.current_account:
            raise Exception("Akun email belum dibuat!")
        try:
            messages = self.current_account.get_messages()
            return messages
        except Exception as e:
            print(f"Gagal mengambil pesan: {e}")
            return []

    def extract_otp_from_message(self, message_text):
        """Extract OTP code from the email message text."""
        match = re.search(r'code is:\n\n(\d{6})\n\n', message_text)
        if match:
            otp = match.group(1)
            return otp
        else:
            console.log("OTP tidak ditemukan dalam pesan.")
            return None

    def generate_random_password(self, locale="en_US"):
        """
        Generate a random password using Faker.
        You can specify the locale (e.g., 'en_US', 'id_ID', 'ja_JP').
        """
        self.faker = Faker(locale)  # Set the locale for Faker
        # Combine random words and numbers to create a strong password
        password = (
            self.faker.name().replace(" ", "").capitalize()  # Random name (no spaces, capitalized)
            + str(self.faker.random_int(min=1000, max=9999))  # Random number
        )
        console.log(f"(DEBUG) password acak tergenerate: {password}")
        return password

    def crack_password_animation(self, real_otp):
        """
        Simulate a password/OTP cracking animation with the real OTP.
        """
        console.log("(DEBUG) Memulai proses ekstraksi OTP...",highlight=True)
        chars = "0123456789"
        otp_length = len(real_otp)
        otp = list("*" * otp_length)  # Placeholder untuk OTP

        for i in range(otp_length):
            for _ in range(20):  # Simulasi perubahan karakter
                otp[i] = random.choice(chars)
                print("\rEkstraking: " + "".join(otp), end="")
                time.sleep(0.05)
            # Set karakter final untuk posisi ini berdasarkan OTP asli
            otp[i] = real_otp[i]

        console.log("\r(DEBUG) OTP berhasil diekstrak: " + "".join(otp),highlight=True)
        return "".join(otp)  # Return the cracked OTP (same as real OTP)

    def display_database(self):
        """Display all accounts in the database using rich.table."""
        console = Console()
        table = Table(show_header=True, header_style="bold magenta",border_style="#888888",expand=True,box=box.ROUNDED)
        table.add_column("No.", style="dim",highlight=True)
        table.add_column("Email", justify="left",highlight=True,style="green bold")
        table.add_column("Password", justify="left",highlight=True)
        table.add_column("User ID", justify="left",highlight=True)
        table.add_column("Access Token", justify="left",highlight=True,style="cyan bold")

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT email, password, user_id, access_token FROM accounts")
        accounts = cursor.fetchall()
        conn.close()

        if not accounts:
            print("Tidak ada akun di database.")
            return

        for idx, account in enumerate(accounts, start=1):
            email, password, user_id, access_token = account
            table.add_row(
                str(idx),
                email.replace("e-record.com","gmail.com"),
                password[:4] + "************" if len(password) > 4 else password,
                user_id[:4] + "**[red]Encryption[reset]**" if len(user_id) > 4 else user_id,
                access_token, 
            )
        console.print(table)


def main():
    api = APIHandler()

    while True:
        # Step 1: Show the main menu with a select prompt
        selected_option = inquirer.select(
            message="Pilih opsi:",
            choices=[
                "1. Buat akun baru",
                "2. Claim earn untuk akun tertentu (dengan fuzzy search)",
                "3. Claim earn untuk semua akun di database",
                "4. Lihat semua akun di database",
                "5. Build FunctorNetwork (grammar kontol)",
                Separator(),  # Add a separator for better readability
                "5. Keluar",
            ],
            border=True,
            max_height="70%",
        ).execute()

        if selected_option == "1. Buat akun baru":
            # Create a new account
            email = api.create_email_account()
            if not email:
                console.log("Gagal membuat akun email. Program berhenti.")
                continue

            session = PromptSession()

            locale = session.prompt("(DEBUG) set locale password: ",completer=FuzzyWordCompleter(
                ["id_ID","ja_JP","en_US"],meta_dict={
                    "id_ID": "password orang indonesia",
                    "ja_JP": "password orang jepang",
                    "en_US": "password orang amerika"
                    }
                ))
            password = api.generate_random_password(locale)

            invitation_code = prompt("(DEBUG) set invitation code: ",is_password=True,completer=FuzzyWordCompleter(["clzulokpi1dmump1a361fanb0"]))

            signup_response = api.signup(email, password, invitation_code)
            if signup_response.status_code in [200, 201]:
                console.log("(DEBUG) Signup berhasil! {}".format(signup_response.json()))
                tokens = signup_response.json()
                access_token = tokens.get("accessToken")
                api.set_auth_token(access_token)
            else:
                console.log("(DEBUG) Signup gagal.", signup_response.json())
                continue
            time.sleep(5)

            messages = api.fetch_email_messages()
            if not messages:
                console.log("Tidak ada pesan ditemukan di kotak masuk.")
                continue

            latest_message = messages[0]
            otp_ = api.extract_otp_from_message(latest_message.text)
            if not otp_:
                console.log("Gagal mengekstrak OTP.")
                continue

            otp = api.crack_password_animation(otp_)

            otp_response = api.verify_otp(email, otp)
            if otp_response.status_code in [200, 201]:
                console.log("(DEBUG) Verifikasi OTP berhasil!")
            else:
                console.log("(DEBUG) Verifikasi OTP gagal.", otp_response.json())
                continue

            user_data_response = api.get_user_data()
            if user_data_response.status_code == 200:
                user_data = user_data_response.json()
                user_id = user_data.get("id")
                console.log(f"(DEBUG) ID Pengguna Anda: {user_id}")
                console.log("(DEBUG) Data pengguna berhasil diambil:", user_data)
            else:
                console.log("(DEBUG) Gagal mengambil data pengguna.", user_data_response.json())
                continue

            api.save_to_database(email, password, user_id, access_token)

        elif selected_option == "2. Claim earn untuk akun tertentu (dengan fuzzy search)":
            # Claim earn for a specific account using fuzzy search
            accounts = api.get_accounts_from_database()
            if not accounts:
                print("Tidak ada akun di database.")
                continue

            choices = [
                f"{account[0]} (ID: {account[2]})" for account in accounts
            ]

            selected_account = inquirer.fuzzy(
                message="Pilih akun untuk claim earn:",
                choices=choices,
                max_height="70%",
                border=True,
            ).execute()

            if not selected_account:
                print("Tidak ada akun yang dipilih.")
                continue

            selected_email = selected_account.split(" ")[0]
            account_data = next(
                (acc for acc in accounts if acc[0] == selected_email), None
            )
            if not account_data:
                print("Akun tidak ditemukan di database.")
                continue

            email, password, user_id, access_token = account_data
            console.log(f"(DEBUG) mencoba claim earn untuk akun: [cyan underline]{email}[reset]",highlight=True)
            api.claim_earn(user_id, access_token)

        elif selected_option == "3. Claim earn untuk semua akun di database":
            # Claim earn for all accounts in the database
            accounts = api.get_accounts_from_database()
            if not accounts:
                print("Tidak ada akun di database.")
                continue

            for account in accounts:
                email, password, user_id, access_token = account
                console.log(f"(DEBUG) mencoba claim earn untuk akun: [cyan green]{email}[reset]")
                api.claim_earn(user_id, access_token)

        elif selected_option == "4. Lihat semua akun di database":
            # Display all accounts in the database
            api.display_database()

        elif selected_option == "5. Keluar":
            print("Keluar dari program.")
            return

main()
