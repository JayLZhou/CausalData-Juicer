from sqlalchemy import create_engine


def init(url):
    engine = create_engine(url)
    engine.execute('CREATE TABLE IF NOT EXISTS logs (msg TEXT)')
    return engine


def add(engine, msg):
    engine.execute("INSERT INTO logs (msg) VALUES ('" + msg + "')")


def count(engine):
    return engine.execute('SELECT COUNT(*) FROM logs').scalar()
