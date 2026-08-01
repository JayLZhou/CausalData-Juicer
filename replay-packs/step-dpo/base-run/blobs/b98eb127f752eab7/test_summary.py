from summary import summarize


def test_summary_counts():
    out = summarize([(1, 2), (2, 3)])
    assert out['nodes'] == 3
    assert out['edges'] == 2
    assert isinstance(out['text'], str) and out['text']
