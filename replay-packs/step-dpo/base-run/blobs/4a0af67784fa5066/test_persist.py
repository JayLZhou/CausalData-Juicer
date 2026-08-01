from persist import build_and_save, load


def test_pipeline(tmp_path):
    target = tmp_path / 'dag.gpickle'
    build_and_save([('a', 'b'), ('b', 'c')], target)
    graph = load(target)
    assert list(graph.successors('a')) == ['b']
    assert graph.is_directed()
