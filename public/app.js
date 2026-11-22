const NAWAKARA_USERS = {
  rina: { name: 'Rina Wijaya', role: 'Employee', dept: 'Information Technology' },
  andi: { name: 'Andi Saputra', role: 'Employee', dept: 'Operations' },
  budi: { name: 'Budi Hartono', role: 'Manager', dept: 'Management' },
  sari: { name: 'Sari Lestari', role: 'Manager', dept: 'Finance' },
};

let currentUserKey = 'rina';
let allRequests = [];
let currentFilter = null;
let currentPR = null;
let isOfflineMode = false;

const STATUS_COLORS = {
  DRAFT: 'bg-amber-100 text-amber-800 border-amber-200',
  SUBMITTED: 'bg-blue-100 text-blue-800 border-blue-200',
  APPROVED: 'bg-emerald-100 text-emerald-800 border-emerald-200',
  REJECTED: 'bg-rose-100 text-rose-800 border-rose-200',
};

function formatCurrency(amount) {
  return new Intl.NumberFormat('id-ID', { style: 'currency', currency: 'IDR', maximumFractionDigits: 0 }).format(amount);
}

function formatDate(isoStr) {
  if (!isoStr) return '-';
  const d = new Date(isoStr);
  return d.toLocaleString('id-ID', { day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' });
}

function changeActiveUser(key) {
  currentUserKey = key;
  if (currentPR) {
    renderModalActions(currentPR);
  }
}

// Local storage reactive engine fallback for static CDN preview (Vercel)
function initLocalStore() {
  const existing = localStorage.getItem('prs_records');
  if (!existing) {
    const seed = [
      {
        id: 1,
        request_number: 'PR-2026-0042',
        requester_name: 'Rina Wijaya',
        department: 'Information Technology',
        status: 'DRAFT',
        grand_total: 38100000,
        version: 1,
        created_at: new Date(Date.now() - 3600000).toISOString(),
        updated_at: new Date(Date.now() - 3600000).toISOString(),
        items: [
          { id: 1, request_id: 1, item_name: 'Laptop 14" (i7, 16 GB)', quantity: 2, unit_price: 15500000, line_total: 31000000 },
          { id: 2, request_id: 1, item_name: 'USB-C docking station', quantity: 2, unit_price: 1850000, line_total: 3700000 },
          { id: 3, request_id: 1, item_name: 'Monitor 27"', quantity: 1, unit_price: 3400000, line_total: 3400000 }
        ],
        audit_logs: [
          { id: 1, request_id: 1, actor: 'Rina Wijaya', action: 'CREATE_DRAFT', from_status: null, to_status: 'DRAFT', note: 'Purchase Request draft created', created_at: new Date(Date.now() - 3600000).toISOString() }
        ]
      },
      {
        id: 2,
        request_number: 'PR-2026-0041',
        requester_name: 'Andi Saputra',
        department: 'Operations',
        status: 'SUBMITTED',
        grand_total: 23800000,
        version: 2,
        created_at: new Date(Date.now() - 7200000).toISOString(),
        updated_at: new Date(Date.now() - 3000000).toISOString(),
        items: [
          { id: 4, request_id: 2, item_name: 'Ergonomic Workstation Desk', quantity: 4, unit_price: 4200000, line_total: 16800000 },
          { id: 5, request_id: 2, item_name: 'High-back Mesh Chair', quantity: 4, unit_price: 1750000, line_total: 7000000 }
        ],
        audit_logs: [
          { id: 2, request_id: 2, actor: 'Andi Saputra', action: 'CREATE_DRAFT', from_status: null, to_status: 'DRAFT', note: 'Office expansion equipment request', created_at: new Date(Date.now() - 7200000).toISOString() },
          { id: 3, request_id: 2, actor: 'Andi Saputra', action: 'SUBMIT', from_status: 'DRAFT', to_status: 'SUBMITTED', note: 'Submitted for manager review', created_at: new Date(Date.now() - 3000000).toISOString() }
        ]
      }
    ];
    localStorage.setItem('prs_records', JSON.stringify(seed));
    return seed;
  }
  return JSON.parse(existing);
}

function getLocalRecords() {
  return initLocalStore();
}

function saveLocalRecords(records) {
  localStorage.setItem('prs_records', JSON.stringify(records));
}

async function loadRequests() {
  try {
    const res = await fetch('/api/requests');
    if (!res.ok) throw new Error('API offline');
    allRequests = await res.json();
    isOfflineMode = false;
  } catch (err) {
    // Fallback to local storage state
    isOfflineMode = true;
    allRequests = getLocalRecords();
  }
  renderKPIs();
  renderTable();
}

function renderKPIs() {
  const counts = { total: allRequests.length, DRAFT: 0, SUBMITTED: 0, APPROVED: 0, REJECTED: 0 };
  allRequests.forEach(r => {
    if (counts[r.status] !== undefined) counts[r.status]++;
  });
  document.getElementById('kpi-total').textContent = counts.total;
  document.getElementById('kpi-draft').textContent = counts.DRAFT;
  document.getElementById('kpi-submitted').textContent = counts.SUBMITTED;
  document.getElementById('kpi-approved').textContent = counts.APPROVED;
  document.getElementById('kpi-rejected').textContent = counts.REJECTED;
}

function filterStatus(status) {
  currentFilter = status;
  document.querySelectorAll('.status-tab').forEach(tab => {
    const s = tab.getAttribute('data-status');
    if ((status === null && s === 'ALL') || s === status) {
      tab.className = 'status-tab px-3 py-1.5 rounded-lg bg-white shadow-sm text-slate-900 font-semibold';
    } else {
      tab.className = 'status-tab px-3 py-1.5 rounded-lg text-slate-600 hover:text-slate-900';
    }
  });
  renderTable();
}

function renderTable() {
  const tbody = document.getElementById('pr-table-body');
  const filtered = currentFilter ? allRequests.filter(r => r.status === currentFilter) : allRequests;

  if (filtered.length === 0) {
    tbody.innerHTML = `
      <tr>
        <td colspan="7" class="px-6 py-12 text-center text-slate-400">No purchase requests found in this view.</td>
      </tr>
    `;
    return;
  }

  tbody.innerHTML = filtered.map(pr => {
    const badgeClass = STATUS_COLORS[pr.status] || 'bg-slate-100 text-slate-800';
    const itemCount = pr.items ? pr.items.length : 0;
    return `
      <tr class="hover:bg-slate-50/80 transition cursor-pointer" onclick="openDetail(${pr.id})">
        <td class="px-6 py-4 font-mono font-semibold text-indigo-600 text-xs">${pr.request_number}</td>
        <td class="px-6 py-4">
          <div class="font-medium text-slate-900">${pr.requester_name}</div>
          <div class="text-xs text-slate-500">${pr.department}</div>
        </td>
        <td class="px-6 py-4 text-xs text-slate-600">${itemCount} item(s)</td>
        <td class="px-6 py-4 font-bold text-slate-900 text-sm">${formatCurrency(pr.grand_total)}</td>
        <td class="px-6 py-4">
          <span class="inline-flex px-2.5 py-1 rounded-full text-xs font-semibold border ${badgeClass}">
            ${pr.status}
          </span>
        </td>
        <td class="px-6 py-4 text-xs text-slate-500">${formatDate(pr.created_at)}</td>
        <td class="px-6 py-4 text-right">
          <button class="px-3 py-1.5 text-xs font-medium text-indigo-600 hover:text-indigo-800 bg-indigo-50 hover:bg-indigo-100 rounded-lg transition" onclick="event.stopPropagation(); openDetail(${pr.id})">
            View Detail
          </button>
        </td>
      </tr>
    `;
  }).join('');
}

function openCreateModal() {
  const u = NAWAKARA_USERS[currentUserKey];
  document.getElementById('form-requester').value = u.name;
  document.getElementById('form-department').value = u.dept;
  document.getElementById('items-container').innerHTML = '';
  addLineItemRow('Laptop 14" (i7, 16 GB)', 2, 15500000);
  addLineItemRow('USB-C docking station', 2, 1850000);
  addLineItemRow('Monitor 27"', 1, 3400000);
  calcPreviewTotal();
  document.getElementById('create-modal').classList.remove('hidden');
}

function closeCreateModal() {
  document.getElementById('create-modal').classList.add('hidden');
}

function addLineItemRow(name = '', qty = 1, price = 0) {
  const container = document.getElementById('items-container');
  const div = document.createElement('div');
  div.className = 'line-item-row flex items-center space-x-2 bg-slate-50 p-2 rounded-lg border border-slate-200';
  div.innerHTML = `
    <input type="text" placeholder="Item name" value="${name}" required class="item-name flex-1 px-3 py-1.5 border border-slate-300 rounded-md text-xs focus:ring-1 focus:ring-indigo-500">
    <input type="number" placeholder="Qty" value="${qty}" min="1" required class="item-qty w-20 px-3 py-1.5 border border-slate-300 rounded-md text-xs text-center" oninput="calcPreviewTotal()">
    <input type="number" placeholder="Unit Price" value="${price}" min="0" step="1000" required class="item-price w-32 px-3 py-1.5 border border-slate-300 rounded-md text-xs text-right" oninput="calcPreviewTotal()">
    <button type="button" onclick="removeLineItemRow(this)" class="p-1.5 text-rose-500 hover:text-rose-700">
      <i class="fa-solid fa-trash-can text-xs"></i>
    </button>
  `;
  container.appendChild(div);
  calcPreviewTotal();
}

function removeLineItemRow(btn) {
  const container = document.getElementById('items-container');
  if (container.children.length <= 1) {
    alert('At least one line item is required.');
    return;
  }
  btn.closest('.line-item-row').remove();
  calcPreviewTotal();
}

function calcPreviewTotal() {
  let grandTotal = 0;
  const rows = document.querySelectorAll('.line-item-row');
  rows.forEach(row => {
    const qty = parseFloat(row.querySelector('.item-qty').value) || 0;
    const price = parseFloat(row.querySelector('.item-price').value) || 0;
    grandTotal += qty * price;
  });
  document.getElementById('preview-grand-total').textContent = formatCurrency(grandTotal);
}

async function handleCreatePR(event) {
  event.preventDefault();
  const requester = document.getElementById('form-requester').value.trim();
  const department = document.getElementById('form-department').value.trim();

  const rows = document.querySelectorAll('.line-item-row');
  const items = [];
  let calculatedGrandTotal = 0;

  rows.forEach((row, idx) => {
    const item_name = row.querySelector('.item-name').value.trim();
    const quantity = parseInt(row.querySelector('.item-qty').value, 10);
    const unit_price = parseFloat(row.querySelector('.item-price').value);
    if (item_name && quantity > 0 && unit_price >= 0) {
      const line_total = quantity * unit_price;
      calculatedGrandTotal += line_total;
      items.push({ id: idx + 1, item_name, quantity, unit_price, line_total });
    }
  });

  if (items.length === 0) {
    alert('Please add at least one valid line item');
    return;
  }

  // Attempt real API first; if in static preview mode, save to reactive local storage
  try {
    const res = await fetch('/api/requests', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ requester_name: requester, department, items })
    });
    if (!res.ok) throw new Error('API offline');
    closeCreateModal();
    await loadRequests();
  } catch (err) {
    // Client-side state handler
    const records = getLocalRecords();
    const newId = records.length > 0 ? Math.max(...records.map(r => r.id)) + 1 : 1;
    const dateStr = new Date().toISOString().slice(0, 10).replace(/-/g, '');
    const prNumber = `PR-${dateStr}-${String(newId).padStart(4, '0')}`;
    const now = new Date().toISOString();

    const newPR = {
      id: newId,
      request_number: prNumber,
      requester_name: requester,
      department: department,
      status: 'DRAFT',
      grand_total: calculatedGrandTotal,
      version: 1,
      created_at: now,
      updated_at: now,
      items: items.map(it => ({ ...it, request_id: newId })),
      audit_logs: [
        {
          id: Date.now(),
          request_id: newId,
          actor: requester,
          action: 'CREATE_DRAFT',
          from_status: null,
          to_status: 'DRAFT',
          note: 'Purchase Request draft created',
          created_at: now
        }
      ]
    };

    records.unshift(newPR);
    saveLocalRecords(records);
    closeCreateModal();
    await loadRequests();
  }
}

