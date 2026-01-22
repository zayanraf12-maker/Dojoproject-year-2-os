# Create a database

import sqlite3

db_locale = 'users.db'


connection = sqlite3.connect(db_locale)

c = connection.cursor()


# Create users table if it doesn't exist

c.execute("""

CREATE TABLE IF NOT EXISTS users (

id INTEGER PRIMARY KEY AUTOINCREMENT,

username TEXT UNIQUE NOT NULL,

password TEXT NOT NULL

)

""")


connection.commit()

