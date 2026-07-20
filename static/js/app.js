/* app.js — LikeGod.net application core.
   Owns: API wrapper, session user, toasts, modals, header/footer rendering,
   shared UI helpers, and per-page controllers (App.pages[...]).
   Bootstraps via App.start(pageName) from each template's inline init.

   Backend contract notes honoured here:
   - user.role === 'admin' (no is_admin), user.avatar (no avatar_url)
   - deposit returns { pay_url }, withdraw body uses `address`
   - news uses image_path/btn_text/btn_url, tariffs use discount_text
   - duel create uses map_name; theme is int (0 dark / 1 light)
*/
window.App = (() => {
  const t = (k, p) => window.I18n.t(k, p);
  const MAPS = ['aim_redline', 'aim_ag_texture', 'awp_india'];

  const state = { user: null, commission: 10 };

  /* ---------------- SVG icons (inline, no emoji) ---------------- */
  const icons = {
    menu: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M4 7h16M4 12h16M4 17h16"/></svg>',
    close: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M6 6l12 12M18 6L6 18"/></svg>',
    sun: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M2 12h2M20 12h2M5 5l1.5 1.5M17.5 17.5L19 19M19 5l-1.5 1.5M6.5 17.5L5 19"/></svg>',
    moon: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z"/></svg>',
    logout: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4M16 17l5-5-5-5M21 12H9"/></svg>',
    steam: '<svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M12 2C6.6 2 2.2 6.2 2 11.5l5.3 2.2a2.9 2.9 0 0 1 1.7-.5l2.4-3.4v-.1a3.9 3.9 0 1 1 3.9 3.9h-.1l-3.4 2.4a2.9 2.9 0 0 1-5.7.8L2.3 15A10 10 0 1 0 12 2zM8.4 17.6l-1.2-.5a2.2 2.2 0 0 0 4-.2 2.2 2.2 0 0 0-2.9-2.9l1.2.5a1.6 1.6 0 1 1-1.1 3.1zM17.3 9.5a2.6 2.6 0 1 0-2.6 2.6 2.6 2.6 0 0 0 2.6-2.6zm-4.6 0a2 2 0 1 1 2 2 2 2 0 0 1-2-2z"/></svg>',
    arrowL: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M15 18l-6-6 6-6"/></svg>',
    arrowR: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M9 18l6-6-6-6"/></svg>'
  };

  /* ---------------- utils ---------------- */
  function esc(str) {
    return String(str == null ? '' : str).replace(/[&<>"']/g, (c) =>
      ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c])
    );
  }
  function money(v) { return '$' + Number(v || 0).toFixed(2); }
  function rankLabel(rank) { return t('common.rank', { rank }); }
  function initial(name) { return (String(name || '?').trim()[0] || '?').toUpperCase(); }

  function avatarMarkup(url, name, cls) {
    const klass = 'avatar' + (cls ? ' ' + cls : '');
    if (url) return `<img class="${klass}" src="${esc(url)}" alt="${esc(name)}" loading="lazy">`;
    return `<span class="${klass} avatar-fallback">${esc(initial(name))}</span>`;
  }

  function statusBadge(status) {
    const s = esc(status);
    return `<span class="badge badge-${s}">${t('statuses.' + status)}</span>`;
  }

  function mapOptions(selected) {
    return MAPS.map((m) => `<option value="${m}"${m === selected ? ' selected' : ''}>${m}</option>`).join('');
  }
  function rankOptions(selected, withAll) {
    let out = withAll ? `<option value="">${t('duels.filters.allRanks')}</option>` : '';
    for (let i = 1; i <= 10; i++) out += `<option value="${i}"${String(i) === String(selected) ? ' selected' : ''}>${t('common.rank', { rank: i })}</option>`;
    return out;
  }

  /* ---------------- API ---------------- */
  async function api(method, url, body) {
    const opts = {
      method,
      credentials: 'include',
      headers: { Accept: 'application/json' }
    };
    if (body !== undefined) {
      opts.headers['Content-Type'] = 'application/json';
      opts.body = JSON.stringify(body);
    }
    const res = await fetch(url, opts);
    let data = null;
    const text = await res.text();
    if (text) { try { data = JSON.parse(text); } catch (_) { data = text; } }
    if (!res.ok) {
      const detail = data && data.detail ? data.detail : t('common.errors.genericError');
      const err = new Error(typeof detail === 'string' ? detail : t('common.errors.genericError'));
      err.status = res.status;
      throw err;
    }
    return data;
  }

  /* ---------------- toasts ---------------- */
  function toast(message, type) {
    const box = document.getElementById('toast-container');
    if (!box) return;
    const el = document.createElement('div');
    el.className = 'toast' + (type ? ' ' + type : '');
    el.textContent = message;
    box.appendChild(el);
    setTimeout(() => {
      el.style.opacity = '0';
      setTimeout(() => el.remove(), 200);
    }, 3200);
  }

  /* ---------------- modal ---------------- */
  function openModal(html) {
    const backdrop = document.getElementById('modal-backdrop');
    const content = document.getElementById('modal-content');
    if (!backdrop || !content) return;
    content.innerHTML = html;
    backdrop.classList.remove('hidden');
    content.querySelectorAll('[data-close]').forEach((b) => b.addEventListener('click', closeModal));
  }
  function closeModal() {
    const backdrop = document.getElementById('modal-backdrop');
    const content = document.getElementById('modal-content');
    if (!backdrop) return;
    backdrop.classList.add('hidden');
    if (content) content.innerHTML = '';
  }

  function paymentModalSkeleton(mode) {
    const isWithdraw = mode === 'withdraw';
    const title = isWithdraw ? t('common.modal.withdrawTitle') : t('common.modal.depositTitle');
    const text = isWithdraw ? t('common.modal.withdrawText') : t('common.modal.depositText');
    const telegram = isWithdraw
      ? `<div class="form-group">
           <label class="form-label">${t('common.modal.telegram')}</label>
           <input id="pay-telegram" class="form-input" placeholder="${t('common.modal.telegramPlaceholder')}">
           <p class="method-meta">${t('common.modal.withdrawNotice')}</p>
         </div>` : '';
    const cta = isWithdraw ? t('common.actions.requestPayout') : t('common.actions.generateInvoice');
    return `
      <div class="modal-header">
        <div>
          <span class="eyebrow">${t('common.modal.billingEyebrow')}</span>
          <h3>${title}</h3>
          <p>${text}</p>
        </div>
        <button class="icon-btn" data-close aria-label="${t('common.actions.close')}">${icons.close}</button>
      </div>
      <div class="modal-body">
        <div class="form-group">
          <label class="form-label">${t('common.modal.method')}</label>
          <div id="pay-methods" class="method-list"></div>
        </div>
        <div class="form-group">
          <label class="form-label">${t('common.modal.amount')}</label>
          <input id="pay-amount" class="form-input" type="number" min="1" step="0.01" placeholder="0.00">
        </div>
        ${telegram}
      </div>
      <div class="modal-footer">
        <button class="btn-secondary" data-close>${t('common.actions.close')}</button>
        <button id="pay-submit" class="btn">${cta}</button>
      </div>`;
  }

  function renderDepositModal() {
    if (!requireAuth()) return;
    openModal(paymentModalSkeleton('deposit'));
    window.Payments.initModal('deposit', document.getElementById('modal-content'));
  }
  function renderWithdrawModal() {
    if (!requireAuth()) return;
    openModal(paymentModalSkeleton('withdraw'));
    window.Payments.initModal('withdraw', document.getElementById('modal-content'));
  }

  function requireAuth() {
    if (!state.user) { toast(t('common.errors.authRequired'), 'error'); return false; }
    return true;
  }

  /* ---------------- header ---------------- */
  function navLink(href, label, active) {
    return `<a class="nav-link${active ? ' active' : ''}" href="${href}">${label}</a>`;
  }

  function renderHeader() {
    const root = document.getElementById('header-root');
    if (!root) return;
    const path = location.pathname;
    const u = state.user;

    const links = [
      navLink('/main', t('common.nav.home'), path === '/main' || path === '/'),
      navLink('/duels', t('common.nav.duels'), path === '/duels' || path === '/duel'),
      navLink('/premium', t('common.nav.premium'), path === '/premium')
    ];
    if (u) links.push(navLink('/p/' + encodeURIComponent(u.username), t('common.nav.profile'), path.startsWith('/p/')));
    if (u && u.role === 'admin') links.push(navLink('/admin', t('common.nav.admin'), path === '/admin'));

    const themeIcon = window.Theme.current === 'dark' ? icons.sun : icons.moon;

    let actions = '';
    if (u) {
      actions += `<span class="balance-chip desktop-only"><span>${t('common.nav.balance')}</span>${money(u.balance)}</span>`;
      actions += `<button class="btn btn-sm desktop-only" id="hdr-deposit">${t('common.nav.deposit')}</button>`;
      actions += `<a class="avatar-link" href="/p/${encodeURIComponent(u.username)}">${avatarMarkup(u.avatar, u.username)}</a>`;
      actions += `<a class="icon-btn" href="/auth/logout" title="${t('common.nav.logout')}" aria-label="${t('common.nav.logout')}">${icons.logout}</a>`;
    } else {
      actions += `<a class="btn btn-steam" href="/auth/steam">${icons.steam}<span class="desktop-only">${t('common.nav.loginSteam')}</span></a>`;
    }

    root.innerHTML = `
      <header class="site-header">
        <div class="header-inner">
          <a class="brand" href="/main">
            <span class="brand-mark">L</span>
            <span class="brand-text">
              <span class="brand-name">LikeGod.net</span>
              <span class="brand-sub">${t('common.brandSubtitle')}</span>
            </span>
          </a>
          <nav class="main-nav" id="main-nav">${links.join('')}</nav>
          <div class="header-actions">
            <div class="lang-switch">
              <button class="icon-btn" id="lang-toggle" aria-label="${t('common.nav.language')}"><span class="lang-code">${window.I18n.current.toUpperCase()}</span></button>
              <div class="lang-menu hidden" id="lang-menu">
                ${window.I18n.OPTIONS.map((o) => `<button data-lang="${o.code}" class="${o.code === window.I18n.current ? 'active' : ''}"><span class="lang-code">${o.label}</span>${o.name}</button>`).join('')}
              </div>
            </div>
            <button class="icon-btn" id="theme-toggle" aria-label="${t('common.nav.theme')}">${themeIcon}</button>
            ${actions}
            <button class="icon-btn hamburger" id="hamburger" aria-label="${t('common.nav.menu')}">${icons.menu}</button>
          </div>
        </div>
      </header>`;

    wireHeader();
  }

  function wireHeader() {
    const hamburger = document.getElementById('hamburger');
    const nav = document.getElementById('main-nav');
    if (hamburger && nav) hamburger.addEventListener('click', () => nav.classList.toggle('open'));

    const themeToggle = document.getElementById('theme-toggle');
    if (themeToggle) themeToggle.addEventListener('click', () => { window.Theme.toggle(); renderHeader(); });

    const langToggle = document.getElementById('lang-toggle');
    const langMenu = document.getElementById('lang-menu');
    if (langToggle && langMenu) {
      langToggle.addEventListener('click', (e) => { e.stopPropagation(); langMenu.classList.toggle('hidden'); });
      langMenu.querySelectorAll('[data-lang]').forEach((b) => {
        b.addEventListener('click', async () => {
          await window.I18n.setLanguage(b.dataset.lang);
          if (state.user) api('POST', '/user/update', { language: b.dataset.lang }).catch(() => {});
          renderHeader();
          renderFooter();
          const controller = App.pages[App._page];
          if (controller) controller();
        });
      });
      document.addEventListener('click', () => langMenu.classList.add('hidden'));
    }

    const dep = document.getElementById('hdr-deposit');
    if (dep) dep.addEventListener('click', renderDepositModal);
  }

  /* ---------------- footer ---------------- */
  function renderFooter() {
    const root = document.getElementById('footer-root');
    if (!root) return;
    root.innerHTML = `
      <footer class="site-footer">
        <div class="container">
          <div class="footer-grid">
            <div>
              <a class="brand" href="/main">
                <span class="brand-mark">L</span>
                <span class="brand-text"><span class="brand-name">LikeGod.net</span></span>
              </a>
              <p class="footer-desc">${t('footer.description')}</p>
              <p class="method-meta">${t('footer.entity')}</p>
            </div>
            <div>
              <div class="footer-links">
                <a href="/terms">${t('footer.terms')}</a>
                <a href="/privacy">${t('footer.privacy')}</a>
                <a href="/refund">${t('footer.refund')}</a>
              </div>
            </div>
          </div>
          <div class="footer-bottom">
            <span>${t('footer.copy')}</span>
          </div>
        </div>
      </footer>`;
  }

  /* ---------------- modal backdrop wiring ---------------- */
  function wireGlobalModal() {
    const backdrop = document.getElementById('modal-backdrop');
    if (backdrop) {
      backdrop.addEventListener('click', (e) => { if (e.target === backdrop) closeModal(); });
    }
    document.addEventListener('keydown', (e) => { if (e.key === 'Escape') closeModal(); });
  }

  /* ---------------- bootstrap ---------------- */
  async function loadUser() {
    try { state.user = await api('GET', '/user/me'); }
    catch (_) { state.user = null; }
    return state.user;
  }

  async function start(page) {
    App._page = page;
    await window.I18n.loadLocale(window.I18n.detect());
    await loadUser();
    window.Theme.init(state.user);
    window.Effects.init();
    renderHeader();
    renderFooter();
    wireGlobalModal();
    window.I18n.applyI18n(document);
    App.user = state.user;
    const controller = App.pages[page];
    if (controller) {
      try { await controller(); }
      catch (err) {
        console.error('[page]', page, err);
        App.toast(window.I18n ? window.I18n.t('common.errors.genericError') : 'Failed to load page content', 'error');
      }
    }
    window.I18n.applyI18n(document);
  }

  return {
    _page: null,
    pages: {},
    icons,
    MAPS,
    state,
    user: null,
    api,
    toast,
    openModal,
    closeModal,
    renderHeader,
    renderFooter,
    renderDepositModal,
    renderWithdrawModal,
    requireAuth,
    // helpers exposed to page controllers
    t,
    esc,
    money,
    rankLabel,
    statusBadge,
    avatarMarkup,
    mapOptions,
    rankOptions,
    start
  };
})();

