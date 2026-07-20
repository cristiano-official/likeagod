window.LikeGodApp = (() => {
  const state = {
    landingData: null,
    user: null,
    translations: {},
    lang: 'en',
    theme: 0,
    paymentContext: { type: 'deposit', onSuccess: null },
    paymentMethods: [],
    selectedPaymentMethodId: null
  };

  const i18n = window.LikeGodI18n;
  const themeTools = window.LikeGodTheme;
  const effectsTools = window.LikeGodEffects;
  let globalUiBound = false;

  function t(key, params = {}) {
    return i18n.t(state.translations, key, params);
  }

  function escapeHtml(value) {
    return String(value ?? '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  function safeUrl(value, fallback = '#', options = {}) {
    const raw = String(value || '').trim();
    if (!raw) return fallback;
    if (raw.startsWith('#')) return options.allowHash ? raw : fallback;
    if (raw.startsWith('/')) return raw;
    if (options.allowDataImage && /^data:image\//i.test(raw)) return raw;

    try {
      const parsed = new URL(raw, window.location.origin);
      if (['http:', 'https:'].includes(parsed.protocol)) return parsed.href;
    } catch (error) {
      return fallback;
    }

    return fallback;
  }

  function getInitials(value) {
    const letters = String(value || '')
      .trim()
      .split(/\s+/)
      .filter(Boolean)
      .slice(0, 2)
      .map((chunk) => chunk[0]?.toUpperCase() || '')
      .join('');
    return letters || 'LG';
  }

  function avatarMarkup(name, imageUrl = '', className = 'avatar') {
    const safeName = escapeHtml(name || 'Player');
    const safeSrc = safeUrl(imageUrl, '', { allowDataImage: true });
    if (safeSrc) {
      return `<span class="${className}"><img src="${safeSrc}" alt="${safeName}"></span>`;
    }
    return `<span class="${className} ${className}--token" aria-hidden="true">${escapeHtml(getInitials(name))}</span>`;
  }

  function icon(name, className = '') {
    const cls = className ? ` class="${className}"` : '';
    const icons = {
      crosshair: `<svg${cls} viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="7"></circle><path d="M12 5V3M12 21v-2M19 12h2M3 12h2M17 7l1.5-1.5M5.5 18.5 7 17M17 17l1.5 1.5M5.5 5.5 7 7"></path></svg>`,
      wallet: `<svg${cls} viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M19 7V5a2 2 0 0 0-2-2H5a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2"></path><path d="M3 7h18v10H3z"></path><path d="M16 12h.01"></path></svg>`,
      swords: `<svg${cls} viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="m14.5 17.5 5-5"></path><path d="m3 21 6.5-6.5"></path><path d="m12 8 4-4 4 4-4 4"></path><path d="m8 12-4 4 4 4 4-4"></path><path d="m13 13 6 6"></path><path d="m5 5 6 6"></path></svg>`,
      shield: `<svg${cls} viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10Z"></path><path d="m9 12 2 2 4-4"></path></svg>`,
      trophy: `<svg${cls} viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M8 21h8"></path><path d="M12 17v4"></path><path d="M7 4h10v4a5 5 0 0 1-10 0V4Z"></path><path d="M17 5h3v2a4 4 0 0 1-4 4"></path><path d="M7 5H4v2a4 4 0 0 0 4 4"></path></svg>`,
      globe: `<svg${cls} viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="10"></circle><path d="M2 12h20"></path><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10Z"></path></svg>`,
      map: `<svg${cls} viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="m9 18 6-12"></path><path d="m10 4 6 3"></path><path d="m4 6 6-2v14l-6 2V6Z"></path><path d="m14 6 6-2v14l-6 2V6Z"></path></svg>`,
      coins: `<svg${cls} viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><ellipse cx="12" cy="6" rx="7" ry="3"></ellipse><path d="M5 6v6c0 1.7 3.1 3 7 3s7-1.3 7-3V6"></path><path d="M5 12v6c0 1.7 3.1 3 7 3s7-1.3 7-3v-6"></path></svg>`,
      chart: `<svg${cls} viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3 3v18h18"></path><path d="m19 9-5 5-4-4-3 3"></path></svg>`,
      clock: `<svg${cls} viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="10"></circle><path d="M12 6v6l4 2"></path></svg>`,
      sparkles: `<svg${cls} viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="m12 3 1.9 4.1L18 9l-4.1 1.9L12 15l-1.9-4.1L6 9l4.1-1.9L12 3Z"></path><path d="M5 19l.9 2L8 22l-2.1.9L5 25l-.9-2.1L2 22l2.1-.9L5 19Z"></path><path d="M19 14l1 2 2 1-2 1-1 2-1-2-2-1 2-1 1-2Z"></path></svg>`,
      menu: `<svg${cls} viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M4 7h16M4 12h16M4 17h16"></path></svg>`,
      chevronRight: `<svg${cls} viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="m9 18 6-6-6-6"></path></svg>`
    };
    return icons[name] || icons.chevronRight;
  }

  function formatMoney(value, currencySymbol = '$') {
    const number = Number(value || 0);
    return `${currencySymbol}${number.toFixed(2)}`;
  }

  function statusLabel(status) {
    return t(`statuses.${status}`) === `statuses.${status}` ? status : t(`statuses.${status}`);
  }

  function setButtonBusy(button, isBusy, label) {
    if (!button) return;
    if (isBusy) {
      button.dataset.originalHtml = button.innerHTML;
      button.disabled = true;
      button.innerHTML = `<span class="spinner" aria-hidden="true"></span><span>${escapeHtml(label || t('common.states.loading'))}</span>`;
      return;
    }
    button.disabled = false;
    if (button.dataset.originalHtml) button.innerHTML = button.dataset.originalHtml;
  }

  async function api(url, options = {}) {
    const response = await fetch(url, {
      credentials: 'same-origin',
      headers: {
        'Content-Type': 'application/json',
        ...(options.headers || {})
      },
      ...options
    });

    const contentType = response.headers.get('content-type') || '';
    const payload = contentType.includes('application/json') ? await response.json() : await response.text();

    if (!response.ok) {
      const message = payload?.detail || payload?.message || payload || t('common.errors.genericError');
      throw new Error(message);
    }

    return payload;
  }

  async function loadLandingData() {
    try {
      state.landingData = await api('/api/main', { headers: {} });
      state.user = state.landingData.user;
    } catch (error) {
      state.landingData = { authenticated: false, news: [], my_duels: [], user: null, stats: null };
      state.user = null;
    }
  }

  async function loadTranslations(lang) {
    const loaded = await i18n.loadTranslations(lang);
    state.translations = loaded.translations;
    state.lang = loaded.lang;
  }

  function applyTranslations(root = document) {
    i18n.applyTranslations(state.translations, root);
  }

  function languageOption(lang) {
    return i18n.languageOptions.find((option) => option.code === lang) || i18n.languageOptions[0];
  }

  function getSteamButtonLabel() {
    return t('common.nav.loginSteam');
  }

  function getWalletHref() {
    return state.user ? `/p/${encodeURIComponent(state.user.username)}` : '/premium';
  }

  function getHowHref() {
    return '/main#how-it-works';
  }

  function bindGlobalUiEvents() {
    if (globalUiBound) return;
    globalUiBound = true;

    document.addEventListener('click', (event) => {
      const languageSwitch = document.getElementById('language-switch');
      if (languageSwitch && !languageSwitch.contains(event.target)) {
        languageSwitch.classList.remove('is-open');
      }

      const openNav = document.getElementById('main-nav');
      const navToggle = document.getElementById('nav-toggle');
      if (openNav?.classList.contains('is-open') && !openNav.contains(event.target) && !navToggle?.contains(event.target)) {
        openNav.classList.remove('is-open');
      }

      const backdrop = event.target.closest('.modal-backdrop');
      if (backdrop && event.target === backdrop) {
        closeModal(backdrop.id);
      }
    });

    document.addEventListener('keydown', (event) => {
      if (event.key === 'Escape') {
        document.querySelectorAll('.modal-backdrop.is-open').forEach((modal) => modal.classList.remove('is-open'));
        document.body.classList.remove('modal-open');
      }
    });
  }

  function renderNavbar() {
    const mount = document.getElementById('navbar');
    if (!mount) return;

    const currentPath = window.location.pathname;
    const activeClass = (path) => (currentPath === path ? 'is-active' : '');
    const currentLanguage = languageOption(state.lang);
    const languageItems = i18n.languageOptions.map((option) => `
      <button type="button" class="language-option ${option.code === state.lang ? 'is-active' : ''}" data-language-option="${option.code}">
        <span>${option.flag}</span>
        <span>${escapeHtml(option.name)}</span>
      </button>
    `).join('');

    const authActions = state.user
      ? `
        <a class="wallet-chip" href="${getWalletHref()}">
          ${icon('wallet', 'wallet-chip__icon')}
          <span class="wallet-chip__copy">
            <small>${escapeHtml(t('common.nav.wallet'))}</small>
            <strong>${escapeHtml(formatMoney(state.user.balance || 0))}</strong>
          </span>
        </a>
        <button class="btn-ghost btn-ghost--compact" type="button" data-open-payment="deposit">${escapeHtml(t('common.nav.deposit'))}</button>
        ${state.user.role === 'admin' ? `<a class="nav-link ${activeClass('/admin')}" href="/admin">${escapeHtml(t('common.nav.admin'))}</a>` : ''}
        <a class="user-chip" href="${getWalletHref()}">
          ${avatarMarkup(state.user.username, state.user.avatar, 'avatar avatar--sm')}
          <span class="user-chip__name">${escapeHtml(state.user.username)}</span>
        </a>
        <a class="btn-ghost btn-ghost--compact" href="/auth/logout">${escapeHtml(t('common.nav.logout'))}</a>
      `
      : `
        <a class="steam-btn" href="/auth/steam" aria-label="${escapeHtml(getSteamButtonLabel())}">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M11.98 3C7.58 3 4 6.58 4 10.98c0 3.53 2.3 6.53 5.49 7.59l2.39 1A3.87 3.87 0 0 0 19.65 18a3.85 3.85 0 0 0-3.85-3.85h-.17l-1.69-2.43v-.04a4.7 4.7 0 1 0-4.7 4.7h.1l2.41 1.71c0 .06-.01.13-.01.2a2.6 2.6 0 0 1-2.43-1.7A6.98 6.98 0 0 1 5.99 11 6.99 6.99 0 0 1 17 5.3a6.96 6.96 0 0 1 1.98 4.84c0 .3-.02.59-.06.88a4.84 4.84 0 0 0-3.12-1.13A4.85 4.85 0 1 0 20.65 15c.23-.63.35-1.31.35-2.02C21 7.48 16.5 3 11.98 3Zm0 6.54a2.24 2.24 0 1 1 0 4.49 2.24 2.24 0 0 1 0-4.49Zm3.82 6.08a2.39 2.39 0 1 1 0 4.77 2.39 2.39 0 0 1 0-4.77Z"/></svg>
          <span>${escapeHtml(getSteamButtonLabel())}</span>
        </a>
      `;

    mount.innerHTML = `
      <div class="nav-shell">
        <button class="nav-toggle" type="button" id="nav-toggle" aria-label="${escapeHtml(t('common.nav.menu'))}">
          ${icon('menu', 'nav-toggle__icon')}
        </button>
        <div class="main-nav" id="main-nav">
          <div class="main-nav__inner">
            <nav class="nav-links">
              <a class="nav-link ${activeClass('/duels')}" href="/duels">${escapeHtml(t('common.nav.duels'))}</a>
              <a class="nav-link ${currentPath.startsWith('/p/') ? 'is-active' : ''}" href="${getWalletHref()}">${escapeHtml(t('common.nav.wallet'))}</a>
              <a class="nav-link" href="${getHowHref()}">${escapeHtml(t('common.nav.howItWorks'))}</a>
            </nav>
            <div class="nav-actions">
              <button type="button" class="theme-toggle ${state.theme === 1 ? 'is-light' : ''}" id="theme-toggle" aria-label="${escapeHtml(t('common.nav.theme'))}">
                <span class="theme-toggle__icons"><span>🌙</span><span>☀️</span></span>
                <span class="theme-toggle__knob"></span>
              </button>
              <div class="language-switch" id="language-switch">
                <button type="button" class="language-switch__trigger" id="language-trigger" aria-label="${escapeHtml(t('common.nav.language'))}">
                  <span>${currentLanguage.flag}</span>
                  <span>${escapeHtml(currentLanguage.label)}</span>
                </button>
                <div class="language-switch__menu" id="language-menu">${languageItems}</div>
              </div>
              ${authActions}
            </div>
          </div>
        </div>
      </div>
    `;

    mount.querySelectorAll('[data-open-payment]').forEach((button) => {
      button.addEventListener('click', () => openPaymentModal(button.dataset.openPayment));
    });

    document.getElementById('theme-toggle')?.addEventListener('click', async () => {
      await setTheme(state.theme === 1 ? 0 : 1, true);
    });

    const navToggle = document.getElementById('nav-toggle');
    const nav = document.getElementById('main-nav');
    navToggle?.addEventListener('click', () => nav?.classList.toggle('is-open'));
    nav?.querySelectorAll('a').forEach((link) => link.addEventListener('click', () => nav.classList.remove('is-open')));

    const languageSwitch = document.getElementById('language-switch');
    const languageTrigger = document.getElementById('language-trigger');
    const languageMenu = document.getElementById('language-menu');

    languageTrigger?.addEventListener('click', () => languageSwitch?.classList.toggle('is-open'));
    languageMenu?.querySelectorAll('[data-language-option]').forEach((optionButton) => {
      optionButton.addEventListener('click', async () => {
        languageSwitch.classList.remove('is-open');
        await setLanguage(optionButton.dataset.languageOption);
      });
    });
  }

  function renderFooter() {
    const mount = document.getElementById('footer-shell');
    if (!mount) return;

    mount.innerHTML = `
      <div class="site-footer__inner">
        <div class="footer-brand">
          <a class="brand brand--footer" href="/main">
            <span class="brand__mark">LG</span>
            <span class="brand__text">
              <span class="brand__title">LIKE<span class="brand__title-accent">GOD</span></span>
              <span class="brand__subtitle">LIKEGOD.NET</span>
            </span>
          </a>
          <p class="footer-note" data-i18n="footer.description"></p>
        </div>
        <div class="site-footer__links">
          <a class="inline-link" href="/duels">${escapeHtml(t('common.nav.duels'))}</a>
          <a class="inline-link" href="${getWalletHref()}">${escapeHtml(t('common.nav.wallet'))}</a>
          <a class="inline-link" href="${getHowHref()}">${escapeHtml(t('common.nav.howItWorks'))}</a>
          <a class="inline-link" href="/terms" data-i18n="footer.terms"></a>
          <a class="inline-link" href="/privacy" data-i18n="footer.privacy"></a>
          <a class="inline-link" href="/refund" data-i18n="footer.refund"></a>
        </div>
        <div class="footer-meta">
          <p class="muted" data-i18n="footer.disclaimer"></p>
          <p class="muted" data-i18n="footer.copy"></p>
        </div>
      </div>
    `;
    applyTranslations(mount);
  }

  function ensureSharedUi() {
    bindGlobalUiEvents();

    if (!document.getElementById('toast-container')) {
      const toasts = document.createElement('div');
      toasts.id = 'toast-container';
      toasts.className = 'toast-container';
      document.body.appendChild(toasts);
    }

    if (!document.getElementById('shared-payment-modal')) {
      const wrapper = document.createElement('div');
      wrapper.innerHTML = `
        <div class="modal-backdrop" id="shared-payment-modal" aria-hidden="true">
          <div class="modal modal--sheet">
            <div class="modal__header">
              <div>
                <div class="section-title__eyebrow" data-i18n="common.modal.billingEyebrow"></div>
                <h3 id="payment-modal-title"></h3>
                <p class="page-subtitle" id="payment-modal-text"></p>
              </div>
              <button class="modal__close" type="button" data-close-modal="shared-payment-modal" aria-label="${escapeHtml(t('common.actions.close'))}">×</button>
            </div>
            <div class="form-fields">
              <div class="form-group">
                <label data-i18n="common.modal.method"></label>
                <div id="payment-method-cards" class="payment-method-grid"></div>
              </div>
              <div class="form-group">
                <label for="payment-amount-input" data-i18n="common.modal.amount"></label>
                <input id="payment-amount-input" class="input" type="number" min="1" step="0.5" value="10">
                <div class="chip-row chip-row--compact" id="payment-presets">
                  ${[5, 10, 25, 50, 100].map((amount) => `<button class="chip-button" type="button" data-payment-preset="${amount}">+${amount}</button>`).join('')}
                </div>
              </div>
              <div class="form-group" id="payment-address-group" hidden>
                <label for="payment-address-input" data-i18n="common.modal.telegram"></label>
                <input id="payment-address-input" class="input" type="text" data-i18n-placeholder="common.modal.telegramPlaceholder">
              </div>
              <div class="state-card state-card--warning" id="payment-warning" hidden data-i18n="common.modal.withdrawNotice"></div>
            </div>
            <div class="form-actions">
              <button class="btn" type="button" id="payment-submit-btn"></button>
              <button class="btn-ghost" type="button" data-close-modal="shared-payment-modal" data-i18n="common.actions.close"></button>
            </div>
          </div>
        </div>
        <div class="modal-backdrop" id="shared-payment-result-modal" aria-hidden="true">
          <div class="modal modal--compact">
            <div class="modal__header">
              <div>
                <div class="section-title__eyebrow" data-i18n="common.modal.invoiceReady"></div>
                <h3 data-i18n="common.modal.completePayment"></h3>
              </div>
              <button class="modal__close" type="button" data-close-modal="shared-payment-result-modal" aria-label="${escapeHtml(t('common.actions.close'))}">×</button>
            </div>
            <p class="page-subtitle" data-i18n="common.modal.invoiceText"></p>
            <div class="form-actions">
              <a class="btn" id="payment-result-link" href="#" target="_blank" rel="noreferrer" data-i18n="common.actions.pay"></a>
              <button class="btn-ghost" type="button" data-close-modal="shared-payment-result-modal" data-i18n="common.actions.close"></button>
            </div>
          </div>
        </div>
      `;
      document.body.appendChild(wrapper);
    }

    document.querySelectorAll('[data-close-modal]').forEach((button) => {
      button.onclick = () => closeModal(button.dataset.closeModal);
    });

    document.querySelectorAll('[data-payment-preset]').forEach((button) => {
      button.onclick = () => {
        const amount = Number(button.dataset.paymentPreset);
        document.getElementById('payment-amount-input').value = String(amount);
      };
    });
  }

  function openModal(id) {
    const modal = document.getElementById(id);
    if (!modal) return;
    modal.classList.add('is-open');
    modal.setAttribute('aria-hidden', 'false');
    document.body.classList.add('modal-open');
  }

  function closeModal(id) {
    const modal = document.getElementById(id);
    if (!modal) return;
    modal.classList.remove('is-open');
    modal.setAttribute('aria-hidden', 'true');
    if (!document.querySelector('.modal-backdrop.is-open')) {
      document.body.classList.remove('modal-open');
    }
  }

  function showToast(message, variant = 'info') {
    const container = document.getElementById('toast-container');
    if (!container) return;
    const toast = document.createElement('div');
    toast.className = `toast toast--${variant}`;
    toast.textContent = message;
    container.appendChild(toast);
    setTimeout(() => toast.remove(), 3600);
  }

  function renderPaymentMethods() {
    const cards = document.getElementById('payment-method-cards');
    if (!cards) return;
    cards.innerHTML = window.LikeGodPayments.renderMethodCards(state.paymentMethods, state.selectedPaymentMethodId);
    cards.querySelectorAll('[data-payment-method]').forEach((button) => {
      button.addEventListener('click', () => {
        state.selectedPaymentMethodId = Number(button.dataset.paymentMethod);
        renderPaymentMethods();
      });
    });
  }

  async function openPaymentModal(type = 'deposit', options = {}) {
    if (!state.user) {
      showToast(t('common.errors.authRequired'), 'warning');
      return;
    }

    try {
      state.paymentContext = { type, onSuccess: options.onSuccess || null };
      state.paymentMethods = await api(`/api/v1/payments/methods?type=${type}`, { headers: {} });
      state.selectedPaymentMethodId = state.paymentMethods[0]?.id || null;

      const modalTitle = document.getElementById('payment-modal-title');
      const modalText = document.getElementById('payment-modal-text');
      const submitButton = document.getElementById('payment-submit-btn');
      const addressGroup = document.getElementById('payment-address-group');
      const warning = document.getElementById('payment-warning');
      const amountInput = document.getElementById('payment-amount-input');
      const addressInput = document.getElementById('payment-address-input');

      amountInput.value = type === 'withdraw' ? '5' : '10';
      addressInput.value = '';

      if (type === 'withdraw') {
        modalTitle.textContent = t('common.modal.withdrawTitle');
        modalText.textContent = t('common.modal.withdrawText');
        submitButton.textContent = t('common.actions.requestPayout');
        addressGroup.hidden = false;
        warning.hidden = false;
      } else {
        modalTitle.textContent = t('common.modal.depositTitle');
        modalText.textContent = t('common.modal.depositText');
        submitButton.textContent = t('common.actions.generateInvoice');
        addressGroup.hidden = true;
        warning.hidden = true;
      }

      submitButton.onclick = submitPaymentModal;
      renderPaymentMethods();
      applyTranslations(document.getElementById('shared-payment-modal'));
      openModal('shared-payment-modal');
    } catch (error) {
      showToast(error.message, 'error');
    }
  }

  async function submitPaymentModal() {
    const submitButton = document.getElementById('payment-submit-btn');
    const methodId = Number(state.selectedPaymentMethodId);
    const amount = Number(document.getElementById('payment-amount-input').value || 0);
    const address = document.getElementById('payment-address-input').value.trim();
    const { type, onSuccess } = state.paymentContext;

    if (!amount || amount <= 0) {
      showToast(t('common.errors.invalidAmount'), 'warning');
      return;
    }

    if (!Number.isFinite(methodId) || methodId < 0) {
      showToast(t('common.errors.selectMethod'), 'warning');
      return;
    }

    setButtonBusy(submitButton, true, t('common.states.loading'));

    try {
      let payload;
      if (type === 'withdraw') {
        payload = await api('/api/v1/payments/withdraw', {
          method: 'POST',
          body: JSON.stringify({ amount, method_id: methodId, address })
        });
        showToast(payload.message || t('common.toasts.saved'), payload.status === 'failed' ? 'warning' : 'success');
      } else {
        payload = await api('/api/v1/payments/deposit', {
          method: 'POST',
          body: JSON.stringify({ amount, method_id: methodId })
        });
        if (payload.pay_url) {
          document.getElementById('payment-result-link').href = safeUrl(payload.pay_url, '#');
          openModal('shared-payment-result-modal');
        }
        showToast(t('common.toasts.invoiceCreated'), 'success');
      }

      closeModal('shared-payment-modal');
      if (typeof onSuccess === 'function') await onSuccess(payload);
      await refreshSession();
      renderNavbar();
    } catch (error) {
      showToast(error.message, 'error');
    } finally {
      setButtonBusy(submitButton, false);
    }
  }

  async function setLanguage(lang, sync = true) {
    await loadTranslations(lang);
    if (sync && state.user) {
      try {
        await api('/user/update', {
          method: 'POST',
          body: JSON.stringify({ language: state.lang })
        });
        state.user.language = state.lang;
      } catch (error) {
        showToast(error.message, 'warning');
      }
    }
    renderNavbar();
    renderFooter();
    applyTranslations();
    document.dispatchEvent(new CustomEvent('likeagod:language-changed', { detail: { lang: state.lang } }));
  }

  async function setTheme(theme, sync = false) {
    state.theme = themeTools.applyTheme(theme);
    if (state.user) state.user.theme = state.theme;
    renderNavbar();
    if (sync && state.user) {
      try {
        await api('/user/update', {
          method: 'POST',
          body: JSON.stringify({ theme: state.theme })
        });
      } catch (error) {
        showToast(error.message, 'warning');
      }
    }
    document.dispatchEvent(new CustomEvent('likeagod:theme-changed', { detail: { theme: state.theme } }));
  }

  async function setEffects(enabled, type = null, sync = false) {
    effectsTools.configure({ enabled, type });
    if (state.user) state.user.effects = Boolean(enabled);
    if (sync && state.user) {
      try {
        await api('/user/update', {
          method: 'POST',
          body: JSON.stringify({ effects: Boolean(enabled) })
        });
      } catch (error) {
        showToast(error.message, 'warning');
      }
    }
    document.dispatchEvent(new CustomEvent('likeagod:effects-changed', { detail: effectsTools.getState() }));
  }

  async function refreshSession() {
    await loadLandingData();
  }

  async function boot(options = {}) {
    ensureSharedUi();
    await loadLandingData();
    await loadTranslations(i18n.detectLanguage(state.user));

    state.theme = themeTools.resolveInitialTheme(state.user);
    themeTools.applyTheme(state.theme);

    const effectsInitial = effectsTools.resolveInitial(state.user);
    effectsTools.configure(effectsInitial);

    renderNavbar();
    renderFooter();
    applyTranslations();

    if (options.titleKey) document.title = t(options.titleKey);
    if (typeof options.onReady === 'function') await options.onReady();
  }

  return {
    api,
    avatarMarkup,
    boot,
    closeModal,
    escapeHtml,
    formatMoney,
    getInitials,
    icon,
    openModal,
    openPaymentModal,
    refreshSession,
    renderNavbar,
    safeUrl,
    setButtonBusy,
    setLanguage,
    setTheme,
    setEffects,
    showToast,
    state,
    statusLabel,
    t,
    applyTranslations,
    getUser: () => state.user,
    getLandingData: () => state.landingData,
    getTheme: () => state.theme,
    getEffectsState: () => effectsTools.getState()
  };
})();
