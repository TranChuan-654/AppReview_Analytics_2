// dashboard/script.js

// ═══════════════════════════════════════════
// STATE
// ═══════════════════════════════════════════
const STATE = {
  rawData:      [],
  filteredData: [],
  wcData:       {},
  charts:       {},
  sort:         { col: 'total', dir: -1 },
  page:         1,
  pageSize:     20,
  activeTab:    'tab-overview',
  filterTimer:  null,
  renderTimer:  null,
  filters: {
    banks:      new Set(),
    sentiments: new Set(['Positive', 'Neutral', 'Negative']),
    source:     'All',
    segment:    'All',
    year:       'All',
    quarter:    'All',
    ratingMin:  1,
    ratingMax:  5,
    search:     '',
  },
};

const PALETTE = [
  '#6366f1','#10b981','#f59e0b','#f43f5e','#8b5cf6',
  '#06b6d4','#84cc16','#fb923c','#ec4899','#14b8a6',
];

// ═══════════════════════════════════════════
// KHỞI ĐỘNG
// ═══════════════════════════════════════════
document.addEventListener('DOMContentLoaded', () => {
  initTheme();
  initUpload();
  initTabs();
  initFilters();
  initSortTable();
});

// ═══════════════════════════════════════════
// THEME
// ═══════════════════════════════════════════
function initTheme() {
  const btn = document.getElementById('themeToggleBtn');
  applyTheme(localStorage.getItem('theme') || 'dark');
  btn.addEventListener('click', () => {
    const next = document.body.classList.contains('light-mode') ? 'dark' : 'light';
    applyTheme(next);
    localStorage.setItem('theme', next);
  });
}

function applyTheme(t) {
  document.body.classList.toggle('light-mode', t === 'light');
  document.getElementById('themeToggleBtn').textContent = t === 'light' ? '🌙' : '☀️';
  if (STATE.rawData.length) requestRender();
}

// ═══════════════════════════════════════════
// UPLOAD
// ═══════════════════════════════════════════
function initUpload() {
  const csvInput = document.getElementById('csvFileInput');
  const wcInput  = document.getElementById('wcFileInput');
  const dropZone = document.getElementById('dropZone');

  // Click vào dropzone → mở hộp thoại chọn file
  dropZone.addEventListener('click', () => csvInput.click());

  // Kéo thả file
  dropZone.addEventListener('dragover',  e => { e.preventDefault(); dropZone.classList.add('drag-over'); });
  dropZone.addEventListener('dragleave', () => dropZone.classList.remove('drag-over'));
  dropZone.addEventListener('drop', e => {
    e.preventDefault();
    dropZone.classList.remove('drag-over');
    const file = [...e.dataTransfer.files].find(f => f.name.endsWith('.csv'));
    if (file) parseCSV(file);
    else alert('Vui lòng kéo file .csv vào đây!');
  });

  // Chọn file qua input
  csvInput.addEventListener('change', e => {
    if (e.target.files[0]) parseCSV(e.target.files[0]);
    e.target.value = '';
  });

  // Upload wordcloud JSON
  wcInput.addEventListener('change', e => {
    if (e.target.files[0]) parseWC(e.target.files[0]);
    e.target.value = '';
  });

  // Nút đổi file ở header
  document.getElementById('headerUploadBtn').addEventListener('click', () => csvInput.click());

  // Nút vào workspace (sau khi đã tải file)
  document.getElementById('btnGoWorkspace').addEventListener('click', () => {
    if (STATE.rawData.length) showWorkspace();
  });
  document.getElementById('btnStartAnalysis').addEventListener('click', showWorkspace);
}

