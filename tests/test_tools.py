from metascript.agents import tools
import os


def test_compute_stats_basic():
    res = tools.compute_stats({"text": "a b\nc"})
    assert res["ok"]
    assert res["lines"] == 2
    assert res["words"] == 3


def test_safe_eval_arithmetic():
    res = tools.safe_eval({"expr": "2 + 3 * 4"})
    assert res["ok"] and res["result"] == 14


def test_http_get_example_com():
    res = tools.http_get({"url": "https://example.com/"})
    assert res["ok"] and "Example Domain" in res["body"]


def test_read_write_and_list(tmp_path):
    p = tmp_path / "subdir"
    p.mkdir()
    f = p / "t.txt"
    path = str(f)
    w = tools.write_file({"path": path, "content": "hello"})
    assert w["ok"]
    r = tools.read_file({"path": path})
    assert r["ok"] and r["text"] == "hello"
    l = tools.list_dir({"path": str(p)})
    assert l["ok"] and "t.txt" in l["entries"]


def test_format_code_and_plan():
    code = "print(1 + 2)"
    res = tools.format_code({"code": code, "lang": "python"})
    assert res["ok"]
    plan = tools.get_plan({"code": code})
    assert plan["ok"] and isinstance(plan["plan"], dict)
