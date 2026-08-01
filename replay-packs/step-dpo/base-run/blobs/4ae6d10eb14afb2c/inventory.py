from sqlalchemy import create_engine

from schema import metadata
def ensure_and_list_tables(url):
    engine = create_engine(url)
    metadata.create_all(engine)
    return sorted(engine.table_names())