/* ============================================================
   PAGE CONTROLLERS
   ============================================================ */

/* ---------- HOME ---------- */
App.pages.home = async function () {
  const A = App, t = A.t;
  const u = A.state.user;

  // session card
  const session = document.getElementById('session-card');
  if (session) {
    if (u) {
      session.innerHTML = `
        <span class="eyebrow">${t('home.hero.statusEyebrow')}</span>
        <div class="session-head">
          ${A.avatarMarkup(u.avatar, u.username)}
          <div>
            <h3>${A.esc(u.username)}</h3>
            <span class="method-meta">${A.rankLabel(u.rank)} · ${u.is_premium ? t('premium.status.title') : t('profile.hero.standard')}</span>
          </div>
        </div>
        <div class="session-metrics">
          <div class="metric"><div class="metric-label">${t('common.labels.balance')}</div><div class="metric-value is-gold">${A.money(u.balance)}</div></div>
          <div class="metric"><div class="metric-label">${t('common.labels.elo')}</div><div class="metric-value">${u.elo}</div></div>
        </div>`;
    } else {
      session.innerHTML = `
        <span class="eyebrow">${t('home.hero.statusEyebrow')}</span>
        <h3>${t('home.hero.guestTitle')}</h3>
        <p style="margin:12px 0">${t('home.hero.guestText')}</p>
        <p class="method-meta" style="margin-bottom:20px">${t('home.hero.guestValue')}</p>
        <a class="btn btn-steam btn-block" href="/auth/steam">${A.icons.steam}${t('common.nav.loginSteam')}</a>`;
    }
  }

  // hero CTA wiring
  const depBtn = document.getElementById('hero-deposit');
  if (depBtn) depBtn.addEventListener('click', A.renderDepositModal);

  // live lobbies
  const grid = document.getElementById('live-lobbies');
  if (grid) {
    grid.innerHTML = Array(3).fill('<div class="skeleton"></div>').join('');
    try {
      const duels = await A.api('GET', '/api/v1/duels');
      const top = (duels || []).slice(0, 3);
      if (!top.length) {
        grid.innerHTML = `<div class="state-card" style="grid-column:1/-1">${t('common.states.emptyDuels')}</div>`;
      } else {
        grid.innerHTML = top.map(duelCard).join('');
        wireDuelCards(grid);
      }
    } catch (_) {
      grid.innerHTML = `<div class="state-card" style="grid-column:1/-1">${t('common.errors.genericError')}</div>`;
    }
  }

  // create duel (auth only)
  const createSection = document.getElementById('create-section');
  if (createSection) {
    if (!u) { createSection.classList.add('hidden'); }
    else {
      createSection.classList.remove('hidden');
      const mapSel = document.getElementById('cd-map');
      const minSel = document.getElementById('cd-min');
      const maxSel = document.getElementById('cd-max');
      if (mapSel) mapSel.innerHTML = A.mapOptions('aim_redline');
      if (minSel) minSel.innerHTML = A.rankOptions(1, false);
      if (maxSel) maxSel.innerHTML = A.rankOptions(10, false);
      const btn = document.getElementById('cd-submit');
      if (btn) btn.addEventListener('click', async () => {
        const bank = parseFloat(document.getElementById('cd-bank').value);
        const map = document.getElementById('cd-map').value;
        const min = parseInt(document.getElementById('cd-min').value, 10);
        const max = parseInt(document.getElementById('cd-max').value, 10);
        if (!bank || bank <= 0) { A.toast(t('common.errors.invalidAmount'), 'error'); return; }
        btn.disabled = true;
        try {
          const res = await A.api('POST', '/api/v1/duels', { total_bank: bank, map_name: map, min_rank: min, max_rank: max });
          if (res && res.duel_id) location.href = '/duel?id=' + res.duel_id;
        } catch (err) { A.toast(err.message, 'error'); }
        finally { btn.disabled = false; }
      });
    }
  }

  // news carousel
  const newsRoot = document.getElementById('news-root');
  if (newsRoot) {
    try {
      const news = await A.api('GET', '/news');
      if (!news || !news.length) {
        newsRoot.innerHTML = `<div class="state-card">${t('common.states.emptyNews')}</div>`;
      } else {
        newsRoot.innerHTML = `
          <div class="slider">
            <div class="slider-viewport"><div class="slider-track">
              ${news.map(newsSlide).join('')}
            </div></div>
            <button class="slider-arrow prev" aria-label="prev">${A.icons.arrowL}</button>
            <button class="slider-arrow next" aria-label="next">${A.icons.arrowR}</button>
            <div class="slider-dots"></div>
          </div>`;
        window.Slider.create(newsRoot.querySelector('.slider'));
      }
    } catch (_) {
      newsRoot.innerHTML = `<div class="state-card">${t('common.states.emptyNews')}</div>`;
    }
  }
};

