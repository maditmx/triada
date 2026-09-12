#!/usr/bin/env python3
"""Validate the curriculum.

- every nvim drill/move solution actually reaches its goal in the engine
- every python `code` exercise's reference solution passes its tests
- every quiz answer index is in range
- ids are unique, cross-track links point at real levels
"""
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
sys.path.insert(0, os.path.join(ROOT, "cli"))
from triada.vimengine import Vim  # noqa: E402

fails: list[str] = []
checked = {"nvim": 0, "python": 0, "typing": 0, "quiz": 0}


def load(name):
    with open(os.path.join(ROOT, "curriculum", f"{name}.json"), encoding="utf-8") as fh:
        return json.load(fh)


def check_nvim(doc):
    for lv in doc["levels"]:
        for ls in lv["lessons"]:
            if ls["kind"] == "quiz":
                if not (0 <= ls["answer"] < len(ls["options"])):
                    fails.append(f"{ls['id']}: answer index out of range")
                checked["quiz"] += 1
                continue
            v = Vim(ls["start"]["lines"], tuple(ls["start"]["cursor"]))
            try:
                v.feed(ls["solution"])
            except Exception as exc:  # noqa: BLE001
                fails.append(f"{ls['id']}: engine raised {exc!r}")
                continue
            g = ls["goal"]
            if v.lines != g["lines"]:
                fails.append(
                    f"{ls['id']} ({ls['title']}): lines mismatch\n"
                    f"    solution={ls['solution']!r}\n"
                    f"    got  {v.lines!r}\n"
                    f"    want {g['lines']!r}"
                )
            elif "cursor" in g and [v.row, v.col] != g["cursor"]:
                fails.append(
                    f"{ls['id']} ({ls['title']}): cursor {[v.row, v.col]} != {g['cursor']}"
                    f"  solution={ls['solution']!r}"
                )
            elif g.get("mode") and v.mode != g["mode"]:
                fails.append(f"{ls['id']}: mode {v.mode} != {g['mode']}")
            else:
                nkeys = v.typed
                if ls.get("par") and nkeys != ls["par"]:
                    fails.append(
                        f"{ls['id']}: par {ls['par']} but reference solution types {nkeys}"
                    )
            checked["nvim"] += 1


def check_python(doc):
    jobs = []
    for lv in doc["levels"]:
        for ls in lv["lessons"]:
            if ls["kind"] == "code":
                jobs.append(ls)
            elif ls["kind"] == "quiz":
                if not (0 <= ls["answer"] < len(ls["options"])):
                    fails.append(f"{ls['id']}: answer index out of range")
                checked["quiz"] += 1
            elif ls["kind"] == "output":
                jobs.append(ls)
    for ls in jobs:
        if ls["kind"] == "code":
            src = ls["solution"] + "\n\n" + ls["tests"] + "\nprint('__OK__')\n"
        else:
            src = ls["code"]
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, encoding="utf-8") as fh:
            fh.write(src)
            path = fh.name
        try:
            p = subprocess.run(
                [sys.executable, path], capture_output=True, text=True, timeout=20
            )
        finally:
            os.unlink(path)
        if ls["kind"] == "code":
            if "__OK__" not in p.stdout:
                fails.append(
                    f"{ls['id']} ({ls['title']}): reference solution fails tests\n"
                    f"    {p.stderr.strip().splitlines()[-1] if p.stderr.strip() else p.stdout.strip()}"
                )
        else:
            got = p.stdout.rstrip("\n")
            want = ls["answer"].rstrip("\n")
            if got != want:
                fails.append(
                    f"{ls['id']} ({ls['title']}): output mismatch\n"
                    f"    got  {got!r}\n    want {want!r}"
                )
        checked["python"] += 1


def check_combos(doc):
    for cb in doc["combos"]:
        v = Vim(cb["vim"]["start"]["lines"], tuple(cb["vim"]["start"]["cursor"]))
        try:
            v.feed(cb["vim"]["solution"])
        except Exception as exc:  # noqa: BLE001
            fails.append(f"{cb['id']}: engine raised {exc!r}")
            continue
        if v.lines != cb["vim"]["goal"]["lines"]:
            fails.append(
                f"{cb['id']} ({cb['title']}): vim solution misses the goal\n"
                f"    got  {v.lines!r}\n    want {cb['vim']['goal']['lines']!r}"
            )
        elif v.typed != cb["vim"]["par"]:
            fails.append(f"{cb['id']}: par {cb['vim']['par']} but solution types {v.typed}")
        if not (0 <= cb["python"]["answer"] < len(cb["python"]["options"])):
            fails.append(f"{cb['id']}: answer index out of range")
        if not cb["typing"]["content"].strip():
            fails.append(f"{cb['id']}: empty typing content")
        checked["combos"] = checked.get("combos", 0) + 1


def check_typing(doc):
    for lv in doc["levels"]:
        for ls in lv["lessons"]:
            if not ls["content"].strip():
                fails.append(f"{ls['id']}: empty content")
            checked["typing"] += 1


def check_structure(docs):
    ids = {}
    levels = set()
    for name, doc in docs.items():
        for lv in doc["levels"]:
            levels.add((name, lv["id"]))
            if lv["id"] in ids:
                fails.append(f"duplicate id {lv['id']}")
            ids[lv["id"]] = 1
            for ls in lv["lessons"]:
                if ls["id"] in ids:
                    fails.append(f"duplicate id {ls['id']}")
                ids[ls["id"]] = 1
    for name, doc in docs.items():
        for lv in doc["levels"]:
            for lk in lv.get("links", []):
                if (lk["track"], lk["level"]) not in levels:
                    fails.append(
                        f"{lv['id']}: link to missing {lk['track']}/{lk['level']}"
                    )


def main():
    docs = {n: load(n) for n in ("typing", "nvim", "python")}
    check_structure(docs)
    check_typing(docs["typing"])
    check_nvim(docs["nvim"])
    check_python(docs["python"])
    check_combos(load("combos"))
    print(
        f"checked: {checked['nvim']} vim drills, {checked['python']} python exercises, "
        f"{checked['quiz']} quizzes, {checked['typing']} typing lessons, "
        f"{checked.get('combos', 0)} combos"
    )
    if fails:
        print(f"\n{len(fails)} FAILURES\n" + "-" * 60)
        for f in fails:
            print(f)
        return 1
    print("all good")
    return 0


if __name__ == "__main__":
    sys.exit(main())
