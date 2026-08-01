from inventory import ensure_and_list_tables


def test_tables(tmp_path):
    url = f'sqlite:///{tmp_path}/app.db'
    assert ensure_and_list_tables(url) == ['users']
