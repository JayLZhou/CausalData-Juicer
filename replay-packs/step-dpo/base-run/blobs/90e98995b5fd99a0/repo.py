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
    new_item = Item(label=label)
    session.add(new_item)
    session.commit()


def count_items(session):
    return session.query(Item).count()