"""Connection check: reads .env and lists the disease modules through the app's limited account."""
import os
import pymysql
from dotenv import load_dotenv

# Name the .env file explicitly: it sits in the project root, one folder above this script.
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".env"))

conn = pymysql.connect(
    host=os.environ["DB_HOST"],
    port=int(os.environ["DB_PORT"]),
    user=os.environ["DB_USER"],
    password=os.environ["DB_PASSWORD"],
    database=os.environ["DB_NAME"],
    cursorclass=pymysql.cursors.DictCursor,
)
with conn.cursor() as cur:
    cur.execute("SELECT module_code, feature_count FROM disease_modules ORDER BY module_id")
    for row in cur.fetchall():
        print(row)
conn.close()
print("Python can talk to MySQL.")
