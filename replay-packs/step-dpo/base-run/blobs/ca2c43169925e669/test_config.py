from config import load_config


def test_defaults():
    cfg = load_config()
    assert cfg.app_name == 'svc'
    assert cfg.max_retries == 3
    assert cfg.debug is False


def test_overrides():
    cfg = load_config(debug=True, max_retries=5)
    assert cfg.debug is True
    assert cfg.max_retries == 5
