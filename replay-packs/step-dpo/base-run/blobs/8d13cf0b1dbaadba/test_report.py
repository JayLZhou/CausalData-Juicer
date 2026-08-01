from report import Metric, render_report


def test_single_metric_exact_format():
    out = render_report([Metric(name='latency', value=1.5)])
    assert out == '{"name": "latency", "value": 1.5}'


def test_multiline_report():
    out = render_report([
        Metric(name='a', value=1.0),
        Metric(name='b', value=2.0),
    ])
    assert out.splitlines() == [
        '{"name": "a", "value": 1.0}',
        '{"name": "b", "value": 2.0}',
    ]