// ── Parse CSV (KHÔNG dùng worker vì file:// không hỗ trợ) ──────────────────
function parseCSV(file) {
  const sizeMB = (file.size / 1024 / 1024).toFixed(1);
  showLoading(`Đang đọc file ${file.name} (${sizeMB} MB)...`);

  // Dùng setTimeout để browser kịp render loading overlay trước
  setTimeout(() => {
    Papa.parse(file, {
      header:         true,
      skipEmptyLines: true,
      worker:         false,   // ← PHẢI là false khi mở qua file://
      complete: result => {
        if (!result.data?.length) {
          hideLoading();
          showError('File CSV trống hoặc không đọc được!');
          return;
        }

        // Kiểm tra cột bắt buộc
        const required = ['Tên ngân hàng', 'sentiment', 'Rating', 'Nội dung review'];
        const cols = Object.keys(result.data[0]);
        const missing = required.filter(c => !cols.includes(c));
        if (missing.length) {
          hideLoading();
          showError(`File thiếu cột: ${missing.join(', ')}\n\nHãy chạy "python process.py" trước để tạo file đúng định dạng.`);
          return;
        }

        showLoading(`Đã đọc ${result.data.length.toLocaleString()} dòng, đang xử lý...`);
        setTimeout(() => processData(result.data), 30);
      },
      error: err => {
        hideLoading();
        showError('Lỗi đọc file: ' + err.message);
      },
    });
  }, 50);
}

// ── Parse wordcloud JSON ────────────────────────────────────────────────────
function parseWC(file) {
  const reader = new FileReader();
  reader.onload = e => {
    try {
      STATE.wcData = JSON.parse(e.target.result);

      // Cập nhật UI
      document.getElementById('wcLoadedStatus').textContent = '✅ Đã nạp';
      document.getElementById('wcItem').classList.add('loaded');

      // Thêm ngân hàng vào dropdown word cloud
      const sel = document.getElementById('wcBankSelect');
      const banks = Object.keys(STATE.wcData).filter(k => k !== 'All').sort();
      while (sel.options.length > 1) sel.remove(1);
      banks.forEach(b => sel.appendChild(new Option(b, b)));

      // Nếu đang ở tab word cloud thì render lại
      if (STATE.activeTab === 'tab-journey') renderWordCloud();
    } catch {
      showError('File wordcloud_data.json không hợp lệ!');
    }
  };
  reader.readAsText(file, 'utf-8');
}

// ── Xử lý dữ liệu sau khi parse xong ──────────────────────────────────────
function processData(rows) {
  // Tạo các trường tính toán sẵn để lọc nhanh hơn
  STATE.rawData = rows.map(r => ({
    ...r,
    _rating:   parseFloat(r.Rating)          || 0,
    _year:     String(r['Năm review']        || ''),
    _quarter:  String(r['Quý review']        || ''),
    _monthyr:  String(r['Tháng-năm review']  || ''),
    _bank:     String(r['Tên ngân hàng']     || ''),
    _sent:     String(r.sentiment            || 'Neutral'),
    _source:   String(r['Nguồn review']      || ''),
    _segment:  String(r['Phân khúc KH']      || ''),
    _content:  String(r['Nội dung review']   || '').toLowerCase(),
  }));

  // Lấy giá trị unique để build filter dropdowns
  const banks    = [...new Set(STATE.rawData.map(r => r._bank).filter(Boolean))].sort();
  const sources  = [...new Set(STATE.rawData.map(r => r._source).filter(Boolean))];
  const segments = [...new Set(STATE.rawData.map(r => r._segment).filter(Boolean))];
  const years    = [...new Set(STATE.rawData.map(r => r._year).filter(Boolean))].sort();

  STATE.filters.banks = new Set(banks);

  buildBankCheckboxes(banks);
  buildSelectOptions('filterSource',  sources);
  buildSelectOptions('filterSegment', segments);
  buildSelectOptions('filterYear',    years);

  // Thêm ngân hàng vào dropdown word cloud
  const wcSel = document.getElementById('wcBankSelect');
  while (wcSel.options.length > 1) wcSel.remove(1);
  banks.forEach(b => wcSel.appendChild(new Option(b, b)));

  // Cập nhật UI trạng thái
  const n = STATE.rawData.length;
  document.getElementById('csvLoadedStatus').textContent = `✅ ${n.toLocaleString()} dòng`;
  document.getElementById('csvItem').classList.add('loaded');
  document.getElementById('btnGoWorkspace').disabled = false;
  document.getElementById('btnGoWorkspace').classList.replace('btn-ghost', 'btn-primary');
  document.getElementById('btnStartAnalysis').style.display = 'inline-flex';

  hideLoading();
  applyFilters();
  showWorkspace();
}

