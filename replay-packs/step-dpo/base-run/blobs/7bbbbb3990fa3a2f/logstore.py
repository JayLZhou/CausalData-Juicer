from sqlalchemy import create_engine, text


def init(url):
    engine = create_engine(url)
    with engine.connect() as connection:
        connection.execute(text('CREATE TABLE IF NOT EXISTS logs (msg TEXT)'))
    return engine


def add(engine, msg):
    with engine.connect() as connection:
        connection.execute(text("INSERT INTO logs (msg) VALUES (:msg)").bindparams(msg=msg))


def count(engine):
    with engine.connect() as connection:
        return connection.execute(text('SELECT COUNT(*) FROM logs')).scalar()
