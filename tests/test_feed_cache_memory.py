"""The feeds disk cache is read once and written with the fast encoder.

The file is one JSON document of up to sixty entries, 8.6MB on the development
copy, where one company's SEC facts is 5.2MB of it. Every memory miss parsed
all of it: the macro calendar did on every ticker load (0.24s), and a cold
symbol's filings lookup parsed it twice and rewrote it once, where the rewrite
alone was 1.26s of a 1.77s profile. The writer was json.dump, which runs the
pure-Python encoder: 0.32s on that file against 0.056s for json.dumps. All of
it held the interpreter lock that every other leg of the load was waiting for.
"""
from __future__ import annotations

import json
import threading
import time

import pytest

from app import feeds


@pytest.fixture
def cache(tmp_path, monkeypatch):
    path = tmp_path / "feed_cache.json"
    monkeypatch.setattr(feeds, "CACHE_PATH", str(path))
    monkeypatch.setattr(feeds, "_DISK", {})
    monkeypatch.setattr(feeds, "_MEM", {})
    return path


def test_the_file_is_read_once_however_often_it_is_asked(cache, monkeypatch):
    cache.write_text(json.dumps({"k": {"at": time.time(), "text": "v"}}))
    reads = []
    real = feeds._read_disk
    monkeypatch.setattr(feeds, "_read_disk", lambda path: reads.append(path) or real(path))
    for _ in range(5):
        assert feeds._load_disk()["k"]["text"] == "v"
    assert len(reads) == 1


def test_a_fresh_entry_on_disk_is_served_without_reading_it_again(cache, monkeypatch):
    # The macro calendar's case: each FRED series was fresh on disk, missing
    # from memory, and read out of the whole file on every ticker load.
    cache.write_text(json.dumps({"text:fred": {"at": time.time(), "text": "DATE,VALUE\n", "error": None}}))
    reads = []
    real = feeds._read_disk
    monkeypatch.setattr(feeds, "_read_disk", lambda path: reads.append(path) or real(path))
    monkeypatch.setattr(feeds, "_fetch", lambda *a, **k: pytest.fail("fetched a fresh entry"))
    for _ in range(4):
        assert feeds.fetch_text("fred", 3600, key="text:fred") == "DATE,VALUE\n"
    assert len(reads) == 1


def test_a_new_path_is_read_afresh(cache, tmp_path, monkeypatch):
    cache.write_text(json.dumps({"a": {"at": 1}}))
    assert "a" in feeds._load_disk()
    other = tmp_path / "other.json"
    other.write_text(json.dumps({"b": {"at": 1}}))
    monkeypatch.setattr(feeds, "CACHE_PATH", str(other))
    assert set(feeds._load_disk()) == {"b"}


def test_a_store_writes_what_memory_holds_with_the_fast_encoder(cache, monkeypatch):
    def slow_path(*a, **k):
        raise AssertionError("json.dump to a file runs the pure-Python encoder")

    monkeypatch.setattr(feeds.json, "dump", slow_path)
    feeds._store("x", {"at": 1.0, "json": {"n": 1}})
    feeds._store("y", {"at": 2.0, "text": "t"})
    assert json.loads(cache.read_text()) == {"x": {"at": 1.0, "json": {"n": 1}},
                                             "y": {"at": 2.0, "text": "t"}}
    assert feeds._load_disk() == json.loads(cache.read_text())


def test_the_file_keeps_its_sixty_newest(cache):
    for i in range(65):
        feeds._store("k%d" % i, {"at": float(i)})
    kept = json.loads(cache.read_text())
    assert len(kept) == 60 and "k0" not in kept and "k64" in kept


def test_a_store_caught_between_serialising_and_writing_cannot_put_back_an_older_file(
        cache, monkeypatch):
    # Every store writes the same temporary file. Unserialised, a store paused
    # after serialising would write its older text over a later store's file,
    # and the newer entry would be gone from disk while memory still held it.
    real = json.dumps
    paused = threading.Event()

    def dumps(obj, *args, **kwargs):
        text = real(obj, *args, **kwargs)
        if not paused.is_set():
            paused.set()
            time.sleep(0.2)
        return text

    monkeypatch.setattr(feeds.json, "dumps", dumps)
    first = threading.Thread(target=feeds._store, args=("a", {"at": 1.0}))
    first.start()
    assert paused.wait(2)
    feeds._store("b", {"at": 2.0})
    first.join(5)
    assert json.loads(cache.read_text()) == {"a": {"at": 1.0}, "b": {"at": 2.0}}