// ═══════════════════════════════════════════
// CHUYỂN MÀN HÌNH
// ═══════════════════════════════════════════
function showWorkspace() {
  document.getElementById('welcomeScreen').style.display = 'none';
  document.getElementById('workspace').style.display     = 'flex';
  document.getElementById('headerUploadBtn').style.display = 'inline-flex';
  updateStatusBadge();
  renderActiveTab();
}

// ═══════════════════════════════════════════
// BỘ LỌC
// ═══════════════════════════════════════════
function initFilters() {
  // Chọn / bỏ tất cả ngân hàng
  document.getElementById('btnSelectAllBanks').addEventListener('click', () => {
    const banks = [...new Set(STATE.rawData.map(r => r._bank).filter(Boolean))];
    STATE.filters.banks = new Set(banks);
    document.querySelectorAll('.bank-cb').forEach(cb => (cb.checked = true));
    scheduleFilter();
  });
  document.getElementById('btnClearAllBanks').addEventListener('click', () => {
    STATE.filters.banks = new Set();
    document.querySelectorAll('.bank-cb').forEach(cb => (cb.checked = false));
    scheduleFilter();
  });

  // Sentiment toggle
  document.querySelectorAll('.sent-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const s = btn.dataset.sentiment;
      if (STATE.filters.sentiments.has(s)) STATE.filters.sentiments.delete(s);
      else                                 STATE.filters.sentiments.add(s);
      btn.classList.toggle('inactive');
      scheduleFilter(100);
    });
  });

  // Dropdowns
  ['filterSource', 'filterSegment', 'filterYear', 'filterQuarter',
   'filterRatingMin', 'filterRatingMax'].forEach(id => {
    document.getElementById(id)?.addEventListener('change', () => {
      readSelectFilters();
      scheduleFilter(100);
    });
  });

  // Tìm kiếm (debounce dài hơn)
  document.getElementById('filterSearch').addEventListener('input', e => {
    STATE.filters.search = e.target.value.toLowerCase().trim();
    scheduleFilter(350);
  });

  // Reset
  document.getElementById('btnResetFilters').addEventListener('click', resetFilters);

  // Word cloud selectors
  document.getElementById('wcBankSelect').addEventListener('change', renderWordCloud);
  document.getElementById('wcSegSelect').addEventListener('change',  renderWordCloud);
}

function scheduleFilter(delay = 150) {
  clearTimeout(STATE.filterTimer);
  STATE.filterTimer = setTimeout(applyFilters, delay);
}

function readSelectFilters() {
  const get = id => document.getElementById(id)?.value || 'All';
  STATE.filters.source    = get('filterSource');
  STATE.filters.segment   = get('filterSegment');
  STATE.filters.year      = get('filterYear');
  STATE.filters.quarter   = get('filterQuarter');
  STATE.filters.ratingMin = parseInt(document.getElementById('filterRatingMin').value) || 1;
  STATE.filters.ratingMax = parseInt(document.getElementById('filterRatingMax').value) || 5;
}

function applyFilters() {
  const f = STATE.filters;
  STATE.filteredData = STATE.rawData.filter(r => {
    if (!f.banks.has(r._bank))                                      return false;
    if (!f.sentiments.has(r._sent))                                 return false;
    if (f.source  !== 'All' && r._source  !== f.source)            return false;
    if (f.segment !== 'All' && r._segment !== f.segment)           return false;
    if (f.year    !== 'All' && r._year    !== f.year)              return false;
    if (f.quarter !== 'All' && r._quarter !== f.quarter)           return false;
    if (r._rating < f.ratingMin || r._rating > f.ratingMax)        return false;
    if (f.search && !r._content.includes(f.search)
        && !r._bank.toLowerCase().includes(f.search))              return false;
    return true;
  });
  STATE.page = 1;
  updateStatusBadge();
  requestRender();
}

