from banner import banner


def test_banner_centered():
    out = banner('hi')
    assert 'hi' in out
    assert out.startswith('=') and out.endswith('=')
    assert len(out) <= 40
