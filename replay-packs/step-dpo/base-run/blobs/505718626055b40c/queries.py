from sqlalchemy import create_engine, insert, select
from schema import metadata, users


def seed(url, names):
    engine = create_engine(url)
    metadata.create_all(engine)
    with engine.begin() as conn:
        for name in names:
            conn.execute(insert(users).values(name=name))


def fetch_names(url):
    engine = create_engine(url)
    with engine.connect() as conn:
        rows = conn.execute(select(users.c.name).order_by(users.c.id))
        return [row.name for row in rows]