function resetFilters() {
  const banks = [...new Set(STATE.rawData.map(r => r._bank).filter(Boolean))];
  STATE.filters = {
    banks: new Set(banks),
    sentiments: new Set(['Positive', 'Neutral', 'Negative']),
    source: 'All', segment: 'All', year: 'All', quarter: 'All',
    ratingMin: 1, ratingMax: 5, search: '',
  };
  document.querySelectorAll('.bank-cb').forEach(cb => (cb.checked = true));
  document.querySelectorAll('.sent-btn').forEach(btn => btn.classList.remove('inactive'));
  ['filterSource','filterSegment','filterYear','filterQuarter'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.value = 'All';
  });
  document.getElementById('filterRatingMin').value = '1';
  document.getElementById('filterRatingMax').value = '5';
  document.getElementById('filterSearch').value    = '';
  STATE.filters.search = '';
  scheduleFilter(0);
}

function buildBankCheckboxes(banks) {
  const container = document.getElementById('bankCheckboxContainer');
  const frag = document.createDocumentFragment();
  banks.forEach(bank => {
    const label = document.createElement('label');
    label.className = 'bank-checkbox-item';
    const cb = document.createElement('input');
    cb.type = 'checkbox'; cb.className = 'bank-cb'; cb.value = bank; cb.checked = true;
    cb.addEventListener('change', e => {
      if (e.target.checked) STATE.filters.banks.add(bank);
      else                   STATE.filters.banks.delete(bank);
      scheduleFilter(100);
    });
    const span = document.createElement('span');
    span.textContent = bank; span.style.fontSize = '12px';
    label.append(cb, span);
    frag.appendChild(label);
  });
  container.innerHTML = '';
  container.appendChild(frag);
}

function buildSelectOptions(id, values) {
  const sel = document.getElementById(id);
  if (!sel) return;
  // Giữ option "Tất cả" đầu tiên, xóa phần còn lại rồi thêm mới
  while (sel.options.length > 1) sel.remove(1);
  values.forEach(v => { if (v) sel.appendChild(new Option(v, v)); });
}

// ═══════════════════════════════════════════
// TABS
// ═══════════════════════════════════════════
function initTabs() {
  document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      STATE.activeTab = btn.dataset.tab;
      document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      document.querySelectorAll('.tab-pane').forEach(p => p.classList.add('hidden'));
      document.getElementById(STATE.activeTab)?.classList.remove('hidden');
      requestRender();
    });
  });
}

function requestRender() {
  cancelAnimationFrame(STATE.renderTimer);
  STATE.renderTimer = requestAnimationFrame(renderActiveTab);
}

function renderActiveTab() {
  if (!STATE.rawData.length) return;
  switch (STATE.activeTab) {
    case 'tab-overview': renderOverview(); break;
    case 'tab-trends':   renderTrends();   break;
    case 'tab-journey':  renderJourney();  break;
    case 'tab-reviews':  renderReviews();  break;
  }
}

function updateStatusBadge() {
  const el = document.getElementById('statusValue');
  if (el) el.textContent = `${STATE.filteredData.length.toLocaleString()} / ${STATE.rawData.length.toLocaleString()}`;
}

// ═══════════════════════════════════════════
// OVERVIEW
// ═══════════════════════════════════════════
function renderOverview() {
  const data  = STATE.filteredData;
  const total = data.length;

  let pos = 0, neg = 0, neu = 0, rSum = 0;
  data.forEach(r => {
    if      (r._sent === 'Positive') pos++;
    else if (r._sent === 'Negative') neg++;
    else                             neu++;
    rSum += r._rating;
  });

  setKPI('kpiTotal',  total.toLocaleString(), 'sau bộ lọc');
  setKPI('kpiPos',    pct(pos, total) + '%',  `${pos.toLocaleString()} reviews`);
  setKPI('kpiNeg',    pct(neg, total) + '%',  `${neg.toLocaleString()} reviews`);
  setKPI('kpiRating', total ? (rSum / total).toFixed(2) + '⭐' : '0⭐', 'trung bình');

  renderBankTable(data);

  // Biểu đồ cảm xúc
  renderChart('chartSentiment', 'doughnut', {
    labels: ['Tích cực', 'Trung lập', 'Tiêu cực'],
    datasets: [{
      data: [pos, neu, neg],
      backgroundColor: ['#10b981', '#f59e0b', '#f43f5e'],
      borderWidth: 0, hoverOffset: 6,
    }],
  }, { cutout: '65%', plugins: { legend: { position: 'right' } } });

  // Biểu đồ rating
  const rCounts = [0, 0, 0, 0, 0];
  data.forEach(r => {
    const i = Math.round(r._rating) - 1;
    if (i >= 0 && i < 5) rCounts[i]++;
  });
  renderChart('chartRating', 'bar', {
    labels: ['1⭐', '2⭐', '3⭐', '4⭐', '5⭐'],
    datasets: [{
      label: 'Số review', data: rCounts,
      backgroundColor: ['#f43f5e', '#f97316', '#f59e0b', '#10b981', '#6366f1'],
      borderRadius: 6, borderWidth: 0,
    }],
  }, { scales: { y: { beginAtZero: true } } });
}