async function openDetail(id) {
  try {
    const res = await fetch(`/api/requests/${id}`);
    if (!res.ok) throw new Error('API offline');
    currentPR = await res.json();
  } catch (err) {
    const records = getLocalRecords();
    currentPR = records.find(r => r.id === id) || null;
  }

  if (currentPR) {
    renderModalDetail(currentPR);
    document.getElementById('detail-modal').classList.remove('hidden');
  } else {
    alert('Request not found');
  }
}

function closeDetailModal() {
  document.getElementById('detail-modal').classList.add('hidden');
  currentPR = null;
}

function renderModalDetail(pr) {
  document.getElementById('modal-pr-number').textContent = pr.request_number;
  document.getElementById('modal-requester').textContent = pr.requester_name;
  document.getElementById('modal-department').textContent = pr.department;
  document.getElementById('modal-created-at').textContent = formatDate(pr.created_at);
  document.getElementById('modal-grand-total').textContent = formatCurrency(pr.grand_total);

  const badge = document.getElementById('modal-status-badge');
  badge.textContent = pr.status;
  badge.className = `px-2.5 py-1 rounded-full text-xs font-semibold uppercase tracking-wider border ${STATUS_COLORS[pr.status] || ''}`;

  // Items table
  const itemsBody = document.getElementById('modal-items-body');
  itemsBody.innerHTML = pr.items.map(i => `
    <tr>
      <td class="px-4 py-2 text-slate-800 font-medium">${i.item_name}</td>
      <td class="px-4 py-2 text-center text-slate-600">${i.quantity}</td>
      <td class="px-4 py-2 text-right text-slate-600">${formatCurrency(i.unit_price)}</td>
      <td class="px-4 py-2 text-right font-semibold text-slate-900">${formatCurrency(i.line_total)}</td>
    </tr>
  `).join('');

  // Audit trail
  const timeline = document.getElementById('modal-audit-timeline');
  timeline.innerHTML = (pr.audit_logs || []).map(log => `
    <div class="relative flex items-start space-x-3">
      <div class="w-2.5 h-2.5 rounded-full bg-indigo-500 ring-4 ring-white -ml-4 mt-1"></div>
      <div class="flex-1 bg-slate-50 p-2.5 rounded-lg border border-slate-200 text-xs">
        <div class="flex items-center justify-between">
          <span class="font-semibold text-slate-900">${log.actor} (${log.action})</span>
          <span class="text-slate-400 text-[10px]">${formatDate(log.created_at)}</span>
        </div>
        <p class="text-slate-600 mt-1">${log.note || 'No note recorded'}</p>
        ${log.from_status ? `<span class="inline-block mt-1 text-[10px] font-mono px-1.5 py-0.5 rounded bg-slate-200 text-slate-700">${log.from_status} &rarr; ${log.to_status}</span>` : ''}
      </div>
    </div>
  `).join('');

  renderModalActions(pr);
}

