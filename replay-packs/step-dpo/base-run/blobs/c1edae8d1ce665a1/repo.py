from sqlalchemy import Column, Integer, String, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

Base = declarative_base()


class Item(Base):
    __tablename__ = 'items'
    id = Column(Integer, primary_key=True)
    label = Column(String(50))


def make_session(url):
    engine = create_engine(url)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def add_item(session, label):
    session.execute("INSERT INTO items (label) VALUES ('" + label + "')")
    session.commit()


def count_items(session):
    return session.execute('SELECT COUNT(*) FROM items').scalar()