function newsSlide(n) {
  const A = App;
  const btn = n.btn_url && n.btn_text
    ? `<a class="btn btn-sm" href="${A.esc(n.btn_url)}" target="_blank" rel="noopener">${A.esc(n.btn_text)}</a>` : '';
  const img = n.image_path ? `<img src="${A.esc(n.image_path)}" alt="">` : '';
  return `<div class="slide"><div class="news-card">${img}
      <div class="news-card-body"><h3>${A.esc(n.title)}</h3>${btn}</div></div></div>`;
}

function duelCard(d) {
  const A = App;
  const own = A.state.user && A.state.user.username === d.creator_username;
  const disabled = !A.state.user || own;
  return `
    <div class="duel-card" data-id="${d.id}">
      <div class="duel-card-head">
        <span class="duel-map">${A.esc(d.map_name)}</span>
        ${A.statusBadge('waiting')}
      </div>
      <div class="duel-creator">
        ${A.avatarMarkup(null, d.creator_username)}
        <div>
          <div class="duel-creator-name">${A.esc(d.creator_username)}</div>
          <div class="duel-creator-rank">${A.rankLabel(d.creator_rank)} · ELO ${d.creator_elo}</div>
        </div>
      </div>
      <div class="duel-card-meta">
        <div class="duel-bank"><small>${A.t('common.labels.bank')}</small>${A.money(d.total_bank)}</div>
        <span class="badge">${A.t('common.rankRange', { min: d.min_rank, max: d.max_rank })}</span>
      </div>
      <div class="duel-card-foot">
        <a class="nav-link" href="/duel?id=${d.id}">${A.t('common.actions.open')}</a>
        <button class="btn btn-sm" data-join="${d.id}"${disabled ? ' disabled' : ''}>${A.t('common.actions.join')}</button>
      </div>
    </div>`;
}

