from sqlalchemy import Column, Integer, MetaData, String, Table

metadata = MetaData()

users = Table(
    'users', metadata,
    Column('id', Integer, primary_key=True),
    Column('name', String(50)),
)