function setKPI(id, value, sub) {
  const el = document.getElementById(id);
  if (!el) return;
  const vEl = el.querySelector('.kpi-value');
  const sEl = el.querySelector('.kpi-sub');
  if (vEl) vEl.textContent = value;
  if (sEl && sub) sEl.textContent = sub;
}

// ── Bảng so sánh ngân hàng ─────────────────────────────────────────────────
function renderBankTable(data) {
  const tbody = document.getElementById('bankTableBody');
  if (!tbody) return;

  const map = new Map();
  data.forEach(r => {
    const b = r._bank; if (!b) return;
    if (!map.has(b)) map.set(b, { bank: b, total: 0, pos: 0, neg: 0, rSum: 0 });
    const m = map.get(b);
    m.total++;
    if      (r._sent === 'Positive') m.pos++;
    else if (r._sent === 'Negative') m.neg++;
    m.rSum += r._rating;
  });

  let rows = [...map.values()].map(b => ({
    ...b,
    avgRating: b.total ? (b.rSum / b.total).toFixed(2) : '0',
    posP: pct(b.pos, b.total),
    negP: pct(b.neg, b.total),
    nps:  pct(b.pos, b.total) - pct(b.neg, b.total),
  }));

  const { col, dir } = STATE.sort;
  rows.sort((a, z) => {
    const av = a[col], bv = z[col];
    return typeof av === 'string' ? dir * av.localeCompare(bv) : dir * (av - bv);
  });

  tbody.innerHTML = rows.map(b => `
    <tr>
      <td><strong>${b.bank}</strong></td>
      <td style="text-align:center">${b.total.toLocaleString()}</td>
      <td style="text-align:center">${b.avgRating} ⭐</td>
      <td style="text-align:center;color:var(--pos)"><strong>${b.posP}%</strong></td>
      <td style="text-align:center;color:var(--neg)"><strong>${b.negP}%</strong></td>
      <td style="text-align:center">
        <span class="nps-pill ${b.nps>=30?'excellent':b.nps>=0?'good':b.nps>=-20?'poor':'bad'}">
          ${b.nps > 0 ? '+' : ''}${b.nps}
        </span>
      </td>
      <td>
        <div class="mini-bar-wrap">
          <div class="mini-bar">
            <div class="mini-bar-fill" style="width:${b.posP}%;background:var(--pos)"></div>
          </div>
          <span style="font-size:10px;color:var(--text-muted)">${b.posP}%</span>
        </div>
      </td>
    </tr>`).join('');
}

function initSortTable() {
  document.addEventListener('click', e => {
    const th = e.target.closest('.sort-th');
    if (!th) return;
    const c = th.dataset.col;
    STATE.sort = { col: c, dir: STATE.sort.col === c ? -STATE.sort.dir : -1 };
    renderBankTable(STATE.filteredData);
  });
}

