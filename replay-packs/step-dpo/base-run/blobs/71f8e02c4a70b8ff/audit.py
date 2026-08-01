from sqlalchemy import create_engine, insert, select

from schema import metadata, users


def record_user(url, name):
    engine = create_engine(url)
    metadata.create_all(engine)
    with engine.connect() as conn:
        conn.execute(insert(users).values(name=name))


def count_users(url):
    engine = create_engine(url)
    with engine.connect() as conn:
        return len(conn.execute(select(users.c.id)).fetchall())
