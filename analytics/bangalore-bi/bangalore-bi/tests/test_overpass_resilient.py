"""The downloader must split heavy cells, resume without re-downloading, and remove duplicates."""
import random

import geopandas as gpd
from shapely.geometry import LineString, box

import overpass_resilient as o


class ConnectTimeout(Exception):
    pass


class InsufficientResponseError(Exception):
    pass


def make_world():
    rnd = random.Random(1)
    return [(i, LineString([(x, y), (x + 0.004, y + 0.004)]))
            for i, (x, y) in enumerate((rnd.uniform(0, 0.2), rnd.uniform(0, 0.2)) for _ in range(500))]


def test_split_resume_and_dedupe(tmp_path):
    world, calls = make_world(), {"n": 0}

    def fake_fetch(bbox, endpoint, timeout):
        calls["n"] += 1
        if bbox[2] - bbox[0] > 0.03:                    # heavy cell: the server always times out
            raise ConnectTimeout("simulated")
        b = box(*bbox)
        hits = [(i, g) for i, g in world if g.intersects(b)]
        if not hits:
            raise InsufficientResponseError("none")
        return gpd.GeoDataFrame({"element": ["way"] * len(hits), "id": [i for i, _ in hits],
                                 "highway": ["residential"] * len(hits)},
                                geometry=[g for _, g in hits], crs="EPSG:4326")

    cells = o.make_cells(box(0, 0, 0.2, 0.2), cell_deg=0.1)
    cache = str(tmp_path / "cache")
    failed = o.download_cells(cells, cache, fetch=fake_fetch, sleep=lambda s: None, log=lambda m: None)
    assert failed == []
    merged = o.merge_cache(cache)
    expected = {i for i, g in world if any(g.intersects(box(*c)) for c in cells)}
    assert set(merged["id"]) == expected and merged["id"].nunique() == len(merged)
    before = calls["n"]
    o.download_cells(cells, cache, fetch=fake_fetch, sleep=lambda s: None, log=lambda m: None)
    assert calls["n"] == before                         # second run downloads nothing