function wireDuelCards(root) {
  root.querySelectorAll('[data-join]').forEach((b) => {
    b.addEventListener('click', () => { location.href = '/duel?id=' + b.dataset.join; });
  });
}

/* ---------- DUELS ---------- */
App.pages.duels = async function () {
  const A = App, t = A.t;
  const grid = document.getElementById('duels-grid');
  if (!grid) return;

  const fMap = document.getElementById('f-map');
  const fMin = document.getElementById('f-bankmin');
  const fMax = document.getElementById('f-bankmax');
  const fRank = document.getElementById('f-rank');
  const fSort = document.getElementById('f-sort');

  if (fMap) fMap.innerHTML = `<option value="">—</option>` + A.mapOptions('');
  if (fRank) fRank.innerHTML = A.rankOptions('', true);

  let all = [];

  function apply() {
    let list = all.slice();
    const map = fMap.value;
    const min = parseFloat(fMin.value);
    const max = parseFloat(fMax.value);
    const rank = fRank.value ? parseInt(fRank.value, 10) : null;
    if (map) list = list.filter((d) => d.map_name === map);
    if (!isNaN(min)) list = list.filter((d) => d.total_bank >= min);
    if (!isNaN(max)) list = list.filter((d) => d.total_bank <= max);
    if (rank) list = list.filter((d) => rank >= d.min_rank && rank <= d.max_rank);
    list.sort((a, b) => fSort.value === 'low' ? a.total_bank - b.total_bank : b.total_bank - a.total_bank);
    if (!list.length) {
      grid.innerHTML = `<div class="state-card" style="grid-column:1/-1">
        <h3>${t('common.states.emptyDuels')}</h3></div>`;
    } else {
      grid.innerHTML = list.map(duelCard).join('');
      wireDuelCards(grid);
    }
  }

  [fMap, fMin, fMax, fRank, fSort].forEach((el) => { if (el) el.addEventListener('input', apply); if (el) el.addEventListener('change', apply); });

  grid.innerHTML = Array(6).fill('<div class="skeleton"></div>').join('');
  try {
    all = await A.api('GET', '/api/v1/duels') || [];
    apply();
  } catch (_) {
    grid.innerHTML = `<div class="state-card" style="grid-column:1/-1">${t('common.errors.genericError')}</div>`;
  }
};

