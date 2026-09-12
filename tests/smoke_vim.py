import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "cli"))
from triada.vimengine import Vim

CASES = [
    # (lines, cursor, keys, expected_lines, expected_cursor or None)
    (["hello world"], (0, 0), "dw", ["world"], (0, 0)),
    (["hello world"], (0, 0), "de", [" world"], (0, 0)),
    (["hello world"], (0, 6), "daw", ["hello"], None),
    (["hello world"], (0, 6), "diw", ["hello "], None),
    (["hello world"], (0, 0), "x", ["ello world"], (0, 0)),
    (["hello world"], (0, 0), "3x", ["lo world"], (0, 0)),
    (["hello"], (0, 0), "cwbye<Esc>", ["bye"], (0, 2)),
    (["foo(bar, baz)"], (0, 5), "ci(x<Esc>", ["foo(x)"], None),
    (["foo(bar, baz)"], (0, 5), "da(", ["foo"], None),
    (['x = "hola"'], (0, 6), 'ci"adios<Esc>', ['x = "adios"'], None),
    (["one", "two", "three"], (0, 0), "dd", ["two", "three"], (0, 0)),
    (["one", "two", "three"], (0, 0), "2dd", ["three"], (0, 0)),
    (["one", "two", "three"], (0, 0), "yyp", ["one", "one", "two", "three"], None),
    (["one", "two"], (0, 0), "ddp", ["two", "one"], None),
    (["ab"], (0, 0), "xp", ["ba"], None),
    (["one", "two"], (0, 0), "J", ["one two"], (0, 3)),
    (["one", "two"], (0, 0), "gJ", ["onetwo"], None),
    (["hello"], (0, 0), "rx", ["xello"], (0, 0)),
    (["hello"], (0, 0), "3rx", ["xxxlo"], None),
    (["hello"], (0, 0), "~", ["Hello"], None),
    (["hello world"], (0, 0), "gUiw", ["HELLO world"], None),
    (["HELLO"], (0, 0), "guu", ["hello"], None),
    (["a", "b", "c"], (0, 0), "GdG", ["a", "b"], None),
    (["a", "b", "c"], (2, 0), "ggdG", [""], None),
    (["hello world"], (0, 0), "$", ["hello world"], (0, 10)),
    (["hello world"], (0, 0), "f ", ["hello world"], (0, 5)),
    (["hello world"], (0, 0), "dfo", [" world"], None),
    (["hello world"], (0, 0), "dtw", ["world"], None),
    (["int x = 1;"], (0, 0), "A // ok<Esc>", ["int x = 1; // ok"], None),
    (["int x = 1;"], (0, 5), "I// <Esc>", ["// int x = 1;"], None),
    (["a"], (0, 0), "ob<Esc>", ["a", "b"], None),
    (["a"], (0, 0), "Ob<Esc>", ["b", "a"], None),
    (["one two three"], (0, 0), "wdw", ["one three"], None),
    (["one", "two"], (0, 0), "yyjp", ["one", "two", "one"], None),
    (["foo bar"], (0, 0), "veU", ["FOO bar"], None),
    (["foo bar"], (0, 0), "vey$p", ["foo barfoo"], None),
    (["a b c d"], (0, 0), "d2w", ["c d"], None),
    (["x=1"], (0, 0), "ciwy<Esc>", ["y=1"], None),
    (["hello"], (0, 0), "u", ["hello"], None),
    (["hello"], (0, 0), "xxu", ["ello"], None),
    (["hello"], (0, 0), "xxu\x12", ["llo"], None),
    (["aaa", "bbb"], (0, 0), "qaxq j@a", ["aa", "bb"], None),
    (["one two"], (0, 0), "dw.", [""], None),
    (["foo", "foo", "foo"], (0, 0), ":%s/foo/bar/g\r", ["bar", "bar", "bar"], None),
    (["a1", "b2", "a3"], (0, 0), ":g/a/d\r", ["b2"], None),
    (["z", "y", "x"], (0, 0), ":%sort\r", ["x", "y", "z"], None),
    (["hello world"], (0, 0), "/world\r", ["hello world"], (0, 6)),
    (["    indented"], (0, 4), "^", ["    indented"], (0, 4)),
    (["    indented"], (0, 4), "0", ["    indented"], (0, 0)),
    (["a", "b", "c"], (0, 0), "Vjd", ["c"], None),
    (["abc"], (0, 0), ">>", ["    abc"], None),
    (["    abc"], (0, 0), "<<", ["abc"], None),
    (["def f():", "    pass"], (0, 0), "jdd", ["def f():"], None),
    (["x = [1, 2, 3]"], (0, 5), "di[", ["x = []"], None),
    (["{a: 1}"], (0, 1), "ci{k<Esc>", ["{k}"], None),
    (["(a(b)c)"], (0, 0), "%", ["(a(b)c)"], (0, 6)),
    (["one", "", "two"], (0, 0), "}", ["one", "", "two"], (1, 0)),
    (["mark me", "x", "y"], (0, 0), "majjd`a", ["y"], None),
    (["abc def"], (0, 0), '"ayw"ap', ["aabc bc def"], None),
    (["a", "b"], (0, 0), "ma" + "j" + "d'a", [""], None),
]


def main():
    fails = 0
    for i, (lines, cur, keys, exp, expcur) in enumerate(CASES):
        v = Vim(lines, cur)
        try:
            v.feed(keys)
        except Exception as e:  # noqa
            print(f"FAIL {i:3d} {keys!r}: EXCEPTION {e!r}")
            fails += 1
            continue
        ok = v.lines == exp and (expcur is None or (v.row, v.col) == expcur)
        if not ok:
            fails += 1
            print(f"FAIL {i:3d} keys={keys!r}")
            print(f"       got  lines={v.lines!r} cur=({v.row},{v.col}) mode={v.mode}")
            print(f"       want lines={exp!r} cur={expcur}")
    print(f"\n{len(CASES) - fails}/{len(CASES)} passed")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
