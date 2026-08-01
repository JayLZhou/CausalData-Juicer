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
        result = conn.execute(select(users.c.id))
        return len(result.fetchall())


if __name__ == '__main__':
    # Example usage
    from sqlalchemy import create_engine
    engine = create_engine('sqlite:///:memory:')
    metadata.create_all(engine)
    record_user(engine.url, 'John Doe')
    print(count_users(engine.url))
