"""Quick checks that need no database or print files. Run from the project folder:

    .venv/bin/python tests/test_smoke.py

1. Every /api/runs request shape reaches its builder with arguments the builder accepts
   (a by_model mix-up once broke every custom Sublimation run).
2. Sheet grouping: mixed fills sheets; model-wise never puts two models on a sheet.
3. Batch numbers continue from the counter, and a damaged counter stops the run.
"""

import inspect
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("RUNS_DIR", tempfile.mkdtemp())

import app.main as main  # noqa: E402
from app import runs  # noqa: E402


def test_run_requests_match_builders():
    called = []
    for name in ("create_run", "create_uv_custom_run", "create_sub_run", "create_custom_run"):
        sig = inspect.signature(getattr(main, name))

        def fake(*a, _sig=sig, _name=name, **k):
            _sig.bind(*a, **k)   # TypeError if main.py passes an argument the builder doesn't take
            called.append(_name)
            return {}
        setattr(main, name, fake)
    main._require_user = lambda request: "test"
    custom = [{"fetch_url": "custom://x.png", "name": "x", "copies": 1}]
    for body in ({"barcodes": ["B1"]}, {"custom": custom},
                 {"process": "sub", "barcodes": ["B1"], "by_model": False},
                 {"process": "sub", "custom": custom, "fit": True, "per_sheet": 2}):
        main.new_run(main.RunReq(**body), None)
    assert called == ["create_run", "create_uv_custom_run", "create_sub_run", "create_custom_run"], called


def test_sheet_groups():
    assert runs._sheet_groups(7, 3) == [[0, 1, 2], [3, 4, 5], [6]]
    models = ["A", "B", "A", "A", "B", "C", "A"]
    groups = runs._sheet_groups(len(models), 3, models)
    assert all(len({models[i] for i in g}) == 1 for g in groups), groups
    assert groups == [[0, 2, 3], [6], [1, 4], [5]], groups


def test_batch_counter():
    path = runs.RUNS_DIR / "batch_counter.txt"
    path.write_text("10000\n", encoding="utf-8")
    assert runs._new_batch_numbers(2) == ["MB10001", "MB10002"]
    assert path.read_text(encoding="utf-8") == "10002"
    path.write_text("", encoding="utf-8")
    try:
        runs._new_batch_numbers(1)
    except ValueError:
        pass
    else:
        raise AssertionError("an empty counter must not restart at MB00001")


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok ", name)
