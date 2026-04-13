(function () {
  /* ── Helpers ── */
  const $ = (id) => document.getElementById(id);
  const escHtml = (s) => {
    const d = document.createElement('div');
    d.textContent = s;
    return d.innerHTML;
  };

  const fmtBytes = (b, decimals = 1) => {
    if (!b) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(b) / Math.log(k));
    return parseFloat((b / Math.pow(k, i)).toFixed(decimals)) + ' ' + sizes[i];
  };

  const fmtSpeed = (b) => (b ? fmtBytes(b) + '/s' : '\u2014');

  const fmtEta = (s) => {
    if (!s || s < 0 || s === 8640000) return '\u221E';
    if (s < 60) return s + 's';
    if (s < 3600) return Math.floor(s / 60) + 'm ' + ('0' + (s % 60)).slice(-2) + 's';
    const h = Math.floor(s / 3600);
    const m = Math.floor((s % 3600) / 60);
    return h + 'h ' + ('0' + m).slice(-2) + 'm';
  };

  const fmtRatio = (r) => (r != null ? r.toFixed(2) : '\u2014');

  const progressColor = (p) => {
    if (p < 0.3) return '#e05c5c';
    if (p < 0.7) return '#f5c542';
    return '#3ecf6e';
  };

  /* ── State map ── */
  function stateClass(s) {
    if (['downloading', 'forcedDL'].includes(s)) return 'downloading';
    if (['uploading', 'forcedUP', 'seeding'].includes(s)) return 'seeding';
    if (['pausedDL', 'pausedUP'].includes(s)) return 'paused';
    if (['stalledDL', 'stalledUP'].includes(s)) return 'stalled';
    if (['checkingDL', 'checkingUP', 'checkingResumeData'].includes(s)) return 'checking';
    if (s === 'error') return 'error';
    return 'paused';
  }

  function stateLabel(s) {
    const m = {
      downloading: 'DL', forcedDL: 'DL!', uploading: 'Seed', forcedUP: 'Seed!',
      seeding: 'Seed', pausedDL: 'Paused', pausedUP: 'Paused',
      stalledDL: 'Stalled', stalledUP: 'Stalled',
      checkingDL: 'Checking', checkingUP: 'Checking', checkingResumeData: 'Checking',
      error: 'Error',
    };
    return m[s] || s;
  }

  /* ── Category filters ── */
  const CATEGORY_FILTERS = {
    downloading: (t) => ['downloading', 'forcedDL', 'stalledDL', 'checkingDL'].includes(t.state),
    seeding: (t) => ['uploading', 'forcedUP', 'seeding', 'stalledUP', 'checkingUP'].includes(t.state),
    completed: (t) => t.progress >= 1.0,
    running: (t) => !['pausedDL', 'pausedUP'].includes(t.state),
    stopped: (t) => ['pausedDL', 'pausedUP'].includes(t.state),
    active: (t) => t.dlspeed > 0 || t.upspeed > 0,
    stalled: (t) => ['stalledDL', 'stalledUP'].includes(t.state),
  };

  function init() {
    /* ── State ── */
    let torrents = [];
    let sortCol = 'dlspeed';
    let sortDir = -1;
    let filterState = 'all';
    let searchQ = '';
    let userRole = 'user';
    let refreshTimer = null;
    let countdown = 0;
    let countdownTimer = null;
    let INTERVAL = 5;
    const MAX_INTERVAL = 60;
    let currentInterval = INTERVAL;
    let consecutiveErrors = 0;

    /* ── Auth check ── */
    async function checkAuth() {
      try {
        const resp = await fetch('/api/auth/me');
        if (!resp.ok) {
          window.location.href = '/login';
          return;
        }
        const user = await resp.json();
        userRole = user.role || 'user';
        const adminBtn = $('btn-admin');
        if (user.is_admin && adminBtn) {
          adminBtn.style.display = '';
        }
        applyRoleVisibility();

        // Show weak password warning if flagged at login
        if (sessionStorage.getItem('password_weak') === '1') {
          const bar = $('error-bar');
          if (bar) {
            bar.innerHTML = '<div class="pw-warn-banner">Your password does not meet current security requirements. Please contact an admin to update it. <button class="btn-ghost pw-warn-dismiss">Dismiss</button></div>';
            bar.querySelector('.pw-warn-dismiss').addEventListener('click', () => {
              bar.innerHTML = '';
              sessionStorage.removeItem('password_weak');
            });
          }
        }
      } catch {
        window.location.href = '/login';
      }
    }

    /* ── Role visibility ── */
    function applyRoleVisibility() {
      const showRatio = userRole === 'admin' || userRole === 'monitor';
      const ratioTh = document.querySelector('thead th[data-col="ratio"]');
      if (ratioTh) ratioTh.style.display = showRatio ? '' : 'none';
    }

    /* ── Connectivity ── */
    function setConnected(ok) {
      const el = $('conn-dot');
      if (el) {
        el.className = 'dot ' + (ok ? 'dot-green' : 'dot-red');
        el.title = ok ? 'Connected to qBittorrent' : 'Disconnected';
      }
    }

    function setSpinning(v) {
      const el = document.querySelector('.header-right');
      if (el) el.classList.toggle('spinning', v);
    }

    function showError(msg) {
      const el = $('error-bar');
      if (el) {
        el.style.display = msg ? 'block' : 'none';
        el.textContent = msg;
      }
    }

    /* ── Fetch ── */
    async function fetchData() {
      setSpinning(true);
      try {
        const [torrentsResp, transferResp] = await Promise.all([
          fetch('/api/torrents'),
          fetch('/api/transfer'),
        ]);

        if (torrentsResp.status === 401 || transferResp.status === 401) {
          console.warn('Session expired (401), redirecting to login');
          window.location.href = '/login';
          return;
        }

        if (!torrentsResp.ok || !transferResp.ok) {
          const errorResp = !torrentsResp.ok ? torrentsResp : transferResp;
          let detail = 'Failed to fetch data';
          if (errorResp.status === 502) {
            try {
              const body = await errorResp.json();
              detail = body.detail || detail;
            } catch {}
          }
          console.error('API error:', errorResp.status, detail);
          throw new Error(detail);
        }

        torrents = await torrentsResp.json();
        const transfer = await transferResp.json();

        updateStats(transfer);
        setConnected(true);
        showError('');

        // Reset backoff on success
        if (consecutiveErrors > 0) {
          console.info('Connection restored, polling reset to ' + INTERVAL + 's');
          consecutiveErrors = 0;
          if (currentInterval !== INTERVAL) {
            currentInterval = INTERVAL;
            startRefreshLoop();
          }
        }
      } catch (e) {
        consecutiveErrors++;
        const isBan = e.message && e.message.toLowerCase().includes('banned');

        if (isBan) {
          console.error('IP banned by qBittorrent \u2014 retries paused for 15 minutes');
          showError('IP banned by qBittorrent. Login attempts paused for 15 minutes. Will auto-retry.');
          currentInterval = MAX_INTERVAL;
        } else {
          console.error('fetchData failed:', e.message);
          showError('Cannot reach qBittorrent: ' + e.message);
          const newInterval = Math.min(INTERVAL * Math.pow(2, consecutiveErrors), MAX_INTERVAL);
          if (newInterval !== currentInterval) {
            console.warn('Polling slowed to ' + newInterval + 's after ' + consecutiveErrors + ' consecutive errors');
            currentInterval = newInterval;
          }
        }

        setConnected(false);
        startRefreshLoop();
      } finally {
        setSpinning(false);
      }
      render();
    }

    /* ── Stats bar ── */
    function updateStats(t) {
      const dlEl = $('s-dl');
      const ulEl = $('s-ul');
      if (dlEl) dlEl.textContent = fmtSpeed(t.dl_info_speed);
      if (ulEl) ulEl.textContent = fmtSpeed(t.up_info_speed);
      computeCounts();
    }

    function computeCounts() {
      const counts = { all: torrents.length };
      for (const key of Object.keys(CATEGORY_FILTERS)) counts[key] = 0;
      for (const t of torrents) {
        for (const [key, fn] of Object.entries(CATEGORY_FILTERS)) {
          if (fn(t)) counts[key]++;
        }
      }
      for (const [key, val] of Object.entries(counts)) {
        const el = document.getElementById('fc-' + key);
        if (el) el.textContent = val;
      }
      // Update mobile filter dropdown text with counts
      const mf = $('mobile-filter');
      if (mf) {
        for (const opt of mf.options) {
          const key = opt.value;
          const label = key.charAt(0).toUpperCase() + key.slice(1);
          const count = counts[key] !== undefined ? counts[key] : 0;
          opt.textContent = label + ' (' + count + ')';
        }
      }
    }

    /* ── Render ── */
    function getFiltered() {
      return torrents.filter((t) => {
        if (filterState !== 'all') {
          const fn = CATEGORY_FILTERS[filterState];
          if (fn && !fn(t)) return false;
          if (!fn && stateClass(t.state) !== filterState) return false;
        }
        if (searchQ && !t.name.toLowerCase().includes(searchQ)) return false;
        return true;
      });
    }

    function getSorted(list) {
      return [...list].sort((a, b) => {
        let av = a[sortCol] ?? '';
        let bv = b[sortCol] ?? '';
        if (typeof av === 'string') return av.localeCompare(bv) * sortDir;
        return (av - bv) * sortDir;
      });
    }

    function render() {
      const list = getSorted(getFiltered());
      const tbody = $('tbody');
      const empty = $('empty');
      if (!tbody || !empty) return;

      if (!list.length) {
        tbody.innerHTML = '';
        empty.style.display = 'block';
        return;
      }
      empty.style.display = 'none';

      const showRatio = userRole === 'admin' || userRole === 'monitor';
      tbody.innerHTML = list
        .map((t) => {
          const sc = stateClass(t.state);
          const pct = (t.progress * 100).toFixed(1);
          const pcol = progressColor(t.progress);
          return (
            '<tr>' +
            '<td class="name-cell">' +
              '<div class="torrent-name" title="' + escHtml(t.name) + '">' + escHtml(t.name) + '</div>' +
              (t.category ? '<div class="torrent-cat">' + escHtml(t.category) + '</div>' : '') +
            '</td>' +
            '<td class="num">' + fmtBytes(t.size) + '</td>' +
            '<td><div class="progress-wrap">' +
              '<div class="progress-bar"><div class="progress-fill" style="width:' + pct + '%;background:' + pcol + '"></div></div>' +
              '<div class="progress-pct">' + pct + '%</div>' +
            '</div></td>' +
            '<td class="num dl-speed">' + fmtSpeed(t.dlspeed) + '</td>' +
            '<td class="num ul-speed">' + fmtSpeed(t.upspeed) + '</td>' +
            '<td class="num eta">' + fmtEta(t.eta) + '</td>' +
            (showRatio ? '<td class="num ratio">' + fmtRatio(t.ratio) + '</td>' : '') +
            '<td><span class="badge badge-' + sc + '">' + stateLabel(t.state) + '</span></td>' +
            '</tr>'
          );
        })
        .join('');
    }

    /* ── Sort ── */
    document.querySelectorAll('thead th[data-col]').forEach((th) => {
      th.addEventListener('click', () => {
        const col = th.dataset.col;
        if (sortCol === col) sortDir *= -1;
        else { sortCol = col; sortDir = -1; }
        document.querySelectorAll('thead th').forEach((x) => x.classList.remove('sorted'));
        th.classList.add('sorted');
        const icon = th.querySelector('.sort-icon');
        if (icon) icon.textContent = sortDir === -1 ? '\u2193' : '\u2191';
        const ms = $('mobile-sort');
        if (ms) ms.value = sortCol;
        render();
      });
    });

    /* ── Mobile sort dropdown ── */
    const mobileSort = $('mobile-sort');
    if (mobileSort) {
      mobileSort.addEventListener('change', () => {
        sortCol = mobileSort.value;
        syncSortUi();
        render();
      });
    }
    const mobileSortDir = $('mobile-sort-dir');
    if (mobileSortDir) {
      mobileSortDir.addEventListener('click', () => {
        sortDir *= -1;
        syncSortUi();
        render();
      });
    }
    function syncSortUi() {
      document.querySelectorAll('thead th').forEach((x) => x.classList.remove('sorted'));
      const th = document.querySelector('thead th[data-col="' + sortCol + '"]');
      if (th) {
        th.classList.add('sorted');
        const icon = th.querySelector('.sort-icon');
        if (icon) icon.textContent = sortDir === -1 ? '\u2193' : '\u2191';
      }
      if (mobileSortDir) {
        const desc = sortDir === -1;
        mobileSortDir.textContent = desc ? '\u2193' : '\u2191';
        mobileSortDir.setAttribute('aria-pressed', desc ? 'true' : 'false');
        mobileSortDir.title = desc ? 'Descending' : 'Ascending';
      }
      const mfd = $('mobile-filter-dir');
      if (mfd) {
        const desc = sortDir === -1;
        mfd.textContent = desc ? '\u2193' : '\u2191';
        mfd.setAttribute('aria-pressed', desc ? 'true' : 'false');
        mfd.title = desc ? 'Descending' : 'Ascending';
      }
    }

    /* ── Filter ── */
    document.querySelectorAll('.filter-btn').forEach((btn) => {
      btn.addEventListener('click', () => {
        document.querySelectorAll('.filter-btn').forEach((b) => b.classList.remove('active'));
        btn.classList.add('active');
        filterState = btn.dataset.filter;
        const mf = $('mobile-filter');
        if (mf) mf.value = filterState;
        render();
      });
    });

    /* ── Mobile filter dropdown ── */
    const mobileFilter = $('mobile-filter');
    if (mobileFilter) {
      mobileFilter.addEventListener('change', () => {
        filterState = mobileFilter.value;
        document.querySelectorAll('.filter-btn').forEach((b) => b.classList.remove('active'));
        const activeBtn = document.querySelector('.filter-btn[data-filter="' + filterState + '"]');
        if (activeBtn) activeBtn.classList.add('active');
        render();
      });
    }
    const mobileFilterDir = $('mobile-filter-dir');
    if (mobileFilterDir) {
      mobileFilterDir.addEventListener('click', () => {
        sortDir *= -1;
        syncSortUi();
        render();
      });
    }

    /* ── Search ── */
    const searchEl = $('search');
    if (searchEl) {
      searchEl.addEventListener('input', (e) => {
        searchQ = e.target.value.toLowerCase().trim();
        render();
      });
    }

    /* ── Refresh ── */
    function startRefreshLoop() {
      clearInterval(refreshTimer);
      clearInterval(countdownTimer);
      countdown = currentInterval;
      countdownTimer = setInterval(() => {
        countdown--;
        const ri = $('refresh-info');
        if (ri) ri.textContent = 'Refresh in ' + countdown + 's';
        if (countdown <= 0) countdown = currentInterval;
      }, 1000);
      refreshTimer = setInterval(() => {
        fetchData();
        countdown = currentInterval;
      }, currentInterval * 1000);
    }

    function doRefresh() {
      fetchData();
      startRefreshLoop();
    }

    const refreshBtn = $('btn-refresh');
    if (refreshBtn) refreshBtn.addEventListener('click', doRefresh);

    /* ── Logout ── */
    const logoutBtn = $('btn-logout');
    if (logoutBtn) {
      logoutBtn.addEventListener('click', async () => {
        await fetch('/api/auth/logout', { method: 'POST' });
        window.location.href = '/login';
      });
    }

    /* ── Boot ── */
    (async function boot() {
      await checkAuth();
      try {
        const resp = await fetch('/api/auth/settings/refresh-rate');
        if (resp.ok) {
          const data = await resp.json();
          INTERVAL = Math.max(2, Math.min(300, data.refresh_rate));
          currentInterval = INTERVAL;
        }
      } catch { /* use default */ }
      doRefresh();
    })();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
