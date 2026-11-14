import psycopg2

conn = psycopg2.connect('postgresql://postgres:postgres@localhost:5432/flatmate_staging_disposable')
cur = conn.cursor()
cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' ORDER BY table_name;")
tables = [r[0] for r in cur.fetchall()]
print(f"Total DB tables: {len(tables)}")
print(tables)

cur.execute("SELECT version_num FROM alembic_version;")
print(f"Alembic version: {cur.fetchall()}")