/* ---------- DUEL ROOM ---------- */
App.pages.duel = async function () {
  const A = App, t = A.t;
  const id = new URLSearchParams(location.search).get('id');
  const header = document.getElementById('duel-header');
  const vs = document.getElementById('duel-vs');
  const actions = document.getElementById('duel-actions');
  const reqPanel = document.getElementById('requests-panel');

  if (!id) {
    if (header) header.innerHTML = `<div class="state-card"><h3>${t('duel.invalidId')}</h3></div>`;
    return;
  }

  let duel;
  try { duel = await A.api('GET', '/api/v1/duels/' + id); }
  catch (err) { if (header) header.innerHTML = `<div class="state-card"><h3>${err.message}</h3></div>`; return; }

  const u = A.state.user;
  const isCreator = u && u.id === duel.creator_id;
  const isGuest = u && u.id === duel.guest_id;

  if (header) {
    header.innerHTML = `
      <span class="eyebrow">${t('duel.hero.eyebrow')} · #${duel.id}</span>
      <div style="display:flex;align-items:center;gap:16px;flex-wrap:wrap">
        <h1 style="margin:0">${A.esc(duel.map_name)}</h1>
        ${A.statusBadge(duel.status)}
      </div>
      <div class="duel-bank" style="margin-top:12px"><small>${t('duel.info.bank')}</small>${A.money(duel.total_bank)}</div>`;
  }

  if (vs) {
    const guestSlot = duel.guest_id
      ? `<div class="player-slot">
           ${A.avatarMarkup(null, duel.guest_username)}
           <div class="player-name">${A.esc(duel.guest_username)}</div>
           <div class="method-meta">${A.rankLabel(duel.guest_rank)} · ELO ${duel.guest_elo}</div>
           <div class="player-share">${A.money(duel.guest_share)}</div>
           <span class="method-meta">${t('duel.info.guestShare')}</span>
         </div>`
      : `<div class="player-slot open">
           <div class="player-name">${t('duel.slotOpen')}</div>
           <div class="method-meta">${t('duel.guestWaiting')}</div>
         </div>`;
    vs.innerHTML = `
      <div class="player-slot">
        ${A.avatarMarkup(null, duel.creator_username)}
        <div class="player-name">${A.esc(duel.creator_username)}</div>
        <div class="method-meta">${A.rankLabel(duel.creator_rank)} · ELO ${duel.creator_elo}</div>
        <div class="player-share">${A.money(duel.creator_share)}</div>
        <span class="method-meta">${t('duel.info.creatorShare')}</span>
      </div>
      <div class="vs-badge">VS</div>
      ${guestSlot}`;
  }

  if (actions) {
    const btns = [];
    if (u && !isCreator && !isGuest && duel.status === 'waiting') {
      btns.push(`<button class="btn" data-act="join">${t('duel.actions.join')}</button>`);
    }
    if (isCreator && duel.status === 'waiting') {
      btns.push(`<button class="btn-danger" data-act="cancel">${t('duel.actions.cancel')}</button>`);
    }
    if ((isCreator || isGuest) && ['ready', 'playing', 'processing'].includes(duel.status)) {
      btns.push(`<button class="btn" data-act="confirm">${t('duel.actions.confirm')}</button>`);
      btns.push(`<button class="btn-danger" data-act="dispute">${t('duel.actions.dispute')}</button>`);
    }
    actions.innerHTML = `
      <span class="eyebrow">${t('duel.actions.title')}</span>
      <p style="margin-bottom:16px">${t('duel.actions.subtitle')}</p>
      <div class="form-actions">${btns.length ? btns.join('') : `<span class="method-meta">${t('duel.actions.noActions')}</span>`}</div>`;

    actions.querySelectorAll('[data-act]').forEach((b) => {
      b.addEventListener('click', () => duelAction(b.dataset.act, duel.id));
    });
  }

  // requests panel (creator + waiting)
  if (reqPanel) {
    if (isCreator && duel.status === 'waiting') {
      reqPanel.classList.remove('hidden');
      reqPanel.innerHTML = `<span class="eyebrow">${t('duel.requests.title')}</span>
        <p style="margin-bottom:16px">${t('duel.requests.subtitle')}</p>
        <div class="stack-sm" id="requests-list"></div>`;
      try {
        const reqs = await A.api('GET', `/api/v1/duels/${id}/requests`);
        const list = document.getElementById('requests-list');
        if (!reqs || !reqs.length) list.innerHTML = `<div class="state-card">${t('common.states.emptyRequests')}</div>`;
        else {
          list.innerHTML = reqs.map((r) => `
            <div class="request-row">
              ${A.avatarMarkup(r.avatar, r.username)}
              <div class="req-name">${A.esc(r.username)}<br><span class="method-meta">${A.rankLabel(r.rank)} · ELO ${r.elo}</span></div>
              <button class="btn btn-sm" data-accept="${r.request_id}">${t('duel.requests.accept')}</button>
            </div>`).join('');
          list.querySelectorAll('[data-accept]').forEach((b) => {
            b.addEventListener('click', async () => {
              try { await A.api('POST', `/api/v1/requests/${b.dataset.accept}/accept`); A.toast(t('duel.toasts.accepted'), 'success'); setTimeout(() => location.reload(), 400); }
              catch (err) { A.toast(err.message, 'error'); }
            });
          });
        }
      } catch (_) {}
    } else {
      reqPanel.classList.add('hidden');
    }
  }
};

