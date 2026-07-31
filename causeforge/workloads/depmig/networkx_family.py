"""networkx 2.8 -> 3.x migration family (6 tasks, pure-python only —
no numpy/scipy-coupled APIs so the family is orthogonal to the numpy one).

Breaks used:
  k01  nx.info removed
  k02  nx.write_gpickle / nx.read_gpickle removed
  k03  nx.OrderedGraph removed (+ nx.info, multi-point)
  k04  nx.jit_data / nx.jit_graph removed (serialization pair)
  k05  gpickle + OrderedDiGraph in a two-module pipeline (multi-file)
  k06  nx.to_dict_of_dicts round-trip with removed helpers (multi-point)

Tier note: this family has no true silent-semantics task (candidates are
all numpy-coupled); it ships 2xT1 + 4xT2 and the spec's T3 quota is
carried by the other families.
"""
from __future__ import annotations

from causeforge.workloads.depmig.base import DepMigTask, Family

FAMILY = Family(
    name="networkx",
    old_pins=["networkx==2.8.8"],
    new_pins=["networkx==3.3"],
)


def build_tasks() -> list[DepMigTask]:
    tasks: list[DepMigTask] = []

    tasks.append(DepMigTask(
        id="k01_info", family=FAMILY, tier=1,
        description="A graph summary helper built on nx.info.",
        migration_points=["nx.info removed (compose from number_of_nodes/edges)"],
        files={
            "summary.py": (
                "import networkx as nx\n"
                "\n"
                "\n"
                "def summarize(edges):\n"
                "    graph = nx.Graph(edges)\n"
                "    text = nx.info(graph)\n"
                "    return {'nodes': graph.number_of_nodes(),\n"
                "            'edges': graph.number_of_edges(),\n"
                "            'text': text}\n"
            ),
            "test_summary.py": (
                "from summary import summarize\n"
                "\n"
                "\n"
                "def test_summary_counts():\n"
                "    out = summarize([(1, 2), (2, 3)])\n"
                "    assert out['nodes'] == 3\n"
                "    assert out['edges'] == 2\n"
                "    assert isinstance(out['text'], str) and out['text']\n"
            ),
        },
    ))

    tasks.append(DepMigTask(
        id="k02_gpickle", family=FAMILY, tier=1,
        description="Graph persistence via nx.write_gpickle / nx.read_gpickle.",
        migration_points=["gpickle helpers removed (-> pickle module)"],
        files={
            "storage.py": (
                "import networkx as nx\n"
                "\n"
                "\n"
                "def save_graph(graph, path):\n"
                "    nx.write_gpickle(graph, path)\n"
                "\n"
                "\n"
                "def load_graph(path):\n"
                "    return nx.read_gpickle(path)\n"
            ),
            "test_storage.py": (
                "import networkx as nx\n"
                "\n"
                "from storage import load_graph, save_graph\n"
                "\n"
                "\n"
                "def test_roundtrip(tmp_path):\n"
                "    graph = nx.path_graph(4)\n"
                "    target = tmp_path / 'g.gpickle'\n"
                "    save_graph(graph, target)\n"
                "    loaded = load_graph(target)\n"
                "    assert sorted(loaded.edges()) == sorted(graph.edges())\n"
            ),
        },
    ))

    tasks.append(DepMigTask(
        id="k03_ordered_graph", family=FAMILY, tier=2,
        description="A pipeline that builds nx.OrderedGraph instances and reports on them.",
        migration_points=["nx.OrderedGraph removed (Graph preserves insertion order)",
                          "nx.info removed"],
        files={
            "pipeline.py": (
                "import networkx as nx\n"
                "\n"
                "\n"
                "def build(edges):\n"
                "    graph = nx.OrderedGraph()\n"
                "    graph.add_edges_from(edges)\n"
                "    return graph\n"
                "\n"
                "\n"
                "def describe(edges):\n"
                "    graph = build(edges)\n"
                "    return f'{nx.info(graph)}|order={list(graph.nodes())}'\n"
            ),
            "test_pipeline.py": (
                "from pipeline import build, describe\n"
                "\n"
                "\n"
                "def test_insertion_order_kept():\n"
                "    graph = build([(3, 1), (1, 2)])\n"
                "    assert list(graph.nodes()) == [3, 1, 2]\n"
                "\n"
                "\n"
                "def test_describe():\n"
                "    out = describe([(1, 2)])\n"
                "    assert 'order=[1, 2]' in out\n"
            ),
        },
    ))

    tasks.append(DepMigTask(
        id="k04_jit", family=FAMILY, tier=2,
        description="JSON serialization via the removed JIT graph format.",
        migration_points=["nx.jit_data / nx.jit_graph removed (-> node_link JSON)"],
        files={
            "jsonio.py": (
                "import networkx as nx\n"
                "\n"
                "\n"
                "def to_json(graph):\n"
                "    return nx.jit_data(graph)\n"
                "\n"
                "\n"
                "def from_json(data):\n"
                "    return nx.jit_graph(data)\n"
            ),
            "test_jsonio.py": (
                "import networkx as nx\n"
                "\n"
                "from jsonio import from_json, to_json\n"
                "\n"
                "\n"
                "def test_roundtrip():\n"
                "    graph = nx.Graph([(1, 2), (2, 3)])\n"
                "    data = to_json(graph)\n"
                "    loaded = from_json(data)\n"
                "    assert sorted(loaded.nodes()) == [1, 2, 3]\n"
                "    assert loaded.number_of_edges() == 2\n"
            ),
        },
    ))

    tasks.append(DepMigTask(
        id="k05_persist_pipeline", family=FAMILY, tier=2,
        description="A two-module ETL: ordered DiGraph construction persisted with gpickle.",
        migration_points=["nx.OrderedDiGraph removed", "gpickle helpers removed"],
        files={
            "build_graph.py": (
                "import networkx as nx\n"
                "\n"
                "\n"
                "def dag_from_pairs(pairs):\n"
                "    graph = nx.OrderedDiGraph()\n"
                "    graph.add_edges_from(pairs)\n"
                "    return graph\n"
            ),
            "persist.py": (
                "import networkx as nx\n"
                "\n"
                "from build_graph import dag_from_pairs\n"
                "\n"
                "\n"
                "def build_and_save(pairs, path):\n"
                "    graph = dag_from_pairs(pairs)\n"
                "    nx.write_gpickle(graph, path)\n"
                "\n"
                "\n"
                "def load(path):\n"
                "    return nx.read_gpickle(path)\n"
            ),
            "test_persist.py": (
                "from persist import build_and_save, load\n"
                "\n"
                "\n"
                "def test_pipeline(tmp_path):\n"
                "    target = tmp_path / 'dag.gpickle'\n"
                "    build_and_save([('a', 'b'), ('b', 'c')], target)\n"
                "    graph = load(target)\n"
                "    assert list(graph.successors('a')) == ['b']\n"
                "    assert graph.is_directed()\n"
            ),
        },
    ))

    tasks.append(DepMigTask(
        id="k06_report_tool", family=FAMILY, tier=2,
        description="A reporting tool combining nx.info with gpickle-backed caching.",
        migration_points=["nx.info removed", "nx.read_gpickle/write_gpickle removed"],
        files={
            "reports.py": (
                "import networkx as nx\n"
                "\n"
                "\n"
                "def cache_report(edges, cache_path):\n"
                "    graph = nx.Graph(edges)\n"
                "    nx.write_gpickle(graph, cache_path)\n"
                "    return nx.info(graph)\n"
                "\n"
                "\n"
                "def cached_degree(cache_path, node):\n"
                "    graph = nx.read_gpickle(cache_path)\n"
                "    return graph.degree(node)\n"
            ),
            "test_reports.py": (
                "from reports import cache_report, cached_degree\n"
                "\n"
                "\n"
                "def test_report_and_cache(tmp_path):\n"
                "    cache = tmp_path / 'g.gpickle'\n"
                "    text = cache_report([(1, 2), (2, 3)], cache)\n"
                "    assert isinstance(text, str) and text\n"
                "    assert cached_degree(cache, 2) == 2\n"
            ),
        },
    ))

    tasks.append(DepMigTask(
        id="k07_log_summary", family=FAMILY, tier=1,
        description="A monitoring hook logging graphs via nx.info.",
        migration_points=["nx.info removed"],
        files={
            "monitor.py": (
                "import networkx as nx\n"
                "\n"
                "\n"
                "def log_line(edges):\n"
                "    graph = nx.Graph(edges)\n"
                "    return f'[graph] {nx.info(graph)}'\n"
            ),
            "test_monitor.py": (
                "from monitor import log_line\n"
                "\n"
                "\n"
                "def test_log_line():\n"
                "    out = log_line([(1, 2), (2, 3)])\n"
                "    assert out.startswith('[graph] ') and len(out) > 10\n"
            ),
        },
    ))

    tasks.append(DepMigTask(
        id="k08_jit_cache", family=FAMILY, tier=2,
        description="A JSON cache layer built on the removed JIT format plus nx.info.",
        migration_points=["nx.jit_data/jit_graph removed", "nx.info removed"],
        files={
            "cache.py": (
                "import networkx as nx\n"
                "\n"
                "\n"
                "def dump(graph):\n"
                "    return {'payload': nx.jit_data(graph), 'summary': nx.info(graph)}\n"
                "\n"
                "\n"
                "def load(entry):\n"
                "    return nx.jit_graph(entry['payload'])\n"
            ),
            "test_cache.py": (
                "import networkx as nx\n"
                "\n"
                "from cache import dump, load\n"
                "\n"
                "\n"
                "def test_roundtrip_with_summary():\n"
                "    entry = dump(nx.path_graph(3))\n"
                "    assert isinstance(entry['summary'], str)\n"
                "    assert sorted(load(entry).nodes()) == [0, 1, 2]\n"
            ),
        },
    ))

    tasks.append(DepMigTask(
        id="k09_ordered_store", family=FAMILY, tier=2,
        description="An ordered-graph store persisting via gpickle across two modules.",
        migration_points=["nx.OrderedGraph removed", "gpickle helpers removed"],
        files={
            "graphs.py": (
                "import networkx as nx\n"
                "\n"
                "\n"
                "def ordered_from(edges):\n"
                "    graph = nx.OrderedGraph()\n"
                "    graph.add_edges_from(edges)\n"
                "    return graph\n"
            ),
            "store.py": (
                "import networkx as nx\n"
                "\n"
                "from graphs import ordered_from\n"
                "\n"
                "\n"
                "def save(edges, path):\n"
                "    nx.write_gpickle(ordered_from(edges), path)\n"
                "\n"
                "\n"
                "def node_order(path):\n"
                "    return list(nx.read_gpickle(path).nodes())\n"
            ),
            "test_store.py": (
                "from store import node_order, save\n"
                "\n"
                "\n"
                "def test_order_survives_roundtrip(tmp_path):\n"
                "    target = tmp_path / 'g.gpickle'\n"
                "    save([(9, 1), (1, 5)], target)\n"
                "    assert node_order(target) == [9, 1, 5]\n"
            ),
        },
    ))

    tasks.append(DepMigTask(
        id="k10_dag_export", family=FAMILY, tier=2,
        description="A DAG exporter combining OrderedDiGraph and the JIT JSON format.",
        migration_points=["nx.OrderedDiGraph removed", "nx.jit_data/jit_graph removed"],
        files={
            "dag.py": (
                "import networkx as nx\n"
                "\n"
                "\n"
                "def export(pairs):\n"
                "    graph = nx.OrderedDiGraph()\n"
                "    graph.add_edges_from(pairs)\n"
                "    return nx.jit_data(graph)\n"
                "\n"
                "\n"
                "def restore(data):\n"
                "    return nx.jit_graph(data, create_using=nx.DiGraph())\n"
            ),
            "test_dag.py": (
                "from dag import export, restore\n"
                "\n"
                "\n"
                "def test_roundtrip_directed():\n"
                "    data = export([('a', 'b'), ('b', 'c')])\n"
                "    graph = restore(data)\n"
                "    assert graph.is_directed()\n"
                "    assert list(graph.successors('b')) == ['c']\n"
            ),
        },
    ))

    return tasks
