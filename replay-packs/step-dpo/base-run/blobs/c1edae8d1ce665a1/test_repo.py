from repo import add_item, count_items, make_session


def test_raw_sql_roundtrip(tmp_path):
    session = make_session(f'sqlite:///{tmp_path}/app.db')
    add_item(session, 'widget')
    add_item(session, 'gadget')
    assert count_items(session) == 2
