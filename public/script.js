const cards = [...document.querySelectorAll('.scholarship-card')];
const search = document.querySelector('#search');
const chips = [...document.querySelectorAll('.filter-chip')];
let activeFilter = 'Semua';

async function api(url, options = {}) {
  const response = await fetch(url, { ...options, headers: { 'Content-Type': 'application/json', ...(options.headers || {}) } });
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || 'Permintaan belum berhasil.');
  return data;
}

function filterCards() {
  const query = search.value.trim().toLowerCase();
  let visible = 0;
  cards.forEach(card => {
    const matchesText = card.innerText.toLowerCase().includes(query);
    const matchesFilter = activeFilter === 'Semua' || card.dataset.location === activeFilter || card.dataset.degree.split(',').includes(activeFilter);
    card.hidden = !(matchesText && matchesFilter);
    if (!card.hidden) visible++;
  });
  document.querySelector('#noResults').style.display = visible ? 'none' : 'block';
}

search.addEventListener('input', filterCards);
document.querySelector('#searchButton').addEventListener('click', filterCards);
chips.forEach(chip => chip.addEventListener('click', () => {
  chips.forEach(item => item.classList.remove('active'));
  chip.classList.add('active');
  activeFilter = chip.dataset.filter;
  filterCards();
}));

document.querySelectorAll('.bookmark').forEach(button => button.addEventListener('click', () => {
  button.classList.toggle('saved');
  button.textContent = button.classList.contains('saved') ? '♥' : '♡';
}));

const menuButton = document.querySelector('.menu-toggle');
menuButton.addEventListener('click', () => {
  const open = document.querySelector('.nav').classList.toggle('open');
  menuButton.setAttribute('aria-expanded', String(open));
  menuButton.textContent = open ? '×' : '☰';
});
document.querySelectorAll('.nav a').forEach(link => link.addEventListener('click', () => {
  document.querySelector('.nav').classList.remove('open');
  menuButton.setAttribute('aria-expanded', 'false');
  menuButton.textContent = '☰';
}));

const scholarshipSelect = document.querySelector('#applicationScholarship');
api('/api/scholarships').then(({ scholarships }) => {
  scholarshipSelect.replaceChildren(new Option('Pilih beasiswa', ''));
  scholarships.forEach(item => scholarshipSelect.add(new Option(`${item.name} · ${item.country}`, item.id)));
}).catch(() => {
  scholarshipSelect.replaceChildren(new Option('Jalankan server untuk memuat beasiswa', ''));
});

document.querySelector('#applicationForm').addEventListener('submit', async event => {
  event.preventDefault();
  const form = event.currentTarget;
  const button = form.querySelector('button[type="submit"]');
  const message = document.querySelector('#applicationMessage');
  const result = document.querySelector('#trackingResult');
  message.className = 'form-message';
  message.textContent = 'Mengirim pendaftaran…';
  result.hidden = true;
  button.disabled = true;
  const values = Object.fromEntries(new FormData(form));
  values.scholarship_id = Number(values.scholarship_id);
  try {
    const data = await api('/api/applications', { method: 'POST', body: JSON.stringify(values) });
    message.textContent = data.message;
    result.innerHTML = `<b>Simpan kode pelacakan ini:</b><br><strong>${data.tracking_code}</strong><br>Gunakan kode dan email pendaftaran untuk memantau status. Kode tidak ditampilkan kembali setelah halaman ditutup.`;
    result.hidden = false;
    form.reset();
  } catch (error) {
    message.classList.add('error');
    message.textContent = error.message;
  } finally {
    button.disabled = false;
  }
});

document.querySelector('#trackingForm').addEventListener('submit', async event => {
  event.preventDefault();
  const values = Object.fromEntries(new FormData(event.currentTarget));
  const message = document.querySelector('#trackingMessage');
  const card = document.querySelector('#trackingCard');
  message.className = 'form-message';
  message.textContent = 'Memeriksa status…';
  card.hidden = true;
  try {
    const query = new URLSearchParams({ code: values.tracking_code, email: values.email });
    const { application } = await api(`/api/track?${query}`);
    const statusClass = application.status === 'accepted' ? 'accepted' : application.status === 'rejected' ? 'rejected' : '';
    card.innerHTML = `<h4>${escapeHtml(application.scholarship_name)}</h4><p>Pendaftar: ${escapeHtml(application.full_name)}</p><span class="status-pill ${statusClass}">${escapeHtml(application.status_label)}</span><p>${application.reviewer_note ? `Catatan admin: ${escapeHtml(application.reviewer_note)}` : 'Admin akan memperbarui status setelah pemeriksaan.'}</p><small>Diperbarui: ${escapeHtml(application.updated_at)}</small>`;
    card.hidden = false;
    message.textContent = '';
  } catch (error) {
    message.classList.add('error');
    message.textContent = error.message;
  }
});

document.querySelector('#newsletterForm').addEventListener('submit', async event => {
  event.preventDefault();
  const form = event.currentTarget;
  const message = document.querySelector('#formMessage');
  message.textContent = 'Menyimpan…';
  try {
    const data = await api('/api/newsletter', { method: 'POST', body: JSON.stringify({ email: form.querySelector('#email').value }) });
    message.textContent = data.message;
    form.reset();
  } catch (error) {
    message.textContent = error.message === 'Failed to fetch' ? 'Jalankan server agar langganan dapat disimpan.' : error.message;
  }
});

function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>"']/g, char => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[char]);
}

