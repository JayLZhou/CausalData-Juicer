"""sqlalchemy 1.4 -> 2.0 migration family (6 tasks).

All tasks use file-backed sqlite inside pytest tmp_path (hermetic).
Breaks used:
  s01  select([...]) legacy list style removed
  s02  Engine.table_names() removed
  s03  Engine.execute(raw string) removed (-> connect + text + commit)
  s04  MetaData(bind=) and Table(autoload=True) removed
  s05  Session.execute(raw string) removed (-> text())
       (Query.get was tried first but 2.0 keeps it as a legacy warning)
  s06  library-level DML autocommit removed (T3: rows silently lost)
"""
from __future__ import annotations

from causal_data_juicer.workloads.depmig.base import DepMigTask, Family

FAMILY = Family(
    name="sqlalchemy",
    old_pins=["sqlalchemy==1.4.54"],
    new_pins=["sqlalchemy==2.0.35"],
)

_SCHEMA = (
    "from sqlalchemy import Column, Integer, MetaData, String, Table\n"
    "\n"
    "metadata = MetaData()\n"
    "\n"
    "users = Table(\n"
    "    'users', metadata,\n"
    "    Column('id', Integer, primary_key=True),\n"
    "    Column('name', String(50)),\n"
    ")\n"
)


def build_tasks() -> list[DepMigTask]:
    tasks: list[DepMigTask] = []

    tasks.append(DepMigTask(
        id="s01_select_list", family=FAMILY, tier=1,
        description="Core queries written in the legacy select([...]) list style.",
        migration_points=["select([cols]) -> select(cols)"],
        files={
            "schema.py": _SCHEMA,
            "queries.py": (
                "from sqlalchemy import create_engine, insert, select\n"
                "\n"
                "from schema import metadata, users\n"
                "\n"
                "\n"
                "def seed(url, names):\n"
                "    engine = create_engine(url)\n"
                "    metadata.create_all(engine)\n"
                "    with engine.begin() as conn:\n"
                "        for name in names:\n"
                "            conn.execute(insert(users).values(name=name))\n"
                "\n"
                "\n"
                "def fetch_names(url):\n"
                "    engine = create_engine(url)\n"
                "    with engine.connect() as conn:\n"
                "        rows = conn.execute(select([users.c.name]).order_by(users.c.id))\n"
                "        return [row[0] for row in rows]\n"
            ),
            "test_queries.py": (
                "from queries import fetch_names, seed\n"
                "\n"
                "\n"
                "def test_roundtrip(tmp_path):\n"
                "    url = f'sqlite:///{tmp_path}/app.db'\n"
                "    seed(url, ['ada', 'grace'])\n"
                "    assert fetch_names(url) == ['ada', 'grace']\n"
            ),
        },
    ))

    tasks.append(DepMigTask(
        id="s02_table_names", family=FAMILY, tier=1,
        description="A migration checker using Engine.table_names().",
        migration_points=["Engine.table_names() -> inspect(engine).get_table_names()"],
        files={
            "schema.py": _SCHEMA,
            "inventory.py": (
                "from sqlalchemy import create_engine\n"
                "\n"
                "from schema import metadata\n"
                "\n"
                "\n"
                "def ensure_and_list_tables(url):\n"
                "    engine = create_engine(url)\n"
                "    metadata.create_all(engine)\n"
                "    return sorted(engine.table_names())\n"
            ),
            "test_inventory.py": (
                "from inventory import ensure_and_list_tables\n"
                "\n"
                "\n"
                "def test_tables(tmp_path):\n"
                "    url = f'sqlite:///{tmp_path}/app.db'\n"
                "    assert ensure_and_list_tables(url) == ['users']\n"
            ),
        },
    ))

    tasks.append(DepMigTask(
        id="s03_engine_execute", family=FAMILY, tier=2,
        description="A log store calling Engine.execute with raw SQL strings.",
        migration_points=[
            "Engine.execute removed (-> engine.connect()/begin())",
            "raw SQL strings need text()",
        ],
        files={
            "logstore.py": (
                "from sqlalchemy import create_engine\n"
                "\n"
                "\n"
                "def init(url):\n"
                "    engine = create_engine(url)\n"
                "    engine.execute('CREATE TABLE IF NOT EXISTS logs (msg TEXT)')\n"
                "    return engine\n"
                "\n"
                "\n"
                "def add(engine, msg):\n"
                "    engine.execute(\"INSERT INTO logs (msg) VALUES ('\" + msg + \"')\")\n"
                "\n"
                "\n"
                "def count(engine):\n"
                "    return engine.execute('SELECT COUNT(*) FROM logs').scalar()\n"
            ),
            "test_logstore.py": (
                "from logstore import add, count, init\n"
                "\n"
                "\n"
                "def test_log_roundtrip(tmp_path):\n"
                "    engine = init(f'sqlite:///{tmp_path}/logs.db')\n"
                "    add(engine, 'boot')\n"
                "    add(engine, 'ready')\n"
                "    assert count(engine) == 2\n"
            ),
        },
    ))

    tasks.append(DepMigTask(
        id="s04_bind_autoload", family=FAMILY, tier=2,
        description="Schema reflection using MetaData(bind=) and Table(autoload=True).",
        migration_points=[
            "MetaData(bind=engine) removed",
            "Table(autoload=True) -> autoload_with=engine",
        ],
        files={
            "schema.py": _SCHEMA,
            "reflect.py": (
                "from sqlalchemy import MetaData, Table, create_engine\n"
                "\n"
                "from schema import metadata\n"
                "\n"
                "\n"
                "def reflect_user_columns(url):\n"
                "    engine = create_engine(url)\n"
                "    metadata.create_all(engine)\n"
                "    reflected = MetaData(bind=engine)\n"
                "    table = Table('users', reflected, autoload=True)\n"
                "    return sorted(c.name for c in table.columns)\n"
            ),
            "test_reflect.py": (
                "from reflect import reflect_user_columns\n"
                "\n"
                "\n"
                "def test_reflection(tmp_path):\n"
                "    url = f'sqlite:///{tmp_path}/app.db'\n"
                "    assert reflect_user_columns(url) == ['id', 'name']\n"
            ),
        },
    ))

    tasks.append(DepMigTask(
        id="s05_session_raw_sql", family=FAMILY, tier=2,
        description="An ORM-session repository issuing raw SQL strings via session.execute.",
        migration_points=["Session.execute(raw string) removed — wrap in text() (two sites)"],
        files={
            "repo.py": (
                "from sqlalchemy import Column, Integer, String, create_engine\n"
                "from sqlalchemy.orm import declarative_base, sessionmaker\n"
                "\n"
                "Base = declarative_base()\n"
                "\n"
                "\n"
                "class Item(Base):\n"
                "    __tablename__ = 'items'\n"
                "    id = Column(Integer, primary_key=True)\n"
                "    label = Column(String(50))\n"
                "\n"
                "\n"
                "def make_session(url):\n"
                "    engine = create_engine(url)\n"
                "    Base.metadata.create_all(engine)\n"
                "    return sessionmaker(bind=engine)()\n"
                "\n"
                "\n"
                "def add_item(session, label):\n"
                "    session.execute(\"INSERT INTO items (label) VALUES ('\" + label + \"')\")\n"
                "    session.commit()\n"
                "\n"
                "\n"
                "def count_items(session):\n"
                "    return session.execute('SELECT COUNT(*) FROM items').scalar()\n"
            ),
            "test_repo.py": (
                "from repo import add_item, count_items, make_session\n"
                "\n"
                "\n"
                "def test_raw_sql_roundtrip(tmp_path):\n"
                "    session = make_session(f'sqlite:///{tmp_path}/app.db')\n"
                "    add_item(session, 'widget')\n"
                "    add_item(session, 'gadget')\n"
                "    assert count_items(session) == 2\n"
            ),
        },
    ))

    tasks.append(DepMigTask(
        id="s06_autocommit", family=FAMILY, tier=3,
        description="An audit writer that relied on 1.x library-level autocommit for DML.",
        migration_points=[
            "connection-level DML autocommit removed in 2.0 — inserts are silently rolled back without commit (silent behavioural change)",
        ],
        files={
            "schema.py": _SCHEMA,
            "audit.py": (
                "from sqlalchemy import create_engine, insert, select\n"
                "\n"
                "from schema import metadata, users\n"
                "\n"
                "\n"
                "def record_user(url, name):\n"
                "    engine = create_engine(url)\n"
                "    metadata.create_all(engine)\n"
                "    with engine.connect() as conn:\n"
                "        conn.execute(insert(users).values(name=name))\n"
                "\n"
                "\n"
                "def count_users(url):\n"
                "    engine = create_engine(url)\n"
                "    with engine.connect() as conn:\n"
                "        return len(conn.execute(select(users.c.id)).fetchall())\n"
            ),
            "test_audit.py": (
                "from audit import count_users, record_user\n"
                "\n"
                "\n"
                "def test_records_persist(tmp_path):\n"
                "    url = f'sqlite:///{tmp_path}/audit.db'\n"
                "    record_user(url, 'ada')\n"
                "    record_user(url, 'grace')\n"
                "    assert count_users(url) == 2\n"
            ),
        },
    ))

    return tasks
