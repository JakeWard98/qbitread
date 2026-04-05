(function () {
  const form = document.getElementById('setup-form');
  const errorEl = document.getElementById('setup-error');

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    errorEl.textContent = '';

    const username = document.getElementById('username').value.trim();
    const password = document.getElementById('password').value;
    const confirmPassword = document.getElementById('confirm-password').value;

    if (!username || !password) {
      errorEl.textContent = 'Please enter username and password.';
      return;
    }

    if (password.length < 6) {
      errorEl.textContent = 'Password must be at least 6 characters.';
      return;
    }

    if (password !== confirmPassword) {
      errorEl.textContent = 'Passwords do not match.';
      return;
    }

    try {
      const resp = await fetch('/api/auth/setup', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password }),
      });

      const data = await resp.json();

      if (resp.status === 403) {
        // Setup already completed
        window.location.href = '/login';
        return;
      }

      if (!resp.ok) {
        errorEl.textContent = data.detail || 'Setup failed.';
        return;
      }

      window.location.href = '/login';
    } catch {
      errorEl.textContent = 'Network error. Please try again.';
    }
  });
})();