// ═══════════════════════════════════════════
// TRENDS
// ═══════════════════════════════════════════
function renderTrends() {
  const data = STATE.filteredData;
  const monthMap = new Map();
  const issueMap = new Map();
  const prodMap  = new Map();

  data.forEach(r => {
    // Theo tháng
    const m = r._monthyr;
    if (m) {
      if (!monthMap.has(m)) monthMap.set(m, { pos: 0, neg: 0, neu: 0 });
      const mm = monthMap.get(m);
      if      (r._sent === 'Positive') mm.pos++;
      else if (r._sent === 'Negative') mm.neg++;
      else                             mm.neu++;
    }
    // Vấn đề lỗi
    const v = r['Vấn đề lỗi 1'];
    if (v && v !== 'Không có lỗi' && v !== 'Không')
      issueMap.set(v, (issueMap.get(v) || 0) + 1);
    // Sản phẩm
    const p = r['Sản phẩm 1'];
    if (p && p !== 'Khác')
      prodMap.set(p, (prodMap.get(p) || 0) + 1);
  });

  const months = [...monthMap.keys()].sort();
  renderChart('chartMonthly', 'line', {
    labels: months,
    datasets: [
      { label: 'Tích cực', data: months.map(m => monthMap.get(m).pos), borderColor: '#10b981', backgroundColor: 'rgba(16,185,129,0.1)', tension: 0.4, fill: true },
      { label: 'Tiêu cực', data: months.map(m => monthMap.get(m).neg), borderColor: '#f43f5e', backgroundColor: 'rgba(244,63,94,0.1)',  tension: 0.4, fill: true },
      { label: 'Trung lập', data: months.map(m => monthMap.get(m).neu), borderColor: '#f59e0b', tension: 0.4 },
    ],
  }, { scales: { y: { beginAtZero: true } } });

  const topIssues = [...issueMap.entries()].sort((a, b) => b[1] - a[1]).slice(0, 10);
  renderChart('chartIssues', 'bar', {
    labels: topIssues.map(([k]) => k),
    datasets: [{ label: 'Số lượng', data: topIssues.map(([, v]) => v), backgroundColor: 'rgba(244,63,94,0.75)', borderRadius: 6, borderWidth: 0 }],
  }, { indexAxis: 'y', scales: { x: { beginAtZero: true } } });

  const topProds = [...prodMap.entries()].sort((a, b) => b[1] - a[1]).slice(0, 8);
  renderChart('chartProducts', 'bar', {
    labels: topProds.map(([k]) => k),
    datasets: [{ label: 'Số lượng', data: topProds.map(([, v]) => v), backgroundColor: 'rgba(99,102,241,0.75)', borderRadius: 6, borderWidth: 0 }],
  }, { indexAxis: 'y', scales: { x: { beginAtZero: true } } });
}

// ═══════════════════════════════════════════
// JOURNEY — WORD CLOUD
// ═══════════════════════════════════════════
function renderJourney() {
  renderWordCloud();
  renderProductBankChart();
}

function renderWordCloud() {
  const container = document.getElementById('wordCloudContainer');
  if (!container) return;

  const wcBank = document.getElementById('wcBankSelect')?.value || 'All';
  const wcSeg  = document.getElementById('wcSegSelect')?.value  || 'all';

  let words = [];
  if (Object.keys(STATE.wcData).length) {
    const bankData = STATE.wcData[wcBank] || STATE.wcData['All'] || {};
    words = bankData[wcSeg] || bankData['all'] || [];
  } else {
    words = computeWordFreq(STATE.filteredData);
  }

  if (!words.length) {
    container.innerHTML = `<div class="empty-state">
      <div class="empty-icon">☁️</div>
      <div class="empty-text">Không có dữ liệu word cloud.<br>
      Hãy upload thêm file <strong>wordcloud_data.json</strong></div>
    </div>`;
    return;
  }

  const top    = words.slice(0, 80);
  const maxVal = top[0]?.value || 1;
  const minVal = top[top.length - 1]?.value || 1;
  const range  = maxVal - minVal || 1;

  const frag = document.createDocumentFragment();
  top.forEach(w => {
    const ratio = (w.value - minVal) / range;
    const size  = 10 + Math.round(ratio * 30);
    const cls   = w.sentiment === 'Positive' ? 'wc-pos' : w.sentiment === 'Negative' ? 'wc-neg' : 'wc-neu';
    const span  = document.createElement('span');
    span.className = `wc-word ${cls}`;
    span.style.fontSize = size + 'px';
    span.title = `${w.text}: ${w.value.toLocaleString()} lần`;
    span.textContent = w.text;
    frag.appendChild(span);
  });
  container.innerHTML = '';
  container.appendChild(frag);
}

