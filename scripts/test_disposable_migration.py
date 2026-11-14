import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

def run_disposable_drill():
    conn = psycopg2.connect('postgresql://postgres:postgres@localhost:5432/postgres')
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    cur = conn.cursor()

    test_db = 'disposable_migration_test_db'
    cur.execute(f'DROP DATABASE IF EXISTS {test_db};')
    cur.execute(f'CREATE DATABASE {test_db};')
    print(f'Created disposable database: {test_db}')
    cur.close()
    conn.close()

    # Connect to disposable db
    conn_disp = psycopg2.connect(f'postgresql://postgres:postgres@localhost:5432/{test_db}')
    cur_disp = conn_disp.cursor()

    # Read complete_hosted_schema.sql
    with open('database/migrations/complete_hosted_schema.sql', 'r', encoding='utf-8') as f:
        schema_sql = f.read()

    print('Applying complete_hosted_schema.sql...')
    cur_disp.execute(schema_sql)
    conn_disp.commit()

    # Verify tables
    cur_disp.execute("SELECT count(*) FROM information_schema.tables WHERE table_schema = 'public';")
    t_count = cur_disp.fetchone()[0]
    print(f'Total tables created: {t_count}')

    cur_disp.execute("SELECT version_num FROM alembic_version;")
    alembic_v = cur_disp.fetchone()[0]
    print(f'Alembic version recorded: {alembic_v}')

    # Read and apply rls_policies.sql
    with open('database/policies/rls_policies.sql', 'r', encoding='utf-8') as f:
        rls_sql = f.read()

    print('Applying rls_policies.sql...')
    cur_disp.execute(rls_sql)
    conn_disp.commit()

    cur_disp.execute("SELECT count(*) FROM pg_policies WHERE schemaname = 'public';")
    pol_count = cur_disp.fetchone()[0]
    print(f'Total RLS policies created: {pol_count}')

    cur_disp.close()
    conn_disp.close()

    # Clean up
    conn_cleanup = psycopg2.connect('postgresql://postgres:postgres@localhost:5432/postgres')
    conn_cleanup.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    cur_cleanup = conn_cleanup.cursor()
    cur_cleanup.execute(f'DROP DATABASE {test_db};')
    print(f'Cleaned up disposable database: {test_db}')
    cur_cleanup.close()
    conn_cleanup.close()
    print('DISPOSABLE DATABASE VALIDATION: 100% SUCCESS')

if __name__ == '__main__':
    run_disposable_drill()
