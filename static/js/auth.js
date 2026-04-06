(function () {
  const form = document.getElementById('login-form');
  const errorEl = document.getElementById('login-error');

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    errorEl.textContent = '';

    const username = document.getElementById('username').value.trim();
    const password = document.getElementById('password').value;

    if (!username || !password) {
      errorEl.textContent = 'Please enter username and password.';
      return;
    }

    try {
      const resp = await fetch('/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password }),
      });

      if (resp.status === 429) {
        errorEl.textContent = 'Too many attempts. Please wait and try again.';
        return;
      }

      const data = await resp.json();

      if (!resp.ok) {
        errorEl.textContent = data.detail || 'Login failed.';
        return;
      }

      if (data.password_weak) {
        sessionStorage.setItem('password_weak', '1');
      }
      window.location.href = '/';
    } catch {
      errorEl.textContent = 'Network error. Please try again.';
    }
  });
})();