function computeWordFreq(data) {
  const freq = new Map();
  const stop = new Set(['và','của','được','cho','với','trong','các','những','là','có',
    'đã','đang','này','tôi','bạn','từ','vào','như','mà','app','ứng','dụng']);
  data.forEach(r => {
    r._content.split(/\s+/).forEach(w => {
      if (w.length < 3 || stop.has(w)) return;
      const e = freq.get(w);
      if (e) e.value++;
      else   freq.set(w, { text: w, value: 1, sentiment: r._sent });
    });
  });
  return [...freq.values()].sort((a, b) => b.value - a.value).slice(0, 80);
}

function renderProductBankChart() {
  const data  = STATE.filteredData;
  const banks = [...new Set(data.map(r => r._bank).filter(Boolean))].sort();

  const prodBankMap = new Map();
  data.forEach(r => {
    const p = r['Sản phẩm 1'];
    if (!p || p === 'Khác') return;
    if (!prodBankMap.has(p)) prodBankMap.set(p, new Map());
    const bm = prodBankMap.get(p);
    bm.set(r._bank, (bm.get(r._bank) || 0) + 1);
  });

  const prods = [...prodBankMap.entries()]
    .sort((a, b) => {
      const sa = [...a[1].values()].reduce((x, y) => x + y, 0);
      const sb = [...b[1].values()].reduce((x, y) => x + y, 0);
      return sb - sa;
    })
    .slice(0, 8)
    .map(([k]) => k);

  renderChart('chartProdBank', 'bar', {
    labels: banks,
    datasets: prods.map((prod, i) => ({
      label: prod,
      data: banks.map(b => prodBankMap.get(prod)?.get(b) || 0),
      backgroundColor: PALETTE[i % PALETTE.length],
      borderRadius: 4, borderWidth: 0,
    })),
  }, { scales: { x: { stacked: true }, y: { stacked: true, beginAtZero: true } } });
}

// ═══════════════════════════════════════════
// REVIEWS
// ═══════════════════════════════════════════
function renderReviews() {
  const data  = STATE.filteredData;
  const total = data.length;
  const start = (STATE.page - 1) * STATE.pageSize;
  const page  = data.slice(start, start + STATE.pageSize);

  const container = document.getElementById('reviewList');
  if (!container) return;

  if (!page.length) {
    container.innerHTML = `<div class="empty-state">
      <div class="empty-icon">💬</div>
      <div class="empty-text">Không có review nào khớp bộ lọc.</div>
    </div>`;
  } else {
    const html = page.map(r => {
      const stars   = '⭐'.repeat(Math.min(5, Math.max(1, Math.round(r._rating))));
      const sentCls = r._sent === 'Positive' ? 'badge-pos' : r._sent === 'Negative' ? 'badge-neg' : 'badge-neu';
      const sentLbl = r._sent === 'Positive' ? '😊 Tích cực' : r._sent === 'Negative' ? '😞 Tiêu cực' : '😐 Trung lập';
      const content = String(r['Nội dung review'] || '').substring(0, 300);
      const issue   = r['Vấn đề lỗi 1'];
      return `<div class="review-item">
        <div class="review-meta">
          <span class="review-bank">${r._bank} · ${r['Tên app'] || ''}</span>
          <span class="badge ${sentCls}">${sentLbl}</span>
          <span class="review-stars">${stars}</span>
          <span class="review-time">${String(r['Thời gian review'] || '').substring(0, 10)}</span>
        </div>
        <div class="review-text">${content}${content.length === 300 ? '…' : ''}</div>
        ${issue && issue !== 'Không có lỗi' && issue !== 'Không'
          ? `<div style="margin-top:6px"><span style="font-size:10px;color:var(--neg)">🔴 ${issue}</span></div>`
          : ''}
      </div>`;
    });
    container.innerHTML = html.join('');
  }

  const reviewCountEl = document.getElementById('reviewCount');
  if (reviewCountEl) reviewCountEl.textContent = `${total.toLocaleString()} reviews`;
  renderPagination(Math.ceil(total / STATE.pageSize));
}

