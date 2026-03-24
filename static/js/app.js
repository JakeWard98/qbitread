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

  /* ── State ── */
  let torrents = [];
  let sortCol = 'dlspeed';
  let sortDir = -1;
  let filterState = 'all';
  let searchQ = '';
  let refreshTimer = null;
  let countdown = 0;
  let countdownTimer = null;
  const INTERVAL = 5;

  /* ── Auth check ── */
  async function checkAuth() {
    try {
      const resp = await fetch('/api/auth/me');
      if (!resp.ok) {
        window.location.href = '/login';
        return;
      }
      const user = await resp.json();
      if (user.is_admin) {
        $('btn-admin').style.display = '';
      }
    } catch {
      window.location.href = '/login';
    }
  }

  /* ── Connectivity ── */
  function setConnected(ok) {
    $('conn-dot').className = 'dot ' + (ok ? 'dot-green' : 'dot-red');
    $('conn-dot').title = ok ? 'Connected to qBittorrent' : 'Disconnected';
  }

  function setSpinning(v) {
    document.querySelector('.header-right').classList.toggle('spinning', v);
  }

  function showError(msg) {
    $('error-bar').style.display = msg ? 'block' : 'none';
    $('error-bar').textContent = msg;
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
        window.location.href = '/login';
        return;
      }

      if (!torrentsResp.ok || !transferResp.ok) {
        throw new Error('Failed to fetch data');
      }

      torrents = await torrentsResp.json();
      const transfer = await transferResp.json();

      updateStats(transfer);
      setConnected(true);
      showError('');
    } catch (e) {
      showError('Cannot reach qBittorrent: ' + e.message);
      setConnected(false);
    } finally {
      setSpinning(false);
    }
    render();
  }

  /* ── Stats bar ── */
  function updateStats(t) {
    $('s-dl').textContent = fmtSpeed(t.dl_info_speed);
    $('s-ul').textContent = fmtSpeed(t.up_info_speed);
    $('s-active').textContent = torrents.filter((x) =>
      ['downloading', 'forcedDL', 'checking', 'checkingDL', 'checkingUP'].includes(x.state)
    ).length;
    $('s-seed').textContent = torrents.filter((x) =>
      ['uploading', 'forcedUP', 'seeding'].includes(x.state)
    ).length;
    $('s-paused').textContent = torrents.filter((x) =>
      ['pausedDL', 'pausedUP'].includes(x.state)
    ).length;
  }

  /* ── Render ── */
  function getFiltered() {
    return torrents.filter((t) => {
      if (filterState !== 'all') {
        const c = stateClass(t.state);
        if (filterState !== c) return false;
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

    if (!list.length) {
      tbody.innerHTML = '';
      empty.style.display = 'block';
      return;
    }
    empty.style.display = 'none';

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
          '<td class="num">' + fmtRatio(t.ratio) + '</td>' +
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
      th.querySelector('.sort-icon').textContent = sortDir === -1 ? '\u2193' : '\u2191';
      render();
    });
  });

  /* ── Filter ── */
  document.querySelectorAll('.filter-btn').forEach((btn) => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.filter-btn').forEach((b) => b.classList.remove('active'));
      btn.classList.add('active');
      filterState = btn.dataset.filter;
      render();
    });
  });

  /* ── Search ── */
  $('search').addEventListener('input', (e) => {
    searchQ = e.target.value.toLowerCase().trim();
    render();
  });

  /* ── Refresh ── */
  function startRefreshLoop() {
    clearInterval(refreshTimer);
    clearInterval(countdownTimer);
    countdown = INTERVAL;
    countdownTimer = setInterval(() => {
      countdown--;
      $('refresh-info').textContent = 'Refresh in ' + countdown + 's';
      if (countdown <= 0) countdown = INTERVAL;
    }, 1000);
    refreshTimer = setInterval(() => {
      fetchData();
      countdown = INTERVAL;
    }, INTERVAL * 1000);
  }

  function doRefresh() {
    fetchData();
    startRefreshLoop();
  }

  $('btn-refresh').addEventListener('click', doRefresh);

  /* ── Logout ── */
  $('btn-logout').addEventListener('click', async () => {
    await fetch('/api/auth/logout', { method: 'POST' });
    window.location.href = '/login';
  });

  /* ── Boot ── */
  checkAuth().then(() => {
    doRefresh();
  });
})();
