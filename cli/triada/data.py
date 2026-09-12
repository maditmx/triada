"""Curriculum loading and progress persistence.

The progress file is byte-compatible with the web app's export, so you can move
a session between the browser and the terminal by copy-pasting one JSON file.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

TRACKS = ("typing", "nvim", "python")

_HERE = Path(__file__).resolve().parent
# curriculum/ sits next to cli/ in the repo; also allow an installed copy
_CANDIDATES = [
    _HERE.parent.parent / "curriculum",
    _HERE / "curriculum",
    Path(os.environ.get("TRIADA_CURRICULUM", "/nonexistent")),
]


def curriculum_dir() -> Path:
    for c in _CANDIDATES:
        if (c / "typing.json").exists():
            return c
    raise SystemExit(
        "Cannot find the curriculum/ directory. Set TRIADA_CURRICULUM to its path."
    )


_cache: dict = {}


def load_all() -> dict:
    if _cache:
        return _cache
    d = curriculum_dir()
    for name in TRACKS:
        with open(d / f"{name}.json", encoding="utf-8") as fh:
            _cache[name] = json.load(fh)
    with open(d / "combos.json", encoding="utf-8") as fh:
        _cache["combos"] = json.load(fh)
    return _cache


def home() -> Path:
    p = Path(os.environ.get("TRIADA_HOME", Path.home() / ".triada"))
    p.mkdir(parents=True, exist_ok=True)
    return p


def progress_path() -> Path:
    return home() / "progress.json"


def blank_progress() -> dict:
    return {
        "version": 1,
        "typing": {"lessons": {}, "level": 1},
        "nvim": {"lessons": {}, "level": 1},
        "python": {"lessons": {}, "level": 1},
        "combos": {},
        "keyStats": {},
        "totals": {"seconds": 0, "sessions": 0},
    }


class Progress:
    def __init__(self):
        self.data = blank_progress()
        self.load()

    def load(self):
        p = progress_path()
        if p.exists():
            try:
                raw = json.loads(p.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                return
            base = blank_progress()
            for t in TRACKS:
                base[t]["lessons"] = (raw.get(t) or {}).get("lessons", {})
                base[t]["level"] = (raw.get(t) or {}).get("level", 1)
            base["combos"] = raw.get("combos", {})
            base["keyStats"] = raw.get("keyStats", {})
            base["totals"] = raw.get("totals", base["totals"])
            self.data = base
        self.recompute()

    def save(self):
        try:
            progress_path().write_text(
                json.dumps(self.data, ensure_ascii=False, indent=1), encoding="utf-8"
            )
        except OSError:
            pass

    # ---- queries
    def done(self, track, lesson_id) -> bool:
        rec = self.data[track]["lessons"].get(lesson_id)
        return bool(rec and rec.get("done"))

    def record(self, track, lesson_id) -> dict:
        return self.data[track]["lessons"].get(lesson_id, {})

    def level_complete(self, track, level) -> bool:
        return all(self.done(track, ls["id"]) for ls in level["lessons"])

    def unlocked(self, track) -> int:
        return self.data[track]["level"]

    def stats(self, track) -> dict:
        cur = load_all()[track]
        total = sum(len(lv["lessons"]) for lv in cur["levels"])
        done = sum(
            1 for lv in cur["levels"] for ls in lv["lessons"] if self.done(track, ls["id"])
        )
        return {
            "done": done,
            "total": total,
            "pct": done / total if total else 0.0,
            "level": self.unlocked(track),
            "levels": len(cur["levels"]),
        }

    # ---- mutations
    def mark_done(self, track, lesson_id, score=None):
        rec = self.data[track]["lessons"].setdefault(lesson_id, {"done": False, "tries": 0})
        rec["done"] = True
        rec["tries"] = rec.get("tries", 0) + 1
        if score:
            best = rec.setdefault("best", {})
            for k, v in score.items():
                better = (k == "keys" and (k not in best or v < best[k])) or (
                    k != "keys" and (k not in best or v > best[k])
                )
                if better:
                    best[k] = v
            rec["last"] = score
        self.recompute()
        self.save()

    def mark_tried(self, track, lesson_id):
        rec = self.data[track]["lessons"].setdefault(lesson_id, {"done": False, "tries": 0})
        rec["tries"] = rec.get("tries", 0) + 1
        self.save()

    def bump_key(self, ch, n=1):
        self.data["keyStats"][ch] = self.data["keyStats"].get(ch, 0) + n

    def recompute(self):
        cur = load_all()
        for t in TRACKS:
            levels = cur[t]["levels"]
            unlocked = 1
            for i, lv in enumerate(levels):
                if self.level_complete(t, lv):
                    unlocked = min(len(levels), i + 2)
                else:
                    break
            self.data[t]["level"] = max(self.data[t].get("level", 1), unlocked)


def find_lesson(lesson_id: str):
    """Return (track, level, lesson) for a lesson id, or None."""
    cur = load_all()
    for t in TRACKS:
        for lv in cur[t]["levels"]:
            for ls in lv["lessons"]:
                if ls["id"] == lesson_id:
                    return t, lv, ls
    return None