function renderPagination(totalPages) {
  const el = document.getElementById('pagination');
  if (!el) return;
  if (totalPages <= 1) { el.innerHTML = ''; return; }

  const p = STATE.page;
  const pages = [];
  if (totalPages <= 7) {
    for (let i = 1; i <= totalPages; i++) pages.push(i);
  } else {
    pages.push(1);
    if (p > 3) pages.push('…');
    for (let i = Math.max(2, p - 1); i <= Math.min(totalPages - 1, p + 1); i++) pages.push(i);
    if (p < totalPages - 2) pages.push('…');
    pages.push(totalPages);
  }

  const html = [`<button class="page-btn" onclick="goPage(${p - 1})" ${p <= 1 ? 'disabled' : ''}>‹</button>`];
  pages.forEach(pg => {
    html.push(pg === '…'
      ? `<span style="padding:0 4px;color:var(--text-muted)">…</span>`
      : `<button class="page-btn ${pg === p ? 'active' : ''}" onclick="goPage(${pg})">${pg}</button>`);
  });
  html.push(`<button class="page-btn" onclick="goPage(${p + 1})" ${p >= totalPages ? 'disabled' : ''}>›</button>`);
  el.innerHTML = html.join('');
}

function goPage(p) {
  const total = Math.ceil(STATE.filteredData.length / STATE.pageSize);
  STATE.page = Math.max(1, Math.min(total, p));
  renderReviews();
}

// ═══════════════════════════════════════════
// BIỂU ĐỒ
// ═══════════════════════════════════════════
function renderChart(id, type, data, opts = {}) {
  const canvas = document.getElementById(id);
  if (!canvas) return;

  const dark      = !document.body.classList.contains('light-mode');
  const textColor = dark ? '#94a3b8' : '#475569';
  const gridColor = dark ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.06)';

  const baseOpts = {
    responsive: true,
    maintainAspectRatio: false,
    animation: { duration: 250 },
    plugins: {
      legend: { labels: { color: textColor, font: { family: 'Inter', size: 11 }, boxWidth: 12 } },
      tooltip: {
        backgroundColor: dark ? '#1e293b' : '#fff',
        titleColor: textColor, bodyColor: textColor,
        borderColor: gridColor, borderWidth: 1, padding: 10,
      },
    },
    ...(type !== 'doughnut' && type !== 'pie' ? {
      scales: {
        x: { ticks: { color: textColor, font: { size: 10 } }, grid: { color: gridColor } },
        y: { ticks: { color: textColor, font: { size: 10 } }, grid: { color: gridColor } },
      },
    } : {}),
  };

  const merged = deepMerge(baseOpts, opts);

  // Tái sử dụng chart instance nếu cùng type → không destroy
  if (STATE.charts[id] && STATE.charts[id].config.type === type) {
    STATE.charts[id].data    = data;
    STATE.charts[id].options = merged;
    STATE.charts[id].update('none');
    return;
  }

  STATE.charts[id]?.destroy();
  STATE.charts[id] = new Chart(canvas, { type, data, options: merged });
}

function deepMerge(t, s) {
  const out = { ...t };
  for (const k in s) {
    if (s[k] && typeof s[k] === 'object' && !Array.isArray(s[k])) {
      out[k] = deepMerge(t[k] || {}, s[k]);
    } else {
      out[k] = s[k];
    }
  }
  return out;
}

// ═══════════════════════════════════════════
// LOADING & ERROR
// ═══════════════════════════════════════════
function showLoading(msg = 'Đang xử lý...') {
  document.getElementById('loadingMsg').textContent = msg;
  document.getElementById('loadingOverlay').classList.remove('hidden');
}
function hideLoading() {
  document.getElementById('loadingOverlay').classList.add('hidden');
}
function showError(msg) {
  alert(msg);
}

// ═══════════════════════════════════════════
// UTILS
// ═══════════════════════════════════════════
function pct(num, total) {
  return total ? Math.round((num / total) * 100) : 0;
}
