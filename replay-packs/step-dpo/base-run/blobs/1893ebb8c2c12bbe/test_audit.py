from audit import count_users, record_user


def test_records_persist(tmp_path):
    url = f'sqlite:///{tmp_path}/audit.db'
    record_user(url, 'ada')
    record_user(url, 'grace')
    assert count_users(url) == 2
