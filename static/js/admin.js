(function () {
  const $ = (id) => document.getElementById(id);

  function getCsrfToken() {
    const m = document.cookie.match(/(?:^|;\s*)csrf_token=([^;]*)/);
    return m ? m[1] : '';
  }

  function validatePassword(pw) {
    const errors = [];
    if (pw.length < 8) errors.push('at least 8 characters');
    if (!/[A-Z]/.test(pw)) errors.push('1 uppercase letter');
    if (!/[a-z]/.test(pw)) errors.push('1 lowercase letter');
    if (!/\d/.test(pw)) errors.push('1 number');
    if (!/[^a-zA-Z0-9]/.test(pw)) errors.push('1 special character');
    return { valid: errors.length === 0, errors };
  }

  function escHtml(s) {
    const d = document.createElement('div');
    d.textContent = s;
    return d.innerHTML;
  }

  function init() {
    const errorEl = $('admin-error');
    const tbody = $('users-tbody');
    if (!errorEl || !tbody) return;

    async function checkAdmin() {
      try {
        const resp = await fetch('/api/auth/me');
        if (!resp.ok) { window.location.href = '/login'; return; }
        const user = await resp.json();
        if (!user.is_admin) { window.location.href = '/'; return; }
      } catch {
        window.location.href = '/login';
      }
    }

    async function loadUsers() {
      errorEl.textContent = '';
      try {
        const resp = await fetch('/api/auth/users');
        if (resp.status === 401) { window.location.href = '/login'; return; }
        if (resp.status === 403) { window.location.href = '/'; return; }
        const users = await resp.json();
        renderUsers(users);
      } catch {
        errorEl.textContent = 'Failed to load users.';
      }
    }

    function roleBadgeClass(role) {
      if (role === 'admin') return 'badge-admin';
      if (role === 'manager') return 'badge-manager';
      return 'badge-user';
    }

    function roleLabel(role) {
      if (role === 'admin') return 'Admin';
      if (role === 'manager') return 'Manager';
      return 'User';
    }

    function renderUsers(users) {
      tbody.innerHTML = users
        .map((u) => {
          const created = new Date(u.created_at).toLocaleDateString();
          const pwStatus = u.password_meets_policy
            ? '<span class="badge badge-pw-ok">OK</span>'
            : '<span class="badge badge-pw-weak" title="Password does not meet current security requirements">Weak</span>';
          return (
            '<tr>' +
            '<td>' + escHtml(u.username) + '</td>' +
            '<td><span class="badge ' + roleBadgeClass(u.role) + '">' + roleLabel(u.role) + '</span></td>' +
            '<td style="color:var(--muted)">' + created + '</td>' +
            '<td>' + pwStatus + ' <button class="btn-ghost btn-chpw" data-id="' + u.id + '" data-name="' + escHtml(u.username) + '">Change</button></td>' +
            '<td><button class="btn-danger btn-del" data-id="' + u.id + '">Delete</button></td>' +
            '</tr>'
          );
        })
        .join('');

      tbody.querySelectorAll('.btn-del').forEach((btn) => {
        btn.addEventListener('click', () => deleteUser(parseInt(btn.dataset.id)));
      });

      tbody.querySelectorAll('.btn-chpw').forEach((btn) => {
        btn.addEventListener('click', () => showChangePassword(parseInt(btn.dataset.id), btn.dataset.name));
      });
    }

    async function deleteUser(id) {
      if (!confirm('Delete this user?')) return;
      errorEl.textContent = '';
      try {
        const resp = await fetch('/api/auth/users/' + id, {
          method: 'DELETE',
          headers: { 'X-CSRF-Token': getCsrfToken() },
        });
        if (!resp.ok) {
          const data = await resp.json();
          errorEl.textContent = data.detail || 'Failed to delete user.';
          return;
        }
        loadUsers();
      } catch {
        errorEl.textContent = 'Network error.';
      }
    }

    /* ── Change Password ── */
    function showChangePassword(userId, username) {
      // Remove any existing change-password form
      const existing = document.getElementById('chpw-form-' + userId);
      if (existing) { existing.remove(); return; }

      document.querySelectorAll('.chpw-inline').forEach((el) => el.remove());

      const row = document.createElement('tr');
      row.className = 'chpw-inline';
      row.id = 'chpw-form-' + userId;
      row.innerHTML =
        '<td colspan="5" style="padding:10px 8px">' +
        '<div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap">' +
        '<span style="font-size:12px;color:var(--muted)">New password for <strong style="color:var(--text)">' + escHtml(username) + '</strong>:</span>' +
        '<input type="password" class="chpw-input" placeholder="min 8 chars" style="background:#1e1e1e;border:1px solid var(--border);color:var(--text);border-radius:var(--radius);padding:6px 8px;font-size:12px;width:180px;outline:none">' +
        '<button class="btn-primary chpw-save" style="font-size:11px;padding:6px 12px">Save</button>' +
        '<button class="btn-ghost chpw-cancel" style="font-size:11px;padding:6px 10px">Cancel</button>' +
        '<span class="chpw-msg" style="font-size:12px;min-height:16px"></span>' +
        '</div>' +
        '</td>';

      // Insert after the user's row
      const userRow = tbody.querySelector('.btn-chpw[data-id="' + userId + '"]').closest('tr');
      userRow.after(row);

      const input = row.querySelector('.chpw-input');
      const msg = row.querySelector('.chpw-msg');
      input.focus();

      row.querySelector('.chpw-cancel').addEventListener('click', () => row.remove());

      row.querySelector('.chpw-save').addEventListener('click', async () => {
        msg.textContent = '';
        msg.style.color = 'var(--red)';
        const pw = input.value;

        if (!pw) { msg.textContent = 'Password is required.'; return; }

        const check = validatePassword(pw);
        if (!check.valid) {
          msg.textContent = 'Missing: ' + check.errors.join(', ');
          return;
        }

        try {
          const resp = await fetch('/api/auth/users/' + userId + '/password', {
            method: 'PUT',
            headers: {
              'Content-Type': 'application/json',
              'X-CSRF-Token': getCsrfToken(),
            },
            body: JSON.stringify({ password: pw }),
          });

          if (!resp.ok) {
            const data = await resp.json();
            msg.textContent = data.detail || 'Failed to change password.';
            return;
          }

          msg.style.color = 'var(--green)';
          msg.textContent = 'Password updated.';
          setTimeout(() => { row.remove(); loadUsers(); }, 1000);
        } catch {
          msg.textContent = 'Network error.';
        }
      });
    }

    /* ── Create User ── */
    const createBtn = $('btn-create');
    if (createBtn) {
      createBtn.addEventListener('click', async () => {
        errorEl.textContent = '';
        const username = $('new-username').value.trim();
        const password = $('new-password').value;
        const role = $('new-role').value;

        if (!username || !password) {
          errorEl.textContent = 'Username and password are required.';
          return;
        }

        const check = validatePassword(password);
        if (!check.valid) {
          errorEl.textContent = 'Password must contain: ' + check.errors.join(', ') + '.';
          return;
        }

        try {
          const resp = await fetch('/api/auth/users', {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              'X-CSRF-Token': getCsrfToken(),
            },
            body: JSON.stringify({ username, password, role }),
          });

          if (!resp.ok) {
            const data = await resp.json();
            errorEl.textContent = data.detail || 'Failed to create user.';
            return;
          }

          $('new-username').value = '';
          $('new-password').value = '';
          $('new-role').value = 'user';
          loadUsers();
        } catch {
          errorEl.textContent = 'Network error.';
        }
      });
    }

    /* ── Logout ── */
    const logoutBtn = $('btn-logout');
    if (logoutBtn) {
      logoutBtn.addEventListener('click', async () => {
        await fetch('/api/auth/logout', { method: 'POST' });
        window.location.href = '/login';
      });
    }

    /* ── qBittorrent Connection ── */
    const qbitDot = $('qbit-dot');
    const qbitStatusText = $('qbit-status-text');
    const qbitStatusMsg = $('qbit-status-msg');
    const browserAuthMsg = $('browser-auth-msg');

    async function loadConnectionInfo() {
      try {
        const resp = await fetch('/api/qbit/connection-info');
        if (!resp.ok) return;
        const info = await resp.json();

        if (qbitDot && qbitStatusText && qbitStatusMsg) {
          if (info.authenticated) {
            qbitDot.className = 'dot dot-green';
            qbitStatusText.textContent = 'Connected';
            qbitStatusText.style.color = 'var(--green)';
            qbitStatusMsg.textContent = '';
          } else if (info.ban_detected) {
            qbitDot.className = 'dot dot-red';
            qbitStatusText.textContent = 'IP Banned';
            qbitStatusText.style.color = 'var(--red)';
            qbitStatusMsg.textContent = 'Ban time remaining: ~' + info.ban_seconds_remaining + 's. Use Browser Auth or wait for ban to lift.';
          } else if (info.cooldown_remaining > 0) {
            qbitDot.className = 'dot dot-red';
            qbitStatusText.textContent = 'Cooldown';
            qbitStatusText.style.color = 'var(--yellow)';
            qbitStatusMsg.textContent = 'Retry cooldown: ' + info.cooldown_remaining + 's remaining.';
          } else {
            qbitDot.className = 'dot dot-red';
            qbitStatusText.textContent = 'Disconnected';
            qbitStatusText.style.color = 'var(--red)';
            qbitStatusMsg.textContent = 'Not authenticated with qBittorrent.';
          }
        }

        // Pre-fill fields from config
        if (info.browser_host && !$('qbit-url').value) {
          $('qbit-url').value = info.browser_host;
        }
        if (info.qbit_username && !$('qbit-user').value) {
          $('qbit-user').value = info.qbit_username;
        }
      } catch {
        if (qbitDot) qbitDot.className = 'dot dot-red';
        if (qbitStatusText) {
          qbitStatusText.textContent = 'Error';
          qbitStatusText.style.color = 'var(--red)';
        }
      }
    }

    const retryBtn = $('btn-retry-login');
    if (retryBtn) {
      retryBtn.addEventListener('click', async () => {
        retryBtn.disabled = true;
        retryBtn.textContent = 'Retrying...';
        if (qbitStatusMsg) qbitStatusMsg.textContent = '';
        try {
          const resp = await fetch('/api/qbit/retry-login', {
            method: 'POST',
            headers: { 'X-CSRF-Token': getCsrfToken() },
          });
          const data = await resp.json();
          if (qbitStatusMsg) {
            qbitStatusMsg.textContent = data.message || '';
            qbitStatusMsg.style.color = data.success ? 'var(--green)' : 'var(--red)';
          }
          await loadConnectionInfo();
        } catch {
          if (qbitStatusMsg) {
            qbitStatusMsg.textContent = 'Network error.';
            qbitStatusMsg.style.color = 'var(--red)';
          }
        }
        retryBtn.disabled = false;
        retryBtn.textContent = 'Retry Login';
      });
    }

    const autofillBtn = $('btn-autofill');
    if (autofillBtn) {
      autofillBtn.addEventListener('click', async () => {
        if (browserAuthMsg) browserAuthMsg.textContent = '';
        try {
          const resp = await fetch('/api/qbit/browser-auth-creds');
          if (!resp.ok) {
            if (browserAuthMsg) {
              browserAuthMsg.textContent = 'Failed to fetch credentials.';
              browserAuthMsg.style.color = 'var(--red)';
            }
            return;
          }
          const creds = await resp.json();
          if (creds.url) $('qbit-url').value = creds.url;
          if (creds.username) $('qbit-user').value = creds.username;
          if (creds.password) $('qbit-pass').value = creds.password;
          if (browserAuthMsg) {
            browserAuthMsg.textContent = 'Credentials loaded from server.';
            browserAuthMsg.style.color = 'var(--green)';
          }
        } catch {
          if (browserAuthMsg) {
            browserAuthMsg.textContent = 'Network error.';
            browserAuthMsg.style.color = 'var(--red)';
          }
        }
      });
    }

    const browserAuthBtn = $('btn-browser-auth');
    if (browserAuthBtn) {
      browserAuthBtn.addEventListener('click', () => {
        const url = $('qbit-url').value.trim();
        const username = $('qbit-user').value.trim();
        const password = $('qbit-pass').value;

        if (!url) {
          if (browserAuthMsg) {
            browserAuthMsg.textContent = 'qBit URL is required.';
            browserAuthMsg.style.color = 'var(--red)';
          }
          return;
        }
        if (!username || !password) {
          if (browserAuthMsg) {
            browserAuthMsg.textContent = 'Username and password are required.';
            browserAuthMsg.style.color = 'var(--red)';
          }
          return;
        }

        // Create sandboxed hidden iframe (no allow-same-origin to protect our cookies)
        const iframe = document.createElement('iframe');
        iframe.name = 'qbit-auth-frame';
        iframe.sandbox = 'allow-forms';
        iframe.style.display = 'none';
        document.body.appendChild(iframe);

        // Create hidden form targeting the iframe
        const form = document.createElement('form');
        form.method = 'POST';
        form.action = url.replace(/\/+$/, '') + '/api/v2/auth/login';
        form.target = 'qbit-auth-frame';
        form.style.display = 'none';

        const inputUser = document.createElement('input');
        inputUser.type = 'hidden';
        inputUser.name = 'username';
        inputUser.value = username;
        form.appendChild(inputUser);

        const inputPass = document.createElement('input');
        inputPass.type = 'hidden';
        inputPass.name = 'password';
        inputPass.value = password;
        form.appendChild(inputPass);

        document.body.appendChild(form);
        form.submit();

        if (browserAuthMsg) {
          browserAuthMsg.textContent = 'Auth request sent to qBittorrent. Click "Retry Login" to check if the backend can now connect.';
          browserAuthMsg.style.color = 'var(--accent)';
        }

        // Clean up after 5 seconds
        setTimeout(() => {
          iframe.remove();
          form.remove();
        }, 5000);
      });
    }

    const openWebuiBtn = $('btn-open-webui');
    if (openWebuiBtn) {
      openWebuiBtn.addEventListener('click', () => {
        const url = $('qbit-url').value.trim();
        if (!url) {
          if (browserAuthMsg) {
            browserAuthMsg.textContent = 'Enter a qBit URL first.';
            browserAuthMsg.style.color = 'var(--red)';
          }
          return;
        }
        window.open(url, '_blank');
      });
    }

    /* ── Boot ── */
    checkAdmin().then(() => {
      loadUsers();
      loadConnectionInfo();
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
