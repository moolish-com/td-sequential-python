"""Parity with the shared fixtures, and with the JavaScript reference when node is available."""

import dataclasses
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from td_sequential import compute

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = sorted((ROOT / "tests" / "fixtures").glob("*.json"))
NODE = shutil.which("node")
# Path of the JavaScript reference module; override with TD_SEQUENTIAL_JS.
JS_MODULE = Path(os.environ.get("TD_SEQUENTIAL_JS", ROOT.parent / "td-sequential" / "src" / "td-sequential.js"))
FLAG_FIELDS = ["buy_perfected", "sell_perfected", "bullish_flip", "bearish_flip"]


def snake(name):
    return re.sub(r"([A-Z])", lambda m: "_" + m.group(1).lower(), name)


def load(path):
    return json.loads(path.read_text())


def test_fixtures_present():
    assert len(FIXTURES) >= 8


@pytest.mark.parametrize("path", FIXTURES, ids=lambda p: p.name)
def test_counting_fields_match_fixture(path):
    fx = load(path)
    got = compute(fx["bars"])
    assert len(got) == len(fx["expected"])
    for i, (record, want) in enumerate(zip(got, fx["expected"])):
        have = {k: getattr(record, snake(k)) for k in want}
        assert have == want, f"bar {i}"


@pytest.mark.parametrize("path", FIXTURES, ids=lambda p: p.name)
def test_flags_are_consistent_with_counts(path):
    got = compute(load(path)["bars"])
    bars = load(path)["bars"]
    for i, r in enumerate(got):
        if r.buy_perfected:
            assert r.buy_setup == 9
        if r.sell_perfected:
            assert r.sell_setup == 9
        if r.bullish_flip:
            assert i >= 5 and bars[i - 1]["c"] < bars[i - 5]["c"] and bars[i]["c"] > bars[i - 4]["c"]
        if r.bearish_flip:
            assert i >= 5 and bars[i - 1]["c"] > bars[i - 5]["c"] and bars[i]["c"] < bars[i - 4]["c"]
    # Each fixture is long enough to contain at least one setup 9 and one flip.
    assert any(r.buy_setup == 9 or r.sell_setup == 9 for r in got)
    assert any(r.bullish_flip or r.bearish_flip for r in got)


JS_RUNNER = """
import { readFileSync } from 'node:fs';
import { pathToFileURL } from 'node:url';
const [modulePath, fixturePath] = process.argv.slice(2);
const { computeTdSequential } = await import(pathToFileURL(modulePath).href);
const { bars } = JSON.parse(readFileSync(fixturePath, 'utf8'));
process.stdout.write(JSON.stringify(computeTdSequential(bars)));
"""


@pytest.mark.skipif(NODE is None, reason="node is not installed")
@pytest.mark.skipif(not JS_MODULE.is_file(), reason="JavaScript reference module not found (set TD_SEQUENTIAL_JS)")
@pytest.mark.parametrize("path", FIXTURES, ids=lambda p: p.name)
def test_all_twelve_fields_match_javascript_reference(path, tmp_path):
    runner = tmp_path / "run.mjs"
    runner.write_text(JS_RUNNER)
    proc = subprocess.run(
        [NODE, str(runner), str(JS_MODULE), str(path)],
        capture_output=True, text=True, timeout=60, check=False,
    )
    assert proc.returncode == 0, proc.stderr
    want = [{snake(k): v for k, v in rec.items()} for rec in json.loads(proc.stdout)]
    got = [dataclasses.asdict(r) for r in compute(load(path)["bars"])]
    assert len(got) == len(want)
    assert len(want[0]) == 13  # t plus the twelve indicator fields
    for i, (g, w) in enumerate(zip(got, want)):
        assert g == w, f"bar {i}"
