import random
import re
from datetime import datetime

from werkzeug.security import generate_password_hash

from database.db import get_db

first_names = [
    'Rahul','Amit','Neha','Priya','Vikram','Sana','Rohan','Meera','Arjun','Kavya',
    'Nikhil','Tanya','Kunal','Ananya','Manoj','Swati','Aditya','Ishita','Siddharth','Riya'
]

last_names = [
    'Sharma','Verma','Gupta','Singh','Khan','Patel','Joshi','Reddy','Iyer','Nair',
    'Das','Chatterjee','Banerjee','Kulkarni','Wadhwa','Kapoor','Mehta','Bose','Roy','Nayak'
]

def make_email(name: str) -> str:
    base = re.sub(r'[^a-z0-9]+', '', name.lower())
    return f"{base}{random.randint(10, 999)}@gmail.com"


def seed_one_user():
    conn = get_db()
    try:
        while True:
            name = f"{random.choice(first_names)} {random.choice(last_names)}"
            email = make_email(name)

            if conn.execute(
                'SELECT 1 FROM users WHERE email = ?',
                (email,),
            ).fetchone() is None:
                break

        password_hash = generate_password_hash('password123')
        conn.execute(
            'INSERT INTO users (name, email, password_hash, created_at) VALUES (?, ?, ?, ?)',
            (name, email, password_hash, datetime.now().isoformat()),
        )
        conn.commit()

        user_id = conn.execute('SELECT id FROM users WHERE email = ?', (email,)).fetchone()['id']
        print(f"id={user_id}")
        print(f"name={name}")
        print(f"email={email}")
    finally:
        conn.close()


if __name__ == '__main__':
    seed_one_user()

