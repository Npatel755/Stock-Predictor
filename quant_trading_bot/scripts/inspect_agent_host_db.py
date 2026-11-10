import sqlite3
import json

db_path = r"C:\Users\Nick\AppData\Roaming\Code\User\globalStorage\agent-host.db"
con = sqlite3.connect(db_path)
cur = con.cursor()
tables = cur.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
print("Tables:", tables)
for t in tables:
    name = t[0]
    count = cur.execute(f"SELECT count(*) FROM [{name}]").fetchone()[0]
    print(f"Table {name}: {count} rows")
    if count > 0:
        cols = [d[0] for d in cur.execute(f"SELECT * FROM [{name}] LIMIT 1").description]
        print(f"  Columns: {cols}")
        rows = cur.execute(f"SELECT * FROM [{name}] LIMIT 3").fetchall()
        for r in rows:
            print(f"  Row: {r[:3]}")
