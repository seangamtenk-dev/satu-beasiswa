let applications = [];
let currentFilter = 'all';

async function request(url, options = {}) {
  const response = await fetch(url, { ...options, credentials: 'same-origin', headers: { 'Content-Type': 'application/json', ...(options.headers || {}) } });
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || 'Permintaan gagal.');
  return data;
}

function esc(value) {
  return String(value ?? '').replace(/[&<>"']/g, char => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[char]);
}

const loginPanel = document.querySelector('#loginPanel');
const dashboard = document.querySelector('#dashboard');
const loginForm = document.querySelector('#loginForm');
const loginMessage = document.querySelector('#loginMessage');

function showDashboard() {
  loginPanel.hidden = true;
  dashboard.hidden = false;
  loadApplications();
}

async function checkSession() {
  try { await request('/api/admin/me'); showDashboard(); }
  catch { loginPanel.hidden = false; dashboard.hidden = true; }
}

loginForm.addEventListener('submit', async event => {
  event.preventDefault();
  loginMessage.className = 'admin-message';
  loginMessage.textContent = 'Memeriksa akun…';
  const values = Object.fromEntries(new FormData(loginForm));
  try {
    await request('/api/admin/login', { method: 'POST', body: JSON.stringify(values) });
    loginForm.reset();
    showDashboard();
  } catch (error) {
    loginMessage.classList.add('error');
    loginMessage.textContent = error.message;
  }
});

document.querySelector('#logoutButton').addEventListener('click', async () => {
  try { await request('/api/admin/logout', { method: 'POST', body: '{}' }); } finally { loginPanel.hidden = false; dashboard.hidden = true; }
});
document.querySelector('#refreshButton').addEventListener('click', loadApplications);
document.querySelector('#adminSearch').addEventListener('input', renderApplications);
document.querySelectorAll('.admin-tab').forEach(tab => tab.addEventListener('click', () => {
  document.querySelectorAll('.admin-tab').forEach(item => item.classList.remove('active'));
  tab.classList.add('active');
  currentFilter = tab.dataset.status;
  renderApplications();
}));

async function loadApplications() {
  const message = document.querySelector('#dashboardMessage');
  message.textContent = 'Memuat daftar pendaftar…';
  try {
    const data = await request('/api/admin/applications');
    applications = data.applications;
    message.textContent = '';
    document.querySelector('#totalCount').textContent = applications.length;
    document.querySelector('#pendingCount').textContent = applications.filter(a => a.status === 'submitted').length;
    document.querySelector('#acceptedCount').textContent = applications.filter(a => a.status === 'accepted').length;
    document.querySelector('#rejectedCount').textContent = applications.filter(a => a.status === 'rejected').length;
    renderApplications();
  } catch (error) {
    message.classList.add('error');
    message.textContent = error.message;
    if (error.message.includes('admin')) checkSession();
  }
}

function renderApplications() {
  const query = document.querySelector('#adminSearch').value.trim().toLowerCase();
  const rows = applications.filter(a => (currentFilter === 'all' || a.status === currentFilter) && `${a.full_name} ${a.email} ${a.scholarship_name} ${a.institution}`.toLowerCase().includes(query));
  document.querySelector('#emptyState').hidden = rows.length > 0;
  document.querySelector('#applicationsList').innerHTML = rows.map(a => {
    const decision = a.status === 'submitted';
    const statusClass = a.status === 'accepted' ? 'accepted' : a.status === 'rejected' ? 'rejected' : 'pending';
    const statusText = a.status === 'accepted' ? 'Diterima' : a.status === 'rejected' ? 'Ditolak' : 'Perlu ditinjau';
    return `<article class="application-record" data-id="${a.id}"><div class="record-head"><div><span class="record-scholarship">${esc(a.scholarship_name)}</span><span class="record-status ${statusClass}">${statusText}</span></div><small>#${a.id} · ${esc(a.created_at)}</small></div><div class="record-profile"><div><b>${esc(a.full_name)}</b><a href="mailto:${esc(a.email)}">${esc(a.email)}</a><span>${esc(a.phone || 'Nomor telepon tidak dicantumkan')}</span></div><div><b>${esc(a.degree_level)} · ${esc(a.institution)}</b><span>Status: ${statusText}</span>${a.reviewed_at ? `<span>Ditinjau: ${esc(a.reviewed_at)}</span>` : ''}</div></div><details class="motivation-details"><summary>Baca motivasi dan rencana studi</summary><p>${esc(a.motivation)}</p></details>${a.reviewer_note ? `<div class="reviewer-note"><b>Catatan keputusan:</b> ${esc(a.reviewer_note)}</div>` : ''}${decision ? `<div class="review-controls"><label>Catatan untuk pendaftar <span>(opsional)</span><textarea class="review-note-input" maxlength="1000" rows="2" placeholder="Misalnya: alasan keputusan atau langkah berikutnya"></textarea></label><div><button class="button button-accept" data-decision="accepted">Terima</button><button class="button button-reject" data-decision="rejected">Tolak</button></div></div>` : ''}</article>`;
  }).join('');
  document.querySelectorAll('[data-decision]').forEach(button => button.addEventListener('click', decide));
}

async function decide(event) {
  const button = event.currentTarget;
  const record = button.closest('.application-record');
  const status = button.dataset.decision;
  const label = status === 'accepted' ? 'menerima' : 'menolak';
  if (!window.confirm(`Yakin ingin ${label} pendaftar ini?`)) return;
  const reviewer_note = record.querySelector('.review-note-input').value.trim();
  record.querySelectorAll('button').forEach(item => item.disabled = true);
  try {
    await request(`/api/admin/applications/${record.dataset.id}`, { method: 'PATCH', body: JSON.stringify({ status, reviewer_note }) });
    await loadApplications();
  } catch (error) {
    document.querySelector('#dashboardMessage').textContent = error.message;
    document.querySelector('#dashboardMessage').classList.add('error');
    record.querySelectorAll('button').forEach(item => item.disabled = false);
  }
}

checkSession();

