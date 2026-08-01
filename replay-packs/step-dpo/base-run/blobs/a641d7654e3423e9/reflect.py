from sqlalchemy import MetaData, Table, create_engine
from schema import metadata


def reflect_user_columns(url):
    engine = create_engine(url)
    metadata.create_all(engine)
    reflected = MetaData()
    table = Table('users', reflected, autoload_with=engine)
    return sorted(c.name for c in table.columns)
