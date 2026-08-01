from logstore import add, count, init


def test_log_roundtrip(tmp_path):
    engine = init(f'sqlite:///{tmp_path}/logs.db')
    add(engine, 'boot')
    add(engine, 'ready')
    assert count(engine) == 2
