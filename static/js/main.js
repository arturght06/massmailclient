let currentAccountId = null;

async function selectAccount(id, email) {
    currentAccountId = id;
    document.getElementById('current-view-title').innerText = email;
    document.getElementById('refresh-btn').disabled = false;
    document.getElementById('settings-btn').disabled = false;
    
    document.querySelectorAll('.account-item').forEach(el => el.classList.remove('active'));
    document.getElementById('acc-' + id).classList.add('active');
    
    await loadCachedEmails(id);
}

async function loadCachedEmails(id) {
    const container = document.getElementById('emails-container');
    container.innerHTML = '<div style="text-align:center; padding:20px; color:#888">Loading cached emails...</div>';
    const res = await fetch(`/get_cached_emails/${id}`);
    const emails = await res.json();
    container.innerHTML = '';
    if(emails.length === 0) container.innerHTML = '<div style="text-align:center; padding:40px; color:#888">No emails.</div>';
    emails.forEach(email => {
        const div = document.createElement('div');
        div.className = 'email-card';
        div.innerHTML = `<div class="email-subject">${email.subject}</div><div style="font-size:12px; color:#666">${email.sender}</div>`;
        div.onclick = () => {
            document.getElementById('modal-subject').innerText = email.subject;
            document.getElementById('modal-sender').innerText = email.sender;
            document.getElementById('modal-body').innerText = email.body;
            document.getElementById('modal-email').style.display = 'block';
        };
        container.appendChild(div);
    });
}

async function syncEmails() {
    if(!currentAccountId) return;
    const btn = document.getElementById('refresh-btn');
    btn.disabled = true; btn.childNodes[1].textContent = ' Syncing...';
    await fetch(`/sync_emails/${currentAccountId}`, {method: 'POST'});
    await loadCachedEmails(currentAccountId);
    btn.disabled = false; btn.childNodes[1].textContent = ' Check New';
    updateStatusIcon(currentAccountId, 'active');
}

// --- Settings Logic ---
async function openSettingsModal() {
    if(!currentAccountId) return;
    const res = await fetch(`/get_account_details/${currentAccountId}`);
    const acc = await res.json();
    
    document.getElementById('edit-email').value = acc.email;
    document.getElementById('edit-pass').value = acc.password;
    document.getElementById('edit-server').value = acc.imap_server;
    document.getElementById('modal-settings').style.display = 'block';
}

async function saveAccount() {
    const email = document.getElementById('edit-email').value;
    const password = document.getElementById('edit-pass').value;
    const server = document.getElementById('edit-server').value;
    
    // UX
    const btn = document.querySelector('#modal-settings .btn-success');
    const originalText = btn.innerText;
    btn.innerText = 'Verifying...'; btn.disabled = true;

    const res = await fetch(`/update_account/${currentAccountId}`, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({email, password, imap_server: server})
    });
    const data = await res.json();
    
    btn.innerText = originalText; btn.disabled = false;
    
    if(data.status === 'success') {
        alert('Success!');
        location.reload();
    } else {
        alert(data.message);
    }
}

async function deleteAccount() {
    if(confirm('Are you sure you want to delete this account and all its emails?')) {
        await fetch(`/delete_account/${currentAccountId}`, {method: 'POST'});
        location.reload();
    }
}

async function processBulk() {
    const text = document.getElementById('bulk-input').value;
    await fetch('/bulk_import', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({data: text})
    });
    location.reload();
}

function copyText(text) { navigator.clipboard.writeText(text); }
function updateStatusIcon(id, status) { 
    const el = document.getElementById(`status-icon-${id}`);
    if(el) el.className = `fas fa-circle status-icon status-${status}`;
}

// Auto-check background
setTimeout(async () => {
    const accounts = document.querySelectorAll('.account-item');
    for(let acc of accounts) {
        const id = acc.id.replace('acc-', '');
        const icon = document.getElementById(`status-icon-${id}`);
        if(icon.classList.contains('status-pending') || icon.classList.contains('status-unknown')) {
            icon.className = 'fas fa-spinner fa-spin status-icon';
            try {
                const res = await fetch(`/check_account_status/${id}`);
                const data = await res.json();
                updateStatusIcon(id, data.status);
            } catch(e) {}
        }
    }
}, 1000);