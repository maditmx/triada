/* Run tests/vim_cases.json AND every nvim exercise through the JS engine.
 * Any divergence from the Python engine shows up here. */
const fs = require('fs');
const path = require('path');
const Vim = require(path.join(__dirname, '..', 'web', 'vimengine.js'));

const eq = (a, b) => a.length === b.length && a.every((x, i) => x === b[i]);
let fails = 0;
let n = 0;

function check(label, lines, cursor, keys, wantLines, wantCursor, wantMode) {
  n += 1;
  const v = new Vim(lines, cursor);
  try {
    v.feed(keys);
  } catch (e) {
    console.log(`FAIL ${label}: threw ${e.message}`);
    fails += 1;
    return;
  }
  if (!eq(v.lines, wantLines)) {
    console.log(`FAIL ${label} keys=${JSON.stringify(keys)}`);
    console.log(`   got  ${JSON.stringify(v.lines)}`);
    console.log(`   want ${JSON.stringify(wantLines)}`);
    fails += 1;
    return;
  }
  if (wantCursor && (v.row !== wantCursor[0] || v.col !== wantCursor[1])) {
    console.log(`FAIL ${label} keys=${JSON.stringify(keys)} cursor [${v.row},${v.col}] != [${wantCursor}]`);
    fails += 1;
    return;
  }
  if (wantMode && v.mode !== wantMode) {
    console.log(`FAIL ${label} mode ${v.mode} != ${wantMode}`);
    fails += 1;
  }
}

const cases = JSON.parse(fs.readFileSync(path.join(__dirname, 'vim_cases.json'), 'utf8'));
cases.forEach((c, i) => check(`case${i}`, c.lines, c.cursor, c.keys, c.lines_out, c.cursor_out, null));

const nvim = JSON.parse(
  fs.readFileSync(path.join(__dirname, '..', 'curriculum', 'nvim.json'), 'utf8')
);
for (const lv of nvim.levels) {
  for (const ls of lv.lessons) {
    if (ls.kind === 'quiz') continue;
    check(ls.id, ls.start.lines, ls.start.cursor, ls.solution,
      ls.goal.lines, ls.goal.cursor || null, ls.goal.mode || null);
    const v = new Vim(ls.start.lines, ls.start.cursor);
    v.feed(ls.solution);
    if (ls.par && v.typed !== ls.par) {
      console.log(`FAIL ${ls.id}: par ${ls.par} but JS engine counts ${v.typed} keys`);
      fails += 1;
    }
  }
}

console.log(`\n${n - fails}/${n} passed in the JS engine`);
process.exit(fails ? 1 : 0);
