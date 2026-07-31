"""pydantic 1.10 -> 2.x migration family (6 tasks).

Every task passes verbatim under pydantic==1.10.13 and fails under
pydantic 2 for a *real* documented breaking change (no shimmed
deprecations — v2 keeps `.dict()`, `@validator` etc. working, so those
are useless as bench material):

  p01  BaseSettings moved out to pydantic-settings      (ImportError)
  p02  str fields no longer coerce ints                 (ValidationError)
       (GenericModel was tried first but 2.7 shims it with a warning)
  p03  @root_validator without skip_on_failure errors    (class-def error)
  p04  constr(regex=) and Field(min_items=) removed      (usage errors)
  p05  Optional fields no longer default to None         (ValidationError)
  p06  .json() separator change breaks exact output      (silent, T3)
"""
from __future__ import annotations

from causeforge.workloads.depmig.base import DepMigTask, Family

FAMILY = Family(
    name="pydantic",
    old_pins=["pydantic==1.10.13"],
    new_pins=["pydantic==2.7.4"],
)


def build_tasks() -> list[DepMigTask]:
    tasks: list[DepMigTask] = []

    tasks.append(DepMigTask(
        id="p01_settings", family=FAMILY, tier=1,
        description="A service config module built on pydantic BaseSettings.",
        migration_points=["BaseSettings import (moved to pydantic-settings; migrate to BaseModel)"],
        files={
            "config.py": (
                "from pydantic import BaseSettings\n"
                "\n"
                "\n"
                "class AppConfig(BaseSettings):\n"
                "    app_name: str = 'svc'\n"
                "    max_retries: int = 3\n"
                "    debug: bool = False\n"
                "\n"
                "\n"
                "def load_config(**overrides):\n"
                "    return AppConfig(**overrides)\n"
            ),
            "test_config.py": (
                "from config import load_config\n"
                "\n"
                "\n"
                "def test_defaults():\n"
                "    cfg = load_config()\n"
                "    assert cfg.app_name == 'svc'\n"
                "    assert cfg.max_retries == 3\n"
                "    assert cfg.debug is False\n"
                "\n"
                "\n"
                "def test_overrides():\n"
                "    cfg = load_config(debug=True, max_retries=5)\n"
                "    assert cfg.debug is True\n"
                "    assert cfg.max_retries == 5\n"
            ),
        },
    ))

    tasks.append(DepMigTask(
        id="p02_str_coercion", family=FAMILY, tier=1,
        description="A ticket registry that relied on pydantic v1 coercing int ids to str.",
        migration_points=["str fields no longer accept ints in v2 (convert at the call site)"],
        files={
            "tickets.py": (
                "from pydantic import BaseModel\n"
                "\n"
                "\n"
                "class Ticket(BaseModel):\n"
                "    ticket_id: str\n"
                "    title: str\n"
                "\n"
                "\n"
                "def open_ticket(seq_no, title):\n"
                "    # seq_no arrives as an int from the sequence generator\n"
                "    return Ticket(ticket_id=seq_no, title=title)\n"
            ),
            "test_tickets.py": (
                "from tickets import open_ticket\n"
                "\n"
                "\n"
                "def test_ticket_id_is_string():\n"
                "    ticket = open_ticket(42, 'boom')\n"
                "    assert ticket.ticket_id == '42'\n"
                "    assert ticket.title == 'boom'\n"
                "\n"
                "\n"
                "def test_sequence_of_tickets():\n"
                "    ids = [open_ticket(n, 't').ticket_id for n in (1, 2, 3)]\n"
                "    assert ids == ['1', '2', '3']\n"
            ),
        },
    ))

    tasks.append(DepMigTask(
        id="p03_validators", family=FAMILY, tier=2,
        description="An order model using field and root validators.",
        migration_points=[
            "@root_validator requires skip_on_failure in v2 (migrate to model_validator)",
            "@validator deprecated (migrate to field_validator)",
        ],
        files={
            "orders.py": (
                "from pydantic import BaseModel, root_validator, validator\n"
                "\n"
                "\n"
                "class Order(BaseModel):\n"
                "    price: float\n"
                "    qty: int\n"
                "    total: float = 0.0\n"
                "\n"
                "    @validator('qty')\n"
                "    def qty_positive(cls, v):\n"
                "        if v <= 0:\n"
                "            raise ValueError('qty must be positive')\n"
                "        return v\n"
                "\n"
                "    @root_validator\n"
                "    def compute_total(cls, values):\n"
                "        values['total'] = values.get('price', 0.0) * values.get('qty', 0)\n"
                "        return values\n"
            ),
            "test_orders.py": (
                "import pytest\n"
                "from pydantic import ValidationError\n"
                "\n"
                "from orders import Order\n"
                "\n"
                "\n"
                "def test_total_computed():\n"
                "    order = Order(price=2.5, qty=4)\n"
                "    assert order.total == 10.0\n"
                "\n"
                "\n"
                "def test_qty_must_be_positive():\n"
                "    with pytest.raises(ValidationError):\n"
                "        Order(price=1.0, qty=0)\n"
            ),
        },
    ))

    tasks.append(DepMigTask(
        id="p04_constraints", family=FAMILY, tier=2,
        description="A user model with constrained string and list fields.",
        migration_points=[
            "constr(regex=) removed (pattern= in v2)",
            "Field(min_items=/max_items=) removed (min_length=/max_length=)",
        ],
        files={
            "users.py": (
                "from typing import List\n"
                "\n"
                "from pydantic import BaseModel, Field, constr\n"
                "\n"
                "\n"
                "class User(BaseModel):\n"
                "    username: constr(regex=r'^[a-z][a-z0-9_]{2,15}$')\n"
                "    tags: List[str] = Field(min_items=1, max_items=5)\n"
                "\n"
                "\n"
                "def new_user(username, tags):\n"
                "    return User(username=username, tags=list(tags))\n"
            ),
            "test_users.py": (
                "import pytest\n"
                "from pydantic import ValidationError\n"
                "\n"
                "from users import new_user\n"
                "\n"
                "\n"
                "def test_valid_user():\n"
                "    user = new_user('alice_01', ['admin'])\n"
                "    assert user.username == 'alice_01'\n"
                "    assert user.tags == ['admin']\n"
                "\n"
                "\n"
                "def test_bad_username():\n"
                "    with pytest.raises(ValidationError):\n"
                "        new_user('9bad', ['x'])\n"
                "\n"
                "\n"
                "def test_too_many_tags():\n"
                "    with pytest.raises(ValidationError):\n"
                "        new_user('alice_01', ['a', 'b', 'c', 'd', 'e', 'f'])\n"
                "\n"
                "\n"
                "def test_empty_tags():\n"
                "    with pytest.raises(ValidationError):\n"
                "        new_user('alice_01', [])\n"
            ),
        },
    ))

    tasks.append(DepMigTask(
        id="p05_optionals", family=FAMILY, tier=2,
        description="Profile/event models plus an api layer, written when Optional implied a None default.",
        migration_points=[
            "Optional[T] fields need explicit defaults in v2 (two files affected)",
        ],
        files={
            "models.py": (
                "from typing import Optional\n"
                "\n"
                "from pydantic import BaseModel\n"
                "\n"
                "\n"
                "class Profile(BaseModel):\n"
                "    handle: str\n"
                "    nickname: Optional[str]\n"
                "    bio: Optional[str]\n"
                "\n"
                "\n"
                "class Event(BaseModel):\n"
                "    name: str\n"
                "    location: Optional[str]\n"
            ),
            "api.py": (
                "from models import Event, Profile\n"
                "\n"
                "\n"
                "def create_profile(handle, nickname=None):\n"
                "    if nickname is None:\n"
                "        return Profile(handle=handle)\n"
                "    return Profile(handle=handle, nickname=nickname)\n"
                "\n"
                "\n"
                "def schedule_event(name):\n"
                "    return Event(name=name)\n"
            ),
            "test_api.py": (
                "from api import create_profile, schedule_event\n"
                "\n"
                "\n"
                "def test_profile_defaults():\n"
                "    profile = create_profile('ada')\n"
                "    assert profile.handle == 'ada'\n"
                "    assert profile.nickname is None\n"
                "    assert profile.bio is None\n"
                "\n"
                "\n"
                "def test_profile_with_nickname():\n"
                "    assert create_profile('ada', 'countess').nickname == 'countess'\n"
                "\n"
                "\n"
                "def test_event_without_location():\n"
                "    assert schedule_event('sprint').location is None\n"
            ),
        },
    ))

    tasks.append(DepMigTask(
        id="p06_json_format", family=FAMILY, tier=3,
        description="A metrics reporter that renders models as JSON lines with exact formatting.",
        migration_points=[
            "v2 .json()/model_dump_json() drops separators' spaces — output must keep v1 formatting (silent behavioural change)",
        ],
        files={
            "report.py": (
                "from pydantic import BaseModel\n"
                "\n"
                "\n"
                "class Metric(BaseModel):\n"
                "    name: str\n"
                "    value: float\n"
                "\n"
                "\n"
                "def render_report(metrics):\n"
                "    return '\\n'.join(m.json() for m in metrics)\n"
            ),
            "test_report.py": (
                "from report import Metric, render_report\n"
                "\n"
                "\n"
                "def test_single_metric_exact_format():\n"
                "    out = render_report([Metric(name='latency', value=1.5)])\n"
                "    assert out == '{\"name\": \"latency\", \"value\": 1.5}'\n"
                "\n"
                "\n"
                "def test_multiline_report():\n"
                "    out = render_report([\n"
                "        Metric(name='a', value=1.0),\n"
                "        Metric(name='b', value=2.0),\n"
                "    ])\n"
                "    assert out.splitlines() == [\n"
                "        '{\"name\": \"a\", \"value\": 1.0}',\n"
                "        '{\"name\": \"b\", \"value\": 2.0}',\n"
                "    ]\n"
            ),
        },
    ))

    tasks.append(DepMigTask(
        id="p07_field_regex", family=FAMILY, tier=1,
        description="A signup form model using Field(regex=).",
        migration_points=["Field(regex=) removed (-> pattern=)"],
        files={
            "form.py": (
                "from pydantic import BaseModel, Field\n"
                "\n"
                "\n"
                "class Signup(BaseModel):\n"
                "    email: str = Field(regex=r'^[^@\\s]+@[^@\\s]+$')\n"
                "\n"
                "\n"
                "def signup(email):\n"
                "    return Signup(email=email)\n"
            ),
            "test_form.py": (
                "import pytest\n"
                "from pydantic import ValidationError\n"
                "\n"
                "from form import signup\n"
                "\n"
                "\n"
                "def test_valid_email():\n"
                "    assert signup('a@b.io').email == 'a@b.io'\n"
                "\n"
                "\n"
                "def test_invalid_email():\n"
                "    with pytest.raises(ValidationError):\n"
                "        signup('not-an-email')\n"
            ),
        },
    ))

    tasks.append(DepMigTask(
        id="p08_conlist", family=FAMILY, tier=2,
        description="Batch models constraining list sizes via conlist(min_items/max_items).",
        migration_points=["conlist(min_items=/max_items=) removed (-> min_length=/max_length=, two models)"],
        files={
            "batches.py": (
                "from typing import List\n"
                "\n"
                "from pydantic import BaseModel, conlist\n"
                "\n"
                "\n"
                "class Batch(BaseModel):\n"
                "    items: conlist(int, min_items=1, max_items=3)\n"
                "\n"
                "\n"
                "class TagSet(BaseModel):\n"
                "    tags: conlist(str, min_items=1)\n"
                "\n"
                "\n"
                "def make_batch(items):\n"
                "    return Batch(items=list(items))\n"
                "\n"
                "\n"
                "def make_tags(tags):\n"
                "    return TagSet(tags=list(tags))\n"
            ),
            "test_batches.py": (
                "import pytest\n"
                "from pydantic import ValidationError\n"
                "\n"
                "from batches import make_batch, make_tags\n"
                "\n"
                "\n"
                "def test_ok():\n"
                "    assert make_batch([1, 2]).items == [1, 2]\n"
                "    assert make_tags(['x']).tags == ['x']\n"
                "\n"
                "\n"
                "def test_too_many():\n"
                "    with pytest.raises(ValidationError):\n"
                "        make_batch([1, 2, 3, 4])\n"
                "\n"
                "\n"
                "def test_empty_tags():\n"
                "    with pytest.raises(ValidationError):\n"
                "        make_tags([])\n"
            ),
        },
    ))

    tasks.append(DepMigTask(
        id="p09_settings_optionals", family=FAMILY, tier=2,
        description="A service config stack combining BaseSettings and Optional-default fields.",
        migration_points=["BaseSettings import moved", "Optional[T] needs explicit defaults (two files)"],
        files={
            "conf.py": (
                "from typing import Optional\n"
                "\n"
                "from pydantic import BaseSettings\n"
                "\n"
                "\n"
                "class ServiceConf(BaseSettings):\n"
                "    name: str = 'svc'\n"
                "    region: Optional[str]\n"
                "    replicas: int = 1\n"
            ),
            "boot.py": (
                "from conf import ServiceConf\n"
                "\n"
                "\n"
                "def boot(**overrides):\n"
                "    conf = ServiceConf(**overrides)\n"
                "    return f'{conf.name}@{conf.region or \"local\"} x{conf.replicas}'\n"
            ),
            "test_boot.py": (
                "from boot import boot\n"
                "\n"
                "\n"
                "def test_defaults():\n"
                "    assert boot() == 'svc@local x1'\n"
                "\n"
                "\n"
                "def test_overrides():\n"
                "    assert boot(region='eu', replicas=3) == 'svc@eu x3'\n"
            ),
        },
    ))

    tasks.append(DepMigTask(
        id="p10_json_lines", family=FAMILY, tier=3,
        description="An audit sink writing models as JSON lines with a byte-exact contract.",
        migration_points=[
            "v2 .json() drops separator spaces — restore the contracted v1 formatting (silent output change)",
        ],
        files={
            "audit.py": (
                "from pydantic import BaseModel\n"
                "\n"
                "\n"
                "class Event(BaseModel):\n"
                "    kind: str\n"
                "    count: int\n"
                "\n"
                "\n"
                "def sink(events):\n"
                "    return [e.json() for e in events]\n"
            ),
            "test_audit.py": (
                "from audit import Event, sink\n"
                "\n"
                "\n"
                "def test_exact_lines():\n"
                "    lines = sink([Event(kind='login', count=2)])\n"
                "    assert lines == ['{\"kind\": \"login\", \"count\": 2}']\n"
            ),
        },
    ))

    return tasks