async function duelAction(act, id) {
  const A = App, t = A.t;
  try {
    if (act === 'join') { await A.api('POST', `/api/v1/duels/${id}/request`); A.toast(t('duel.toasts.requestSent'), 'success'); }
    else if (act === 'cancel') { await A.api('DELETE', `/api/v1/duels/${id}/cancel`); A.toast(t('duel.toasts.cancelled'), 'success'); setTimeout(() => location.href = "/duels", 400); return; }
    else if (act === 'confirm') { await A.api('POST', `/api/v1/duels/${id}/confirm`); A.toast(t('duel.toasts.confirmed'), 'success'); }
    else if (act === 'dispute') { await A.api('POST', `/api/v1/duels/${id}/dispute`); A.toast(t('duel.toasts.disputed'), 'success'); }
    setTimeout(() => location.reload(), 400);
  } catch (err) { A.toast(err.message, 'error'); }
}

/* ---------- PROFILE ---------- */
App.pages.profile = async function () {
  const A = App, t = A.t;
  const username = decodeURIComponent(location.pathname.split('/p/')[1] || '');
  const headerRoot = document.getElementById('profile-root');
  const statsRoot = document.getElementById('stats-root');
  const owner = document.getElementById('owner-sections');

  let profile;
  try { profile = await A.api('GET', '/user/by-name/' + encodeURIComponent(username)); }
  catch (err) { if (headerRoot) headerRoot.innerHTML = `<div class="state-card"><h3>${err.message}</h3></div>`; return; }

  const s = profile.stats;
  if (headerRoot) {
    headerRoot.innerHTML = `
      <div class="profile-header">
        ${A.avatarMarkup(profile.avatar, profile.username)}
        <div class="profile-id">
          <h1>${A.esc(profile.username)} ${profile.is_premium ? `<span class="badge badge-premium">${t('premium.status.title')}</span>` : ''}</h1>
          <p>${A.esc(profile.bio) || t('profile.hero.emptyBio')}</p>
          <span class="method-meta">${profile.is_premium ? t('premium.status.title') : t('profile.hero.standard')}</span>
        </div>
      </div>`;
  }

  if (statsRoot) {
    const cards = [
      [t('profile.stats.elo'), s.elo, true],
      [t('profile.stats.rank'), s.rank, false],
      [t('profile.stats.winrate'), s.winrate + '%', false],
      [t('profile.stats.duels'), s.duels, false],
      [t('profile.stats.wins'), s.wins, false],
      [t('profile.stats.kd'), (s.deaths ? (s.kills / s.deaths).toFixed(2) : s.kills.toFixed(2)), false]
    ];
    statsRoot.innerHTML = cards.map(([label, val, gold]) =>
      `<div class="stat-card"><div class="stat-value${gold ? ' is-gold' : ''}">${val}</div><div class="stat-label">${label}</div></div>`
    ).join('');
  }

  if (owner) {
    const me = A.state.user;
    if (!profile.is_own_profile || !me) { owner.classList.add('hidden'); return; }
    owner.classList.remove('hidden');
    renderBilling(me);
    renderHistory();
    renderSettings(me);
  }
};

function renderBilling(me) {
  const A = App, t = A.t;
  const root = document.getElementById('billing-root');
  if (!root) return;
  const inv = me.active_invoice;
  const invoiceWarn = inv
    ? `<div class="state-card" style="text-align:left;margin-top:16px">
         <strong>${t('profile.billing.activeInvoice')}</strong>
         <p>${t('profile.billing.activeInvoiceText', { amount: A.money(inv.amount) })}</p>
         <button class="btn-danger btn-sm" id="cancel-invoice" style="margin-top:12px">${t('profile.billing.cancelInvoice')}</button>
       </div>` : '';
  root.innerHTML = `
    <span class="eyebrow">${t('common.modal.billingEyebrow')}</span>
    <h2>${t('profile.billing.title')}</h2>
    <p style="margin-bottom:16px">${t('profile.billing.subtitle')}</p>
    <div class="metric" style="margin-bottom:16px"><div class="metric-label">${t('common.labels.balance')}</div><div class="metric-value is-gold">${A.money(me.balance)}</div></div>
    <div class="form-actions">
      <button class="btn" id="billing-deposit">${t('profile.billing.deposit')}</button>
      <button class="btn-secondary" id="billing-withdraw">${t('profile.billing.withdraw')}</button>
    </div>
    ${invoiceWarn}`;
  document.getElementById('billing-deposit').addEventListener('click', A.renderDepositModal);
  document.getElementById('billing-withdraw').addEventListener('click', A.renderWithdrawModal);
  const cancel = document.getElementById('cancel-invoice');
  if (cancel) cancel.addEventListener('click', async () => { if (await window.Payments.cancelInvoice()) setTimeout(() => location.reload(), 400); });
}