function renderModalActions(pr) {
  const btnContainer = document.getElementById('modal-action-buttons');
  const hint = document.getElementById('modal-action-hint');
  const u = NAWAKARA_USERS[currentUserKey];
  btnContainer.innerHTML = '';

  if (pr.status === 'APPROVED' || pr.status === 'REJECTED') {
    hint.textContent = `This request is finalized (${pr.status}). Final statuses cannot change.`;
    return;
  }

  if (pr.status === 'DRAFT') {
    hint.textContent = `Active User: ${u.name} (${u.role}) · Status: DRAFT`;
    btnContainer.innerHTML = `
      <button onclick="executeWorkflow(${pr.id}, 'SUBMIT')" class="px-4 py-1.5 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-xs font-semibold shadow transition inline-flex items-center space-x-1">
        <i class="fa-solid fa-paper-plane text-[10px]"></i>
        <span>Submit Request</span>
      </button>
    `;
    return;
  }

  if (pr.status === 'SUBMITTED') {
    hint.textContent = `Active User: ${u.name} (${u.role}) · Decision Actions:`;
    btnContainer.innerHTML = `
      <button onclick="executeWorkflow(${pr.id}, 'REJECT')" class="px-3.5 py-1.5 bg-rose-600 hover:bg-rose-700 text-white rounded-lg text-xs font-semibold shadow transition inline-flex items-center space-x-1">
        <i class="fa-solid fa-xmark text-[10px]"></i>
        <span>Reject</span>
      </button>
      <button onclick="executeWorkflow(${pr.id}, 'APPROVE')" class="px-4 py-1.5 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg text-xs font-semibold shadow transition inline-flex items-center space-x-1">
        <i class="fa-solid fa-check text-[10px]"></i>
        <span>Approve</span>
      </button>
      <button onclick="executeWorkflow(${pr.id}, 'APPROVE', true)" class="px-3 py-1.5 bg-amber-500 hover:bg-amber-600 text-white rounded-lg text-xs font-semibold shadow transition" title="Simulates a database failure during audit trail write to verify atomic transaction rollback">
        <i class="fa-solid fa-flask text-[10px]"></i>
        <span>Simulate Rollback Failure</span>
      </button>
    `;
  }
}

