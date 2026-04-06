(function () {
  function validatePassword(pw) {
    const errors = [];
    if (pw.length < 8) errors.push('at least 8 characters');
    if (!/[A-Z]/.test(pw)) errors.push('1 uppercase letter');
    if (!/[a-z]/.test(pw)) errors.push('1 lowercase letter');
    if (!/\d/.test(pw)) errors.push('1 number');
    if (!/[^a-zA-Z0-9]/.test(pw)) errors.push('1 special character');
    return { valid: errors.length === 0, errors };
  }

  function init() {
    const form = document.getElementById('setup-form');
    const errorEl = document.getElementById('setup-error');
    if (!form || !errorEl) return;

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

      const check = validatePassword(password);
      if (!check.valid) {
        errorEl.textContent = 'Password must contain: ' + check.errors.join(', ') + '.';
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
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
