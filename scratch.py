import sqlite3
import pprint

conn = sqlite3.connect('db.sqlite3')
c = conn.cursor()
c.execute("SELECT id, text FROM game_question LIMIT 5")
print(c.fetchall())
