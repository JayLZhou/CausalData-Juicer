from queries import fetch_names, seed


def test_roundtrip(tmp_path):
    url = f'sqlite:///{tmp_path}/app.db'
    seed(url, ['ada', 'grace'])
    assert fetch_names(url) == ['ada', 'grace']