async function renderHistory() {
  const A = App, t = A.t;
  const root = document.getElementById('history-root');
  if (!root) return;
  root.innerHTML = `<span class="eyebrow">${t('profile.history.title')}</span>
    <h2>${t('profile.history.title')}</h2>
    <p style="margin-bottom:16px">${t('profile.history.subtitle')}</p>
    <div id="history-table"></div>`;
  const table = document.getElementById('history-table');
  try {
    const rows = await A.api('GET', '/api/v1/payments/history');
    if (!rows || !rows.length) { table.innerHTML = `<div class="state-card">${t('common.states.emptyHistory')}</div>`; return; }
    table.innerHTML = `
      <table class="data-table">
        <thead><tr>
          <th>${t('profile.history.columns.date')}</th>
          <th>${t('profile.history.columns.type')}</th>
          <th>${t('profile.history.columns.amount')}</th>
          <th>${t('profile.history.columns.destination')}</th>
          <th>${t('profile.history.columns.status')}</th>
        </tr></thead>
        <tbody>${rows.map((r) => `
          <tr>
            <td data-label="${t('profile.history.columns.date')}" class="mono">${A.esc(r.date)}</td>
            <td data-label="${t('profile.history.columns.type')}">${A.esc(r.type)}</td>
            <td data-label="${t('profile.history.columns.amount')}" class="mono gold">${Number(r.amount).toFixed(2)} ${A.esc(r.currency)}</td>
            <td data-label="${t('profile.history.columns.destination')}" class="mono">${A.esc(r.address || '—')}</td>
            <td data-label="${t('profile.history.columns.status')}">${A.esc(r.status)}</td>
          </tr>`).join('')}</tbody>
      </table>`;
  } catch (_) {
    table.innerHTML = `<div class="state-card">${t('common.states.emptyHistory')}</div>`;
  }
}

function renderSettings(me) {
  const A = App, t = A.t;
  const root = document.getElementById('settings-root');
  if (!root) return;
  const langOpts = window.I18n.OPTIONS.map((o) => `<option value="${o.code}"${o.code === window.I18n.current ? ' selected' : ''}>${o.name}</option>`).join('');
  const effectType = localStorage.getItem('likeagod.effects.type') || 'off';
  root.innerHTML = `
    <span class="eyebrow">${t('profile.settings.title')}</span>
    <h2>${t('profile.settings.title')}</h2>
    <p style="margin-bottom:16px">${t('profile.settings.subtitle')}</p>
    <div class="stack-sm">
      <div class="form-group">
        <label class="form-label">${t('profile.settings.language')}</label>
        <select class="form-select" id="set-lang">${langOpts}</select>
      </div>
      <div class="form-group">
        <label class="form-label">${t('profile.settings.theme')}</label>
        <label class="switch">
          <input type="checkbox" id="set-theme"${window.Theme.current === 'light' ? ' checked' : ''}>
          <span class="switch-track"></span>
          <span>${window.Theme.current === 'light' ? t('profile.settings.light') : t('profile.settings.dark')}</span>
        </label>
      </div>
      <div class="form-group">
        <label class="form-label">${t('profile.settings.effectType')}</label>
        <select class="form-select" id="set-effect">
          <option value="off"${effectType === 'off' ? ' selected' : ''}>${t('profile.settings.effectsOff')}</option>
          <option value="rain"${effectType === 'rain' ? ' selected' : ''}>${t('profile.settings.effectRain')}</option>
          <option value="snow"${effectType === 'snow' ? ' selected' : ''}>${t('profile.settings.effectSnow')}</option>
        </select>
      </div>
      <div class="form-group">
        <label class="form-label">${t('profile.settings.bio')}</label>
        <textarea class="form-textarea" id="set-bio" placeholder="${t('profile.settings.bioPlaceholder')}">${A.esc(me.bio)}</textarea>
      </div>
      <div class="form-actions">
        <button class="btn" id="set-save">${t('common.actions.save')}</button>
      </div>
    </div>`;

  document.getElementById('set-theme').addEventListener('change', () => { window.Theme.toggle(); App.renderHeader(); });
  document.getElementById('set-effect').addEventListener('change', (e) => window.Effects.start(e.target.value));
  document.getElementById('set-lang').addEventListener('change', (e) => {
    window.I18n.setLanguage(e.target.value)
      .then(() => { App.renderHeader(); App.renderFooter(); App.pages.profile(); })
      .catch((err) => { console.error('[profile] language change failed:', err); App.toast('Language change failed', 'error'); });
  });
  document.getElementById('set-save').addEventListener('click', async () => {
    const bio = document.getElementById('set-bio').value;
    const lang = document.getElementById('set-lang').value;
    const effects = document.getElementById('set-effect').value !== 'off';
    try {
      await A.api('POST', '/user/update', { bio, language: lang, theme: window.Theme.current === 'light' ? 1 : 0, effects });
      A.toast(t('common.toasts.saved'), 'success');
    } catch (err) { A.toast(err.message, 'error'); }
  });
}

