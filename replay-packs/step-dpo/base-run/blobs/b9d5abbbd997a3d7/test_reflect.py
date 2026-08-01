from reflect import reflect_user_columns


def test_reflection(tmp_path):
    url = f'sqlite:///{tmp_path}/app.db'
    assert reflect_user_columns(url) == ['id', 'name']
