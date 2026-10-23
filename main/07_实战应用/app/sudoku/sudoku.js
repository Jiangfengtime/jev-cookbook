'use strict';
const $ = id => document.getElementById(id);
let game = null, config = null, version = 0, selectedTrace = null;
let switching = false, inFlight = false, controlling = false, followLatest = true;
let lastTraceId = 0, driveVersion = 0, activeSingle = false, pauseRequested = false;

async function api(path, data) {
  const response = await fetch(path, data === undefined ? {cache: 'no-store'} : {
    method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(data)
  });
  let result;
  try { result = await response.json(); } catch { throw new Error('服务未返回 JSON，请用 serve_sudoku.py 启动实时解题台。'); }
  if (!response.ok) throw new Error(result.error || `HTTP ${response.status}`);
  return result;
}
function showError(message = '') { $('error').hidden = !message; $('error').textContent = message; }
function text(id, value) { $(id).textContent = value; }
function units(grid, r, c, kind) {
  const vals = kind === 'row' ? grid[r] : kind === 'col' ? grid.map(row => row[c]) :
    grid.slice(Math.floor(r / 3) * 3, Math.floor(r / 3) * 3 + 3).flatMap(row => row.slice(Math.floor(c / 3) * 3, Math.floor(c / 3) * 3 + 3));
  return [...new Set(vals.filter(Boolean))].sort((a,b) => a-b).join('  ') || '暂无';
}
function render() {
  const unavailable = !game || switching;
  $('caseSelect').disabled = switching;
  $('applyCase').disabled = switching;
  $('reset').disabled = unavailable;
  $('run').disabled = unavailable || !config?.configured || game.done || game.running || game.busy || inFlight || controlling;
  $('pause').disabled = unavailable || (!game.running && !game.busy && !inFlight) || controlling;
  $('singleStep').disabled = unavailable || !config?.configured || game.done || game.running || game.busy || inFlight || controlling;
  if (!game) return;
  const focus = game.next?.cell;
  $('board').replaceChildren();
  game.grid.forEach((row,r) => row.forEach((v,c) => {
    const cell = document.createElement('div'); cell.className = 'cell'; cell.setAttribute('role','gridcell');
    cell.setAttribute('aria-label',`第 ${r+1} 行第 ${c+1} 列，${v || '空白'}`);
    if (c === 2 || c === 5) cell.classList.add('box-c');
    if (r === 2 || r === 5) cell.classList.add('box-r');
    cell.classList.add(game.givens[r][c] ? 'given' : 'filled');
    if (focus && (r === focus[0] || c === focus[1] || (Math.floor(r/3) === Math.floor(focus[0]/3) && Math.floor(c/3) === Math.floor(focus[1]/3)))) cell.classList.add('related');
    if (focus && r === focus[0] && c === focus[1]) cell.classList.add('focus');
    cell.textContent = v || ''; $('board').append(cell);
  }));
  const status = switching ? '正在切换题目' : game.done ? (game.outcome === 'win' ? '本局完成' : '三次失误 · 本局结束') : game.busy || inFlight ? (game.running ? 'Jev 判断中…' : activeSingle && !pauseRequested ? '单步判断中…' : '已暂停 · 等待在途响应，不会落子') : game.running ? '正在运行' : '已暂停';
  text('status', status); $('statusDot').classList.toggle('running',game.running);
  text('caseMeta',`seed ${game.case.seed} · ${game.holes} 空格`);
  text('boardStatus',game.done ? '本局结束' : `已完成 ${game.steps} 次判断`);
  text('filled',`${game.score} / ${game.holes}`); text('mistakes',`${game.mistakes} / 3`); text('stepCount',game.steps);
  $('progress').style.width = `${game.holes ? game.score / game.holes * 100 : 100}%`;
  if (focus) {
    const [r,c] = focus; text('focusCell',`R${r+1} · C${c+1}`);
    $('candidates').replaceChildren();
    for (let d=1; d<=9; d++) {
      const node = document.createElement('span');node.className = 'candidate' + (game.next.candidates.includes(d) ? '' : ' excluded');node.textContent = d;$('candidates').append(node);
    }
    for (const kind of ['row','col','box']) text(kind+'Digits',units(game.grid,r,c,kind));
    text('explain',`当前候选为 {${game.next.candidates.join(', ')}}。代码只整理约束，填入的数字由 Jev 的 Choice 响应决定。`);
  } else {
    text('focusCell',game.outcome === 'win' ? '棋盘已填满' : '本局已终止');$('candidates').replaceChildren();
    ['rowDigits','colDigits','boxDigits'].forEach(id => text(id,'—'));
    text('explain',game.outcome === 'win' ? '所有空格均已通过唯一解校验。可以切换 case 继续观察。' : '模型累计答错三次，本局停止。完整错误响应保留在历史报文中。');
  }
  const latest = game.history.at(-1);
  if (latest) {
    text('lastDecision',latest.error || latest.note || `R${latest.cell[0]+1} C${latest.cell[1]+1} → ${latest.digit} · ${latest.correct ? '正确，已填入' : '错误，未填入'}`);
    const usage = latest.response?.body?.usage;
    text('usage',`${latest.latency_ms} ms · 输入 ${usage?.input_tokens ?? '未知'} token · 输出 ${usage?.output_tokens ?? '未知'} token`);
    if (latest.error) showError(latest.error);
  } else {text('lastDecision','尚无请求');text('usage','—');}
  renderHistory();
}
function packet(p, response = false) {
  if (!p) return response ? '尚未收到 HTTP 响应' : '尚未发起 HTTP 请求';
  const first = response ? `${p.http_version || 'HTTP'} ${p.status}` : `${p.method} ${p.url}`;
  return first + '\n' + p.headers.map(([k,v]) => `${k}: ${v}`).join('\n') + '\n\n' + p.body_text;
}
function renderHistory() {
  const history = game?.history || [];
  if (followLatest && history.length) selectedTrace = history.at(-1).id;
  if (history.length !== lastTraceId) {
    $('history').replaceChildren();
    if (!history.length) {const option = new Option('尚无请求','');$('history').add(option);}
    history.forEach(t => $('history').add(new Option(`#${t.id} · R${t.cell[0]+1} C${t.cell[1]+1} · ${t.error ? '请求失败' : !t.applied ? '未落子' : t.correct ? '正确' : '错误'}`,String(t.id))));
    lastTraceId = history.length;
  }
  const trace = history.find(t => t.id === selectedTrace);
  if (trace) $('history').value = String(trace.id);
  $('history').disabled = !history.length;
  text('requestBody',trace ? packet(trace.request) : '尚未发起请求');
  text('responseBody',trace ? packet(trace.response,true) : '等待 Jev 响应');
  $('copyRequest').disabled = !trace?.request;$('copyResponse').disabled = !trace?.response;$('copyAll').disabled = !trace;
}
async function createGame() {
  const mine = ++version, previous = game?.id;
  switching = true;showError();render();
  const data = {case_id:$('caseSelect').value, previous_game:previous};
  if (data.case_id === 'custom') {data.seed = Number($('seed').value);data.holes = Number($('holes').value);}
  try {
    const result = await api('/api/games',data);
    if (mine !== version) return;
    game = result;selectedTrace = null;followLatest = true;lastTraceId = -1;inFlight = false;
    text('copyStatus','');
  } catch (error) {
    showError(error.message);
    if (game) {game.running = false;try {await api(`/api/games/${game.id}/control`,{action:'pause'});} catch {}}
  } finally {if (mine === version) {switching = false;render();}}
}
async function control(action) {
  if (!game || controlling) return;
  if (action === 'pause') pauseRequested = true;
  const mine = version, id = game.id, driver = ++driveVersion;controlling = true;showError();render();
  try {
    const state = await api(`/api/games/${id}/control`,{action});
    if (mine !== version || game?.id !== id) return;
    game = state;
  } catch (error) {showError(error.message);}
  finally {controlling = false;render();}
  if (action === 'run' && mine === version && game?.running) drive(mine,driver);
}
async function step(mine, single = false) {
  if (!game || inFlight || mine !== version) return;
  const id = game.id;inFlight = true;activeSingle = single;pauseRequested = false;render();
  try {
    const state = await api(`/api/games/${id}/step`,{expected_steps:game.steps,single});
    if (mine === version && game?.id === id) game = state;
  } catch (error) {
    if (mine === version && game?.id === id) {
      showError(error.message);
      try {game = await api(`/api/games/${id}/control`,{action:'pause'});} catch {game.running = false;}
    }
  } finally {if (mine === version) {inFlight = false;activeSingle = false;render();}}
}
async function drive(mine, driver) {
  while (driver === driveVersion && mine === version && game?.running && !game.done && !switching) {
    await step(mine);
    if (mine !== version || !game?.running || game.done) break;
    await new Promise(resolve => setTimeout(resolve,400));
  }
}
async function copyText(kind) {
  const trace = game?.history.find(t => t.id === selectedTrace);if (!trace) return;
  const value = kind === 'request' ? packet(trace.request) : kind === 'response' ? packet(trace.response,true) :
    `#${trace.id} · R${trace.cell[0]+1} C${trace.cell[1]+1}\n\nREQUEST\n${packet(trace.request)}\n\nRESPONSE\n${packet(trace.response,true)}`;
  try {
    if (navigator.clipboard?.writeText) await navigator.clipboard.writeText(value);
    else {
      const area = document.createElement('textarea');area.value = value;area.style.position = 'fixed';area.style.opacity = '0';document.body.append(area);area.select();
      const ok = document.execCommand('copy');area.remove();if (!ok) throw new Error('请手动选择报文复制');
    }
    text('copyStatus',kind === 'request' ? '已复制完整请求' : kind === 'response' ? '已复制完整响应' : '已复制完整请求与响应');
  } catch (error) {text('copyStatus',`复制失败：${error.message}`);}
}
$('run').onclick = () => control('run');$('pause').onclick = () => control('pause');
$('singleStep').onclick = () => {showError();step(version,true);};
$('reset').onclick = createGame;$('applyCase').onclick = createGame;
$('caseSelect').onchange = () => {$('customFields').hidden = $('caseSelect').value !== 'custom';createGame();};
$('history').onchange = () => {selectedTrace = Number($('history').value);followLatest = selectedTrace === game.history.at(-1)?.id;renderHistory();};
$('copyRequest').onclick = () => copyText('request');$('copyResponse').onclick = () => copyText('response');$('copyAll').onclick = () => copyText('all');
(async () => {
  try {
    if (location.protocol === 'file:') throw new Error('请先运行 serve_sudoku.py，再打开 http://127.0.0.1:8803。');
    config = await api('/api/config');text('modelName',config.model);text('endpoint',config.base_url);
    text('serviceBadge',config.configured ? '真实 Jev · 已配置' : '缺少 API Key');
    $('caseSelect').replaceChildren(...config.cases.map(c => new Option(c.title,c.id)),new Option('自定义 seed / 空格数','custom'));
    await createGame();
    if (!config.configured) showError('请在 main/.env 配置 TYPESAFE_API_KEY 后重启服务。');
  } catch (error) {showError(error.message);text('status','服务未就绪');}
})();
