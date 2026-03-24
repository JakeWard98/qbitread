(function () {
  const $ = (id) => document.getElementById(id);
  const errorEl = $('admin-error');
  const tbody = $('users-tbody');

  function getCsrfToken() {
    const m = document.cookie.match(/(?:^|;\s*)csrf_token=([^;]*)/);
    return m ? m[1] : '';
  }

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

  function renderUsers(users) {
    tbody.innerHTML = users
      .map((u) => {
        const role = u.is_admin ? 'Admin' : 'User';
        const badgeClass = u.is_admin ? 'badge-admin' : 'badge-user';
        const created = new Date(u.created_at).toLocaleDateString();
        return (
          '<tr>' +
          '<td>' + escHtml(u.username) + '</td>' +
          '<td><span class="badge ' + badgeClass + '">' + role + '</span></td>' +
          '<td style="color:var(--muted)">' + created + '</td>' +
          '<td><button class="btn-danger btn-del" data-id="' + u.id + '">Delete</button></td>' +
          '</tr>'
        );
      })
      .join('');

    tbody.querySelectorAll('.btn-del').forEach((btn) => {
      btn.addEventListener('click', () => deleteUser(parseInt(btn.dataset.id)));
    });
  }

  function escHtml(s) {
    const d = document.createElement('div');
    d.textContent = s;
    return d.innerHTML;
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

  $('btn-create').addEventListener('click', async () => {
    errorEl.textContent = '';
    const username = $('new-username').value.trim();
    const password = $('new-password').value;
    const is_admin = $('new-admin').checked;

    if (!username || !password) {
      errorEl.textContent = 'Username and password are required.';
      return;
    }
    if (password.length < 6) {
      errorEl.textContent = 'Password must be at least 6 characters.';
      return;
    }

    try {
      const resp = await fetch('/api/auth/users', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRF-Token': getCsrfToken(),
        },
        body: JSON.stringify({ username, password, is_admin }),
      });

      if (!resp.ok) {
        const data = await resp.json();
        errorEl.textContent = data.detail || 'Failed to create user.';
        return;
      }

      $('new-username').value = '';
      $('new-password').value = '';
      $('new-admin').checked = false;
      loadUsers();
    } catch {
      errorEl.textContent = 'Network error.';
    }
  });

  /* ── Logout ── */
  $('btn-logout').addEventListener('click', async () => {
    await fetch('/api/auth/logout', { method: 'POST' });
    window.location.href = '/login';
  });

  /* ── Boot ── */
  checkAdmin().then(() => loadUsers());
})();