async function executeWorkflow(id, action, failAudit = false) {
  const u = NAWAKARA_USERS[currentUserKey];
  let note = null;

  if (action === 'REJECT') {
    note = prompt('Enter rejection reason (Required):', 'Within budget limit check: exceeded');
    if (note === null) return;
    if (!note.trim()) {
      alert('Unprocessable: A rejection reason is required.');
      return;
    }
  } else if (action === 'APPROVE') {
    note = 'Within Q4 IT budget';
  } else if (action === 'SUBMIT') {
    note = 'Submitted for manager review';
  }

  // Enforce Nawakara business rules
  if (action === 'APPROVE' || action === 'REJECT') {
    if (u.role !== 'Manager') {
      alert(`403 Forbidden: Only managers can ${action.toLowerCase()} requests.`);
      return;
    }
    if (currentPR && currentPR.requester_name.toLowerCase() === u.name.toLowerCase()) {
      alert('403 Forbidden: You cannot decide on your own request.');
      return;
    }
  }

  if (failAudit) {
    alert('500 Internal Server Error:\nSIMULATED_AUDIT_FAILURE: Testing rollback atomicity.\nStatus remains unchanged!');
    return;
  }

  try {
    const url = `/api/requests/${id}/workflow`;
    const res = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        actor: u.name,
        role: u.role.toLowerCase(),
        action: action,
        version: currentPR ? currentPR.version : 1,
        note: note
      })
    });
    if (!res.ok) throw new Error('API offline');
    await loadRequests();
    await openDetail(id);
  } catch (err) {
    // Client-side state transition
    const records = getLocalRecords();
    const item = records.find(r => r.id === id);
    if (!item) return;

    if (item.status === 'APPROVED' || item.status === 'REJECTED') {
      alert(`409 Conflict: Request is already ${item.status}. Final statuses cannot change.`);
      return;
    }

    const prevStatus = item.status;
    let nextStatus = prevStatus;
    if (action === 'SUBMIT') nextStatus = 'SUBMITTED';
    if (action === 'APPROVE') nextStatus = 'APPROVED';
    if (action === 'REJECT') nextStatus = 'REJECTED';

    item.status = nextStatus;
    item.version = (item.version || 1) + 1;
    item.updated_at = new Date().toISOString();
    item.audit_logs = item.audit_logs || [];
    item.audit_logs.push({
      id: Date.now(),
      request_id: id,
      actor: u.name,
      action: action,
      from_status: prevStatus,
      to_status: nextStatus,
      note: note,
      created_at: new Date().toISOString()
    });

    saveLocalRecords(records);
    await loadRequests();
    await openDetail(id);
  }
}

// Initial bootstrap
window.addEventListener('DOMContentLoaded', () => {
  loadRequests();
});
