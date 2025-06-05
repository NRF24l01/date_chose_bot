import sqlite3
from datetime import date

DB_PATH = "votes.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT
    )
    """)
    c.execute("""
    CREATE TABLE IF NOT EXISTS votes (
        user_id INTEGER,
        vote_date TEXT,
        PRIMARY KEY (user_id, vote_date)
    )
    """)
    conn.commit()
    conn.close()

def add_user(user_id, username):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)", (user_id, username))
    conn.commit()
    conn.close()

def get_user_votes(user_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT vote_date FROM votes WHERE user_id = ?", (user_id,))
    dates = [row[0] for row in c.fetchall()]
    conn.close()
    return dates

def set_user_votes(user_id, dates):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM votes WHERE user_id = ?", (user_id,))
    c.executemany("INSERT INTO votes (user_id, vote_date) VALUES (?, ?)", [(user_id, d) for d in dates])
    conn.commit()
    conn.close()

def get_all_votes():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
    SELECT u.user_id, u.username, v.vote_date
    FROM users u
    LEFT JOIN votes v ON u.user_id = v.user_id
    ORDER BY u.user_id, v.vote_date
    """)
    data = c.fetchall()
    conn.close()
    return data

def get_votes_by_date():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
    SELECT vote_date, COUNT(user_id) as cnt
    FROM votes
    GROUP BY vote_date
    ORDER BY vote_date
    """)
    data = c.fetchall()
    conn.close()
    return data

def get_voted_users():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
    SELECT DISTINCT user_id FROM votes
    """)
    users = [row[0] for row in c.fetchall()]
    conn.close()
    return users