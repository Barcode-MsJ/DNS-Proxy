const $ = (id) => document.getElementById(id);
const api = async (path, options = {}) => {
  const response = await fetch(path, { headers: { 'Content-Type': 'application/json' }, ...options });
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || `HTTP ${response.status}`);
  return data;
};
let toastTimer;
function toast(message) {
  const el = $('toast'); el.textContent = message; el.classList.add('show');
  clearTimeout(toastTimer); toastTimer = setTimeout(() => el.classList.remove('show'), 2600);
}
function esc(value) {
  return String(value ?? '').replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
}
function renderStats(stats) {
  $('stat-total').textContent = stats.Total ?? 0;
  $('stat-ads').textContent = stats.AD_BLOCK ?? 0;
  $('stat-sanctions').textContent = stats.SANCTION ?? 0;
  $('stat-cache').textContent = stats.CACHE ?? 0;
}
function renderResult(result) {
  const card = $('result-card');
  card.className = 'result-card has-result';
  card.innerHTML = `<div class="result-head"><span class="result-domain">${esc(result.domain)}</span><span class="tag ${esc(result.source)}">${esc(result.source)}</span></div>
    <div class="result-grid"><div class="result-cell"><span>وضعیت</span><b>${esc(result.status)}</b></div><div class="result-cell"><span>آدرس IP</span><b>${esc(result.ip)}</b></div><div class="result-cell"><span>TTL</span><b>${esc(result.ttl)}</b></div></div>`;
}
function renderCache(entries) {
  $('cache-count').textContent = `${entries.length} مورد`;
  $('cache-body').innerHTML = entries.length ? entries.map(item => `<tr><td>${esc(item.domain)}</td><td class="mono">${esc(item.ip)}</td><td>${esc(item.ttl)}s</td></tr>`).join('') : '<tr><td colspan="3" class="table-empty">کش خالی است.</td></tr>';
}
function renderLists(lists) {
  $('ads-list-count').textContent = lists.ads.length;
  $('sanctions-list-count').textContent = lists.sanctions.length;
  $('ads-list').innerHTML = lists.ads.length ? lists.ads.map(x => `<li>${esc(x)}</li>`).join('') : '<li>بدون مورد</li>';
  $('sanctions-list').innerHTML = lists.sanctions.length ? lists.sanctions.map(x => `<li>${esc(x)}</li>`).join('') : '<li>بدون مورد</li>';
}
function renderLogs(lines) {
  $('logs-body').innerHTML = lines.length ? lines.slice().reverse().map(line => {
    const p = line.split(' | ');
    if (p.length !== 6) return '';
    return `<tr><td>${esc(p[0])}</td><td>${esc(p[1])}</td><td><span class="source-text ${esc(p[2])}">${esc(p[2])}</span></td><td><span class="status-text ${esc(p[3])}">${esc(p[3])}</span></td><td>${esc(p[4])}</td><td>${esc(p[5])}</td></tr>`;
  }).join('') : '<tr><td colspan="6" class="table-empty">هنوز گزارشی ثبت نشده است.</td></tr>';
}
async function refreshAll() {
  try {
    const [status, stats, cache, logs, lists] = await Promise.all([
      api('/api/status'), api('/api/stats'), api('/api/cache'), api('/api/logs'), api('/api/lists')
    ]);
    renderStats(stats); renderCache(cache.entries); renderLogs(logs.entries); renderLists(lists);
    $('side-status').textContent = 'سرویس فعال است'; $('status-label').textContent = 'آنلاین';
    $('mode-value').textContent = status.mode === 'real-dns' ? 'DNS واقعی' : 'شبیه‌ساز محلی';
    $('upstream-value').textContent = status.upstream;
    $('cache-enabled-value').textContent = status.cache_enabled ? 'فعال' : 'غیرفعال';
    $('local-ttl-value').textContent = `${status.local_ttl}s`;
    $('ad-count-value').textContent = status.lists.ads;
    $('sanction-count-value').textContent = status.lists.sanctions;
  } catch (error) {
    $('side-status').textContent = 'خطا در ارتباط'; $('status-label').textContent = 'عدم دسترسی';
    toast(`خطا: ${error.message}`);
  }
}
$('lookup-form').addEventListener('submit', async (event) => {
  event.preventDefault();
  const domain = $('domain-input').value;
  const button = $('resolve-btn'); button.disabled = true; button.textContent = 'در حال بررسی...';
  try {
    const result = await api('/api/resolve', { method: 'POST', body: JSON.stringify({ domain }) });
    renderResult(result); await refreshAll();
  } catch (error) { toast(`خطا: ${error.message}`); }
  finally { button.disabled = false; button.innerHTML = 'بررسی دامنه <span>←</span>'; }
});
$('reload-btn').addEventListener('click', async () => {
  const button = $('reload-btn'); button.disabled = true;
  try {
    const result = await api('/api/reload', { method: 'POST', body: '{}' });
    $('reload-message').textContent = result.message;
    toast(result.message); await refreshAll();
  } catch (error) { $('reload-message').textContent = error.message; toast(`خطا: ${error.message}`); }
  finally { button.disabled = false; }
});
$('refresh-btn').addEventListener('click', refreshAll);
refreshAll();
