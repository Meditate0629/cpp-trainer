/* ============================================================
   计算概论 · 训练场 —— 前端逻辑（原生 JS，无依赖）
   ============================================================ */

const $ = (s) => document.querySelector(s);
const $$ = (s) => Array.from(document.querySelectorAll(s));

const ed = $('#editor');
const gutter = $('#gutter');

const S = {
  problems: [],
  byId: new Map(),
  cur: null,                 // 当前题目完整数据
  lang: localStorage.getItem('ts_lang') || 'cpp',
  codes: {},                 // pid -> {cpp, python}
  q: '', stage: 'ALL', status: 'ALL',
  listCollapsed: false,
};

/* ---------------- 基础工具 ---------------- */
function esc(s) {
  return String(s == null ? '' : s).replace(/[&<>"']/g, (c) => (
    { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}

async function api(path, body) {
  const opt = body
    ? { method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body) }
    : {};
  const r = await fetch(path, opt);
  const text = await r.text();
  let data;
  try {
    data = JSON.parse(text);
  } catch (e) {
    throw new Error('服务器返回了非 JSON 内容：' + text.slice(0, 200));
  }
  if (data && data.ok === false) throw new Error(data.error || '请求失败');
  return data;
}

function setFoot(t) { $('#footStat').textContent = t || ''; }

/* ---------------- 主题 ---------------- */
function applyTheme(t) {
  document.documentElement.dataset.theme = t;
  localStorage.setItem('ts_theme', t);
}
$('#themeBtn').addEventListener('click', () => {
  applyTheme(document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark');
});

/* ---------------- 编辑器 ---------------- */
function syncGutter() {
  const n = ed.value.split('\n').length;
  if (String(n) !== gutter.dataset.n) {
    gutter.dataset.n = String(n);
    let s = '';
    for (let i = 1; i <= n; i++) s += i + (i < n ? '\n' : '');
    gutter.textContent = s;
  }
  gutter.scrollTop = ed.scrollTop;
}

function setCode(text) {
  ed.value = text == null ? '' : text;
  ed.scrollTop = 0;
  ed.scrollLeft = 0;
  syncGutter();
}

ed.addEventListener('scroll', () => { gutter.scrollTop = ed.scrollTop; });
ed.addEventListener('input', () => { syncGutter(); scheduleSave(); });

ed.addEventListener('keydown', (e) => {
  if (e.key === 'Tab') {
    e.preventDefault();
    const a = ed.selectionStart, b = ed.selectionEnd, v = ed.value;
    ed.value = v.slice(0, a) + '    ' + v.slice(b);
    ed.selectionStart = ed.selectionEnd = a + 4;
    syncGutter();
    scheduleSave();
    return;
  }
  if (e.key === 'Enter' && !e.ctrlKey && !e.metaKey) {
    const v = ed.value, pos = ed.selectionStart;
    const lineStart = v.lastIndexOf('\n', pos - 1) + 1;
    const line = v.slice(lineStart, pos);
    const m = line.match(/^[ \t]*/);
    const indent = m ? m[0] : '';
    const extra = /[{(]\s*$/.test(line) ? '    ' : '';
    if (!indent && !extra) return;
    e.preventDefault();
    const ins = '\n' + indent + extra;
    ed.value = v.slice(0, pos) + ins + v.slice(pos);
    ed.selectionStart = ed.selectionEnd = pos + ins.length;
    syncGutter();
    scheduleSave();
  }
});

document.addEventListener('keydown', (e) => {
  if (!(e.ctrlKey || e.metaKey) || e.key !== 'Enter') return;
  e.preventDefault();
  if (e.shiftKey) doSubmit();
  else doRun();
});

/* ---------------- 自动保存 ---------------- */
let saveTimer = null, saving = false, saveAgain = false;

function scheduleSave() {
  if (!S.cur) return;
  clearTimeout(saveTimer);
  saveTimer = setTimeout(saveNow, 900);
}

async function saveNow() {
  if (!S.cur) return;
  const pid = S.cur.pid, lang = S.lang;
  if (!S.codes[pid]) S.codes[pid] = { cpp: '', python: '' };
  S.codes[pid][lang] = ed.value;
  if (saving) { saveAgain = true; return; }
  saving = true;
  try {
    await api('/api/code', { pid, lang, code: ed.value });
    setFoot('已保存 ' + new Date().toTimeString().slice(0, 8));
  } catch (e) {
    setFoot('保存失败：' + e.message);
  }
  saving = false;
  if (saveAgain) { saveAgain = false; saveNow(); }
}

/* ---------------- 题目列表 ---------------- */
const diffClass = (d) => d === '简单' ? 'easy' : d === '中等' ? 'mid' : 'hard';
const KIND_TITLE = {
  desc: '题目描述', input: '输入格式', output: '输出格式',
  hint: '提示', other: '说明',
};

function renderList() {
  const q = S.q.trim().toLowerCase();
  const groups = new Map();
  let shown = 0;

  for (const p of S.problems) {
    if (S.stage !== 'ALL' && p.stage !== S.stage) continue;
    if (S.status === 'DONE' && p.status !== '已通过') continue;
    if (S.status === 'TODO' && p.status === '已通过') continue;
    if (q) {
      const hay = (p.pid + ' ' + p.title + ' ' + p.tags.join(' ') + ' ' + p.num).toLowerCase();
      if (!hay.includes(q)) continue;
    }
    shown++;
    if (!groups.has(p.stage)) groups.set(p.stage, []);
    groups.get(p.stage).push(p);
  }

  const html = [];
  for (const [stage, items] of groups) {
    const done = items.filter((x) => x.status === '已通过').length;
    html.push(
      `<div class="stage-head"><span class="st-badge">${esc(stage)}</span>` +
      `<span>${esc(items[0].stageName.split('：')[0])}</span>` +
      `<span class="st-count">${done}/${items.length}</span></div>`
    );
    for (const p of items) {
      const active = S.cur && S.cur.pid === p.pid ? ' active' : '';
      const doneCls = p.status === '已通过' ? ' done' : '';
      html.push(
        `<div class="item${doneCls}${active}" data-pid="${esc(p.pid)}" title="${esc(p.title)}">` +
        `<span class="dot"></span>` +
        `<span class="idx">${esc(p.pid)}</span>` +
        `<span class="name">${esc(p.title)}</span></div>`
      );
    }
  }

  const list = $('#problemList');
  list.innerHTML = html.length ? html.join('') : '<div class="empty-hint sm">没有匹配的题目</div>';
  $('#listCount').textContent = `${shown} / ${S.problems.length} 题`;
  list.querySelectorAll('.item').forEach((el) => {
    el.addEventListener('click', () => selectProblem(el.dataset.pid));
  });
  updateProgress();
}

function updateProgress() {
  const done = S.problems.filter((p) => p.status === '已通过').length;
  $('#progressChip').textContent = `${done} / ${S.problems.length}`;
}

function renderStageFilter() {
  const seen = [];
  for (const p of S.problems) if (!seen.includes(p.stage)) seen.push(p.stage);
  const sel = $('#stageFilter');
  for (const s of seen) {
    const p = S.problems.find((x) => x.stage === s);
    const o = document.createElement('option');
    o.value = s;
    o.textContent = `${s} · ${p.stageName.split('：')[0]}`;
    sel.appendChild(o);
  }
}

/* ---------------- 选中题目 ---------------- */
async function selectProblem(pid) {
  if (S.cur && S.cur.pid === pid) return;
  await saveNow();
  let p;
  try {
    p = await api('/api/problem/' + encodeURIComponent(pid));
  } catch (e) {
    $('#descPane').innerHTML = `<div class="d-notice">加载失败：${esc(e.message)}</div>`;
    return;
  }
  S.cur = p;
  S.codes[p.pid] = { cpp: p.code.cpp, python: p.code.python };

  renderDesc(p);
  renderCasePick(p);
  selectTab('cases');
  $('#paneResult').innerHTML =
    '<div class="empty-hint sm">还没有运行结果。写好后点「运行」或「提交」。</div>';

  $('#langSel').value = S.lang;
  setCode(S.codes[p.pid][S.lang] || p.skeleton[S.lang] || '');
  setFoot('');
  loadHistory(p.pid);

  $$('.item').forEach((el) => el.classList.toggle('active', el.dataset.pid === p.pid));
  const act = $('.item.active');
  if (act) act.scrollIntoView({ block: 'nearest' });

  $('#customInput').value = p.cases.length ? p.cases[0].in : '';
}

/* ---------------- 题面 ---------------- */
function renderDesc(p) {
  const h = [];
  h.push(`<div class="d-title-row"><h1 class="d-title">${esc(p.title)}</h1>` +
    `<span class="d-num">${esc(p.pid)}</span></div>`);

  const meta = [
    `<span class="pill stage">${esc(p.stage)} · ${esc(p.stageName.split('：')[0])}</span>`,
    `<span class="pill ${diffClass(p.difficulty)}">${esc(p.difficulty)}</span>`,
    `<span class="pill tag">${esc(p.week)}</span>`,
    `<span class="pill tag">参考 ${p.loc} 行</span>`,
  ];
  if (p.status === '已通过') {
    meta.push(`<span class="pill ok">已通过${p.passedDate ? ' · ' + esc(p.passedDate) : ''}</span>`);
  }
  for (const t of p.tags) meta.push(`<span class="pill tag">${esc(t)}</span>`);
  h.push(`<div class="d-meta">${meta.join('')}</div>`);

  if (p.note) h.push(`<div class="d-notice">样例/参考解说明：${esc(p.note)}</div>`);

  const hasCases = p.cases.length > 0;
  for (const s of p.sections) {
    if (!hasCases && (s.key === 'sample_in' || s.key === 'sample_out')) {
      h.push(`<div class="sec"><h3>${esc(s.title)}</h3><pre>${esc(s.text)}</pre></div>`);
      continue;
    }
    if (s.key === 'sample_in' || s.key === 'sample_out') continue;
    if (s.key === 'pre') {
      h.push(`<div class="sec"><p>${esc(s.text)}</p></div>`);
      continue;
    }
    h.push(`<div class="sec"><h3>${esc(KIND_TITLE[s.key] || s.title || '说明')}</h3>` +
      `<p>${esc(s.text)}</p></div>`);
  }

  if (!p.sections.length && p.raw) {
    h.push(`<div class="sec"><pre>${esc(p.raw)}</pre></div>`);
  }

  p.cases.forEach((c, i) => {
    h.push(
      `<div class="example"><div class="ex-head">示例 ${i + 1}</div><div class="ex-grid">` +
      `<div class="ex-block"><div class="ex-lab">输入` +
      `${p.strict ? '（本题行尾空格也算错）' : ''}</div>` +
      `<pre>${esc(c.in === '' ? '(无输入)' : c.in)}</pre></div>` +
      `<div class="ex-block out"><div class="ex-lab">输出</div>` +
      `<pre>${esc(c.out === '' ? '(空)' : c.out)}</pre></div></div></div>`
    );
  });

  if (!hasCases) {
    h.push(`<div class="d-notice">这道题没有可自动判分的官方样例。` +
      `请用下面的「自定义输入」配合参考解对照来验证你的程序。</div>`);
  }

  $('#descPane').innerHTML = h.join('');
  $('#descPane').scrollTop = 0;
}

function renderCasePick(p) {
  const box = $('#casePick');
  const btns = [];
  p.cases.forEach((c, i) => {
    btns.push(`<button class="case-btn" data-i="${i}">示例 ${i + 1}</button>`);
  });
  btns.push('<button class="case-btn" data-i="-1">清空</button>');
  box.innerHTML = btns.join('');
  box.querySelectorAll('.case-btn').forEach((b) => {
    b.addEventListener('click', () => {
      const i = Number(b.dataset.i);
      $('#customInput').value = i < 0 ? '' : (p.cases[i] ? p.cases[i].in : '');
      box.querySelectorAll('.case-btn').forEach((x) => x.classList.remove('active'));
      if (i >= 0) b.classList.add('active');
    });
  });
}

/* ---------------- 标签 ---------------- */
function selectTab(name) {
  $$('.tab').forEach((t) => t.classList.toggle('active', t.dataset.tab === name));
  $('#paneCases').classList.toggle('active', name === 'cases');
  $('#paneResult').classList.toggle('active', name === 'result');
  $('#paneHistory').classList.toggle('active', name === 'history');
}
$$('.tab').forEach((t) => t.addEventListener('click', () => {
  selectTab(t.dataset.tab);
  if (t.dataset.tab === 'history' && S.cur) loadHistory(S.cur.pid);
}));

/* ---------------- 语言切换 ---------------- */
$('#langSel').value = S.lang;
$('#langSel').addEventListener('change', (e) => {
  if (!S.cur) { S.lang = e.target.value; return; }
  S.codes[S.cur.pid][S.lang] = ed.value;
  S.lang = e.target.value;
  localStorage.setItem('ts_lang', S.lang);
  setCode(S.codes[S.cur.pid][S.lang]);
  setFoot('已切到 ' + (S.lang === 'cpp' ? 'C++ 17' : 'Python 3'));
});

/* ---------------- 运行 ---------------- */
function setBusy(on, msg) {
  $('#runBtn').disabled = on;
  $('#submitBtn').disabled = on;
  $('#runCustomBtn').disabled = on;
  if (msg) setFoot(msg);
  else if (!on) setFoot('');
}

function renderError(title, msg) {
  $('#paneResult').innerHTML =
    `<div class="res-head verdict-fail">${esc(title)}</div>` +
    `<pre class="cc-pre">${esc(msg)}</pre>`;
}

async function doRun() {
  if (!S.cur) { setFoot('先选一道题'); return; }
  const pid = S.cur.pid;
  setBusy(true, '运行中…');
  try {
    const r = await api('/api/run', {
      pid, lang: S.lang, code: ed.value,
      input: $('#customInput').value,
      withRef: $('#withRef').checked,
    });
    renderRun(r);
    selectTab('result');
  } catch (e) {
    renderError('运行失败', e.message);
    selectTab('result');
  } finally {
    setBusy(false);
    if (S.codes[pid]) S.codes[pid][S.lang] = ed.value;
  }
}

function renderRun(r) {
  const h = [];
  if (!r.compile.ok) {
    h.push('<div class="res-head verdict-fail">编译失败</div>');
    h.push(`<pre class="cc-pre">${esc(r.compile.message || '(没有输出)')}</pre>`);
    $('#paneResult').innerHTML = h.join('');
    return;
  }
  if (r.compile.message) {
    h.push('<div class="res-head verdict-warn">编译通过（有警告）</div>');
    h.push(`<pre class="cc-pre">${esc(r.compile.message)}</pre>`);
  }

  const run = r.run;
  if (run.timeout) {
    h.push('<div class="res-head verdict-fail">运行超时</div>');
    h.push('<pre class="cc-pre">程序超过 5 秒还没结束，八成是死循环。检查 while 的循环变量有没有变化。</pre>');
  } else {
    h.push(`<div class="res-head">运行完成 <span class="res-time">${run.ms} ms</span></div>`);
    if (run.stderr && run.stderr.trim()) {
      h.push('<div class="cc-lab">标准错误 stderr</div>');
      h.push(`<pre class="cc-pre got">${esc(run.stderr)}</pre>`);
    }
    h.push('<div class="cc-lab">你的输出</div>');
    h.push(`<pre class="cc-pre">${esc(run.stdout === '' ? '(没有任何输出)' : run.stdout)}</pre>`);
  }

  if (r.ref) {
    if (!r.ref.ok) {
      h.push('<div class="cc-lab">参考解</div>');
      h.push(`<pre class="cc-pre">${esc(r.ref.error || '参考解不可用')}</pre>`);
    } else {
      h.push('<div class="cc-lab">参考解的输出</div>');
      h.push(`<pre class="cc-pre want">${esc(r.ref.timeout ? '(参考解也超时了，这组数据可能不合法)' : (r.ref.stdout === '' ? '(空)' : r.ref.stdout))}</pre>`);
      if (typeof r.ref.match === 'boolean') {
        if (r.ref.match) {
          h.push('<div class="res-head verdict-pass" style="margin-top:10px">✓ 和参考解一致</div>');
        } else {
          h.push('<div class="res-head verdict-fail" style="margin-top:10px">✗ 和参考解不一致</div>');
          for (const d of (r.ref.diff || [])) {
            h.push(`<div class="diff-line"><span class="ln">第 ${d.line} 行</span>` +
              `<span class="e">参考：${esc(JSON.stringify(d.expected))}</span><br>` +
              `<span class="ln"></span><span class="a">你写：${esc(JSON.stringify(d.actual))}</span></div>`);
          }
        }
      }
    }
  }
  $('#paneResult').innerHTML = h.join('');
}

/* ---------------- 提交 ---------------- */
const STATUS_TEXT = { PASS: '通过', FAIL: '输出不一致', TLE: '超时', RE: '运行错误' };

async function doSubmit() {
  if (!S.cur) { setFoot('先选一道题'); return; }
  const p = S.cur;
  setBusy(true, '判题中…');
  try {
    const r = await api('/api/submit', { pid: p.pid, lang: S.lang, code: ed.value });
    if (r.error) {
      renderError('无法判题', r.error);
      selectTab('result');
      return;
    }
    renderSubmit(r, p);
    selectTab('result');
    if (r.total && r.passed === r.total) {
      p.status = '已通过';
      p.passedDate = r.passedDate || p.passedDate;
      const bp = S.byId.get(p.pid);
      if (bp) { bp.status = '已通过'; bp.passedDate = p.passedDate; }
      renderList();
      renderDesc(p);
      loadHistory(p.pid);
    }
  } catch (e) {
    renderError('判题失败', e.message);
    selectTab('result');
  } finally {
    setBusy(false);
  }
}

function renderSubmit(r, p) {
  const h = [];
  if (r.verdict === '编译失败') {
    h.push('<div class="res-head verdict-fail">编译失败</div>');
    h.push(`<pre class="cc-pre">${esc((r.compile && r.compile.message) || '(没有输出)')}</pre>`);
    $('#paneResult').innerHTML = h.join('');
    return;
  }

  const allPass = r.passed === r.total;
  h.push(`<div class="res-head ${allPass ? 'verdict-pass' : 'verdict-fail'}">` +
    `${allPass ? '✓ 全部通过' : '✗ 未通过'}　通过 ${r.passed} / ${r.total}` +
    `<span class="res-time">${S.lang === 'cpp' ? 'C++ 17' : 'Python 3'}</span></div>`);

  if (r.compile && r.compile.message) {
    h.push(`<div class="cc-lab">编译器警告</div><pre class="cc-pre">${esc(r.compile.message)}</pre>`);
  }

  for (const c of r.cases) {
    const ok = c.status === 'PASS';
    h.push(`<div class="case-card ${ok ? 'pass' : 'fail'}">`);
    h.push(`<div class="cc-head">用例 ${c.idx} · ${STATUS_TEXT[c.status] || c.status}` +
      `　<span class="res-time">${c.ms} ms</span></div>`);
    h.push('<div class="cc-body">');
    if (!ok) {
      h.push('<div class="cc-lab">输入</div>');
      h.push(`<pre class="cc-pre">${esc(c.input || '(无输入)')}</pre>`);
      h.push('<div class="cc-lab">期望输出</div>');
      h.push(`<pre class="cc-pre want">${esc(c.expected)}</pre>`);
      h.push('<div class="cc-lab">你的输出</div>');
      h.push(`<pre class="cc-pre got">${esc(c.actual === '' ? '(没有任何输出)' : c.actual)}</pre>`);
      if (c.stderr && c.stderr.trim()) {
        h.push('<div class="cc-lab">标准错误</div>');
        h.push(`<pre class="cc-pre">${esc(c.stderr)}</pre>`);
      }
      if (c.message && c.status !== 'FAIL') {
        h.push(`<div class="cc-lab">${esc(c.message)}</div>`);
      }
      for (const d of (c.diff || [])) {
        h.push(`<div class="diff-line"><span class="ln">第 ${d.line} 行</span>` +
          `<span class="e">期望：${esc(JSON.stringify(d.expected))}</span><br>` +
          `<span class="ln"></span><span class="a">实际：${esc(JSON.stringify(d.actual))}</span></div>`);
      }
    } else if (c.message) {
      h.push(`<div class="cc-lab">${esc(c.message)}</div>`);
    } else {
      h.push('<div class="cc-lab">输出与期望完全一致</div>');
    }
    h.push('</div></div>');
  }

  if (allPass && !p.passedDate) {
    h.push('<div class="d-notice" style="color:var(--green);background:var(--green-soft)">' +
      '已写进《进度追踪表.csv》。按计划，错过的题要在 +1 / +3 / +7 / +21 天各盲写一遍。</div>');
  }
  $('#paneResult').innerHTML = h.join('');
}

/* ---------------- 提交记录 ---------------- */
async function loadHistory(pid) {
  try {
    const r = await api('/api/history?pid=' + encodeURIComponent(pid));
    const box = $('#paneHistory');
    if (!r.items.length) {
      box.innerHTML = '<div class="empty-hint sm">这道题还没有提交记录。</div>';
      return;
    }
    box.innerHTML = r.items.map((it) => {
      const pass = it.result === '通过';
      return `<div class="hist-row"><span class="h-ts">${esc((it.ts || '').replace('T', ' '))}</span>` +
        `<span class="h-lang">${esc(it.lang === 'cpp' ? 'C++' : 'Python')}</span>` +
        `<span class="h-res ${pass ? 'pass' : 'fail'}">${esc(it.result || '')}</span>` +
        `<span>${it.passed}/${it.total}</span>` +
        `<span class="h-ts">${it.ms ? it.ms + ' ms' : ''}</span></div>`;
    }).join('');
  } catch (e) {
    $('#paneHistory').innerHTML = `<div class="empty-hint sm">读取失败：${esc(e.message)}</div>`;
  }
}

/* ---------------- 参考解 ---------------- */
function hlCpp(src) {
  const KW = new Set(['if', 'else', 'for', 'while', 'do', 'switch', 'case', 'default',
    'break', 'continue', 'return', 'goto', 'struct', 'class', 'enum', 'union',
    'typedef', 'using', 'namespace', 'public', 'private', 'protected', 'template',
    'typename', 'const', 'static', 'inline', 'virtual', 'new', 'delete', 'this',
    'true', 'false', 'nullptr', 'sizeof', 'operator', 'throw', 'try', 'catch',
    'def', 'import', 'lambda', 'in', 'not', 'and', 'or', 'None', 'True', 'False', 'elif']);
  const TY = new Set(['int', 'long', 'short', 'char', 'float', 'double', 'bool', 'void',
    'unsigned', 'signed', 'size_t', 'string', 'auto', 'print']);
  let out = '', i = 0, n = src.length;
  const span = (cls, s) => `<span class="${cls}">${esc(s)}</span>`;
  while (i < n) {
    const c = src[i];
    if (c === '/' && src[i + 1] === '/') {
      let j = src.indexOf('\n', i); if (j < 0) j = n;
      out += span('c', src.slice(i, j)); i = j; continue;
    }
    if (c === '/' && src[i + 1] === '*') {
      let j = src.indexOf('*/', i + 2); j = j < 0 ? n : j + 2;
      out += span('c', src.slice(i, j)); i = j; continue;
    }
    if (c === '#') {
      let j = src.indexOf('\n', i); if (j < 0) j = n;
      out += span('p', src.slice(i, j)); i = j; continue;
    }
    if (c === '"' || c === "'") {
      const q = c; let j = i + 1;
      while (j < n) { if (src[j] === '\\') { j += 2; continue; } if (src[j] === q) { j++; break; } j++; }
      out += span('s', src.slice(i, j)); i = j; continue;
    }
    if (/[A-Za-z_]/.test(c)) {
      let j = i;
      while (j < n && /[A-Za-z0-9_]/.test(src[j])) j++;
      const w = src.slice(i, j);
      out += KW.has(w) ? span('k', w) : (TY.has(w) ? span('t', w) : esc(w));
      i = j; continue;
    }
    if (/[0-9]/.test(c)) {
      let j = i;
      while (j < n && /[0-9a-fA-FxX.]/.test(src[j])) j++;
      out += span('n', src.slice(i, j)); i = j; continue;
    }
    out += esc(c); i++;
  }
  return out;
}

function showModal(title, bodyHtml) {
  $('#modalTitle').textContent = title;
  $('#modalBody').innerHTML = bodyHtml;
  $('#modal').classList.remove('hidden');
}
function closeModal() { $('#modal').classList.add('hidden'); }
$('#modalClose').addEventListener('click', closeModal);
$('#modal').addEventListener('click', (e) => { if (e.target.id === 'modal') closeModal(); });
document.addEventListener('keydown', (e) => { if (e.key === 'Escape') closeModal(); });

async function showRef() {
  if (!S.cur) return;
  const p = S.cur;
  if (p.status !== '已通过') {
    const ok = confirm(
      '这道题你还没通过。\n\n' +
      '按计划：卡 20 分钟先看提示、卡 40 分钟才看参考解；看完必须合上，从空白文件重写一遍。\n\n' +
      '确定要看参考解吗？'
    );
    if (!ok) return;
  }
  try {
    const r = await api('/api/ref?pid=' + encodeURIComponent(p.pid));
    const note = p.note ? `<div class="modal-note">${esc(p.note)}</div>` : '';
    showModal(`参考解 · ${p.title}（${p.origin}）`,
      note + `<pre>${hlCpp(r.code)}</pre>`);
  } catch (e) {
    showModal('参考解不可用', `<div class="modal-note">${esc(e.message)}</div>`);
  }
}
$('#refBtn').addEventListener('click', showRef);

/* ---------------- 其它按钮 ---------------- */
$('#runBtn').addEventListener('click', doRun);
$('#submitBtn').addEventListener('click', doSubmit);
$('#runCustomBtn').addEventListener('click', doRun);

$('#reloadBtn').addEventListener('click', async () => {
  if (!S.cur) return;
  await saveNow();
  try {
    const p = await api('/api/problem/' + encodeURIComponent(S.cur.pid));
    S.cur = p;
    S.codes[p.pid] = { cpp: p.code.cpp, python: p.code.python };
    setCode(S.codes[p.pid][S.lang]);
    setFoot('已从磁盘重新读取');
  } catch (e) {
    setFoot('读取失败：' + e.message);
  }
});

$('#resetBtn').addEventListener('click', () => {
  if (!S.cur) return;
  if (!confirm('把当前语言的代码恢复成空白骨架？这个操作会覆盖你已经写的内容。')) return;
  setCode(S.cur.skeleton[S.lang]);
  scheduleSave();
});

$('#search').addEventListener('input', (e) => {
  S.q = e.target.value;
  renderList();
});
$('#stageFilter').addEventListener('change', (e) => {
  S.stage = e.target.value;
  renderList();
});
$('#statusFilter').addEventListener('change', (e) => {
  S.status = e.target.value;
  renderList();
});

$('#toggleList').addEventListener('click', () => {
  S.listCollapsed = !S.listCollapsed;
  $('#layout').classList.toggle('no-list', S.listCollapsed);
  $('#toggleList').textContent = S.listCollapsed ? '»' : '«';
});

/* ---------------- 启动 ---------------- */
async function boot() {
  applyTheme(localStorage.getItem('ts_theme') || 'light');
  try {
    const st = await api('/api/state');
    S.problems = st.problems;
    S.byId = new Map(st.problems.map((p) => [p.pid, p]));
    renderStageFilter();
    renderList();
    $('#langSel').value = S.lang;
    setFoot(`已装载 ${st.problems.length} 道题`);
    const first = st.problems.find((p) => p.status !== '已通过') || st.problems[0];
    if (first) selectProblem(first.pid);
  } catch (e) {
    $('#descPane').innerHTML =
      `<div class="d-notice">连不上本地服务：${esc(e.message)}<br><br>` +
      `请确认 启动网站.cmd 的窗口还开着，然后刷新这个页面。</div>`;
  }
}

boot();