/* ---------- ADMIN ---------- */
App.pages.admin = async function () {
  const A = App, t = A.t;
  const guard = document.getElementById('admin-guard');
  const content = document.getElementById('admin-content');
  const u = A.state.user;
  if (!u || u.role !== 'admin') {
    if (content) content.classList.add('hidden');
    if (guard) { guard.classList.remove('hidden'); guard.innerHTML = `<div class="state-card"><h3>${t('admin.errors.forbidden')}</h3></div>`; }
    return;
  }
  if (guard) guard.classList.add('hidden');
  if (content) content.classList.remove('hidden');

  // user adjustments
  const bindTarget = () => document.getElementById('adm-target').value.trim();
  document.getElementById('adm-balance').addEventListener('click', async () => {
    try { const r = await A.api('POST', '/api/v1/admin/adjust-balance', { target: bindTarget(), amount: parseFloat(document.getElementById('adm-amount').value) || 0 }); A.toast(r.message || t('common.toasts.saved'), 'success'); }
    catch (err) { A.toast(err.message, 'error'); }
  });
  document.getElementById('adm-elo').addEventListener('click', async () => {
    try { const r = await A.api('POST', '/api/v1/admin/adjust-elo', { target: bindTarget(), amount: parseInt(document.getElementById('adm-amount').value, 10) || 0 }); A.toast(r.message || t('common.toasts.saved'), 'success'); }
    catch (err) { A.toast(err.message, 'error'); }
  });

  // news composer
  document.getElementById('adm-news-submit').addEventListener('click', async () => {
    try {
      await A.api('POST', '/news/create', {
        title: document.getElementById('adm-news-title').value.trim(),
        image_path: document.getElementById('adm-news-image').value.trim(),
        btn_text: document.getElementById('adm-news-btntext').value.trim(),
        btn_url: document.getElementById('adm-news-btnurl').value.trim()
      });
      A.toast(t('admin.toasts.newsSaved'), 'success');
      loadAdminNews();
    } catch (err) { A.toast(err.message, 'error'); }
  });
  loadAdminNews();

  // tariffs
  document.getElementById('adm-tariff-submit').addEventListener('click', async () => {
    try {
      await A.api('POST', '/api/v1/admin/tariffs', {
        duration_months: parseInt(document.getElementById('adm-tariff-duration').value, 10) || 0,
        price: parseFloat(document.getElementById('adm-tariff-price').value) || 0,
        discount_text: document.getElementById('adm-tariff-discount').value.trim()
      });
      A.toast(t('admin.toasts.tariffSaved'), 'success');
    } catch (err) { A.toast(err.message, 'error'); }
  });

  // commission
  document.getElementById('adm-commission-submit').addEventListener('click', async () => {
    try {
      const r = await A.api('POST', '/api/v1/admin/commission', { commission_percent: parseFloat(document.getElementById('adm-commission').value) || 0 });
      A.toast(t('admin.toasts.commissionSaved') + ' ' + r.commission_percent + '%', 'success');
    } catch (err) { A.toast(err.message, 'error'); }
  });
};

async function loadAdminNews() {
  const A = App, t = A.t;
  const list = document.getElementById('adm-news-list');
  if (!list) return;
  try {
    const news = await A.api('GET', '/news');
    if (!news || !news.length) { list.innerHTML = `<div class="state-card">${t('common.states.emptyNews')}</div>`; return; }
    list.innerHTML = news.map((n) => `
      <div class="request-row">
        <div class="req-name">${A.esc(n.title)}</div>
        <button class="btn-danger btn-sm" data-del="${n.id}">${t('common.actions.delete')}</button>
      </div>`).join('');
    list.querySelectorAll('[data-del]').forEach((b) => b.addEventListener('click', async () => {
      try { await A.api('DELETE', '/news/' + b.dataset.del); A.toast(t('admin.toasts.newsDeleted'), 'success'); loadAdminNews(); }
      catch (err) { A.toast(err.message, 'error'); }
    }));
  } catch (_) {
    list.innerHTML = `<div class="state-card">${t('common.states.emptyNews')}</div>`;
  }
}

/* ---------- PREMIUM ---------- */
App.pages.premium = async function () {
  const A = App, t = A.t;
  const status = document.getElementById('premium-status');
  const grid = document.getElementById('tariff-grid');
  const u = A.state.user;

  if (status) {
    if (!u) status.innerHTML = `<div class="state-card"><p>${t('premium.status.guest')}</p></div>`;
    else if (u.is_premium) {
      const until = u.premium_until ? new Date(u.premium_until).toLocaleDateString() : '';
      status.innerHTML = `<div class="card-lg"><span class="badge badge-premium">${t('premium.status.title')}</span>
        <h2 style="margin-top:12px">${t('premium.status.active')} ${until}</h2></div>`;
    } else {
      status.innerHTML = `<div class="card-lg"><span class="eyebrow">${t('premium.status.title')}</span>
        <h2>${t('premium.status.inactive')}</h2></div>`;
    }
  }

  if (grid) {
    grid.innerHTML = Array(3).fill('<div class="skeleton"></div>').join('');
    try {
      const tariffs = await A.api('GET', '/api/v1/premium/tariffs');
      if (!tariffs || !tariffs.length) { grid.innerHTML = `<div class="state-card" style="grid-column:1/-1">${t('common.states.emptyTariffs')}</div>`; return; }
      grid.innerHTML = tariffs.map((tf) => `
        <div class="tariff-card card-lg">
          ${tf.discount_text ? `<span class="badge badge-gold">${A.esc(tf.discount_text)}</span>` : ''}
          <h3 style="margin:12px 0">${t('premium.cards.months', { months: tf.duration_months })}</h3>
          <div class="stat-value is-gold" style="text-align:left">${A.money(tf.price)}</div>
          <p style="margin:12px 0">${t('premium.cards.cardText')}</p>
          <button class="btn btn-block" data-buy="${tf.id}">${t('premium.cards.buy')}</button>
        </div>`).join('');
      grid.querySelectorAll('[data-buy]').forEach((b) => b.addEventListener('click', async () => {
        if (!A.requireAuth()) return;
        try { await A.api('POST', '/api/v1/premium/buy', { tariff_id: parseInt(b.dataset.buy, 10) }); A.toast(t('premium.toasts.purchased'), 'success'); setTimeout(() => location.reload(), 400); }
        catch (err) { A.toast(err.message, 'error'); }
      }));
    } catch (_) {
      grid.innerHTML = `<div class="state-card" style="grid-column:1/-1">${t('common.states.emptyTariffs')}</div>`;
    }
  }
};

/* legal pages need no controller — i18n only */
App.pages.legal = async function () {};
