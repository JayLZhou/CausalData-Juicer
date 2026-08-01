from reports import cache_report, cached_degree


def test_report_and_cache(tmp_path):
    cache = tmp_path / 'g.gpickle'
    text = cache_report([(1, 2), (2, 3)], cache)
    assert isinstance(text, str) and text
    assert cached_degree(cache, 2) == 2
