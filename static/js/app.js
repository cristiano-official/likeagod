window.LikeGodApp = (() => {
  const storageKey = 'likeagod.language';
  const supportedLanguages = ['en', 'ru', 'zh', 'es'];
  const languageOptions = [
    { code: 'en', label: 'EN', flag: '🇺🇸' },
    { code: 'ru', label: 'RU', flag: '🇷🇺' },
    { code: 'zh', label: 'ZH', flag: '🇨🇳' },
    { code: 'es', label: 'ES', flag: '🇪🇸' }
  ];

  const state = {
    landingData: null,
    user: null,
    translations: {},
    lang: 'en',
    paymentContext: { type: 'deposit', onSuccess: null }
  };

  function getNestedValue(source, path) {
    return path.split('.').reduce((acc, key) => (acc && acc[key] !== undefined ? acc[key] : undefined), source);
  }

  function interpolate(template, params = {}) {
    return String(template).replace(/\{(\w+)\}/g, (_, key) => params[key] ?? '');
  }

  function t(key, params = {}) {
    const value = getNestedValue(state.translations, key);
    if (typeof value === 'string') {
      return interpolate(value, params);
    }
    return key;
  }

  function formatMoney(value, currencySymbol = '$') {
    const number = Number(value || 0);
    return `${currencySymbol}${number.toFixed(2)}`;
  }

  function statusLabel(status) {
    return t(`statuses.${status}`) === `statuses.${status}` ? status : t(`statuses.${status}`);
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
      const message = payload?.detail || payload?.message || payload || t('common.genericError');
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

  function detectLanguage() {
    const stored = localStorage.getItem(storageKey);
    if (stored && supportedLanguages.includes(stored)) {
      return stored;
    }

    if (state.user?.language && supportedLanguages.includes(state.user.language)) {
      return state.user.language;
    }

    const browserLang = (navigator.language || 'en').slice(0, 2).toLowerCase();
    return supportedLanguages.includes(browserLang) ? browserLang : 'en';
  }

  async function loadTranslations(lang) {
    const selected = supportedLanguages.includes(lang) ? lang : 'en';
    const response = await fetch(`/static/i18n/${selected}.json`, { credentials: 'same-origin' });
    if (!response.ok) {
      if (selected !== 'en') {
        return loadTranslations('en');
      }
      throw new Error('Unable to load translations');
    }
    state.translations = await response.json();
    state.lang = selected;
    document.documentElement.lang = selected;
    localStorage.setItem(storageKey, selected);
  }

  function applyTranslations(root = document) {
    root.querySelectorAll('[data-i18n]').forEach((element) => {
      element.textContent = t(element.dataset.i18n);
    });

    root.querySelectorAll('[data-i18n-html]').forEach((element) => {
      element.innerHTML = t(element.dataset.i18nHtml);
    });

    root.querySelectorAll('[data-i18n-placeholder]').forEach((element) => {
      element.placeholder = t(element.dataset.i18nPlaceholder);
    });

    root.querySelectorAll('[data-i18n-title]').forEach((element) => {
      element.title = t(element.dataset.i18nTitle);
    });

    root.querySelectorAll('[data-i18n-value]').forEach((element) => {
      element.value = t(element.dataset.i18nValue);
    });
  }

  function getSteamButtonLabel() {
    return t('common.nav.loginSteam');
  }

  function renderNavbar() {
    const mount = document.getElementById('navbar');
    if (!mount) return;

    const currentPath = window.location.pathname;
    const activeClass = (path) => (currentPath === path ? 'is-active' : '');
    const languageOptionsHtml = languageOptions
      .map((option) => `<option value="${option.code}" ${state.lang === option.code ? 'selected' : ''}>${option.flag} ${option.label}</option>`)
      .join('');

    const authActions = state.user
      ? `
        <span class="balance-pill">${t('common.nav.balance')}: ${formatMoney(state.user.balance || 0)}</span>
        <button class="btn-ghost" type="button" data-open-payment="deposit">${t('common.nav.deposit')}</button>
        ${state.user.role === 'admin' ? `<a class="nav-link ${activeClass('/admin')}" href="/admin">${t('common.nav.admin')}</a>` : ''}
        <a class="nav-link ${activeClass(`/p/${state.user.username}`)}" href="/p/${state.user.username}">${t('common.nav.profile')}</a>
        <a class="nav-link" href="/auth/logout">${t('common.nav.logout')}</a>
      `
      : `
        <a class="steam-btn" href="/auth/steam" aria-label="${getSteamButtonLabel()}">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M11.98 3C7.58 3 4 6.58 4 10.98c0 3.53 2.3 6.53 5.49 7.59l2.39 1A3.87 3.87 0 0 0 19.65 18a3.85 3.85 0 0 0-3.85-3.85h-.17l-1.69-2.43v-.04a4.7 4.7 0 1 0-4.7 4.7h.1l2.41 1.71c0 .06-.01.13-.01.2a2.6 2.6 0 0 1-2.43-1.7A6.98 6.98 0 0 1 5.99 11 6.99 6.99 0 0 1 17 5.3a6.96 6.96 0 0 1 1.98 4.84c0 .3-.02.59-.06.88a4.84 4.84 0 0 0-3.12-1.13A4.85 4.85 0 1 0 20.65 15c.23-.63.35-1.31.35-2.02C21 7.48 16.5 3 11.98 3Zm0 6.54a2.24 2.24 0 1 1 0 4.49 2.24 2.24 0 0 1 0-4.49Zm3.82 6.08a2.39 2.39 0 1 1 0 4.77 2.39 2.39 0 0 1 0-4.77Z"/></svg>
          <span>${getSteamButtonLabel()}</span>
        </a>
      `;

    mount.innerHTML = `
      <div class="nav-shell">
        <button class="nav-toggle" type="button" id="nav-toggle" aria-label="${t('common.nav.menu')}">☰</button>
        <div class="main-nav" id="main-nav">
          <div class="nav-links">
            <a class="nav-link ${activeClass('/main')}" href="/main">${t('common.nav.home')}</a>
            <a class="nav-link ${activeClass('/duels')}" href="/duels">${t('common.nav.duels')}</a>
            <a class="nav-link ${activeClass('/premium')}" href="/premium">${t('common.nav.premium')}</a>
          </div>
          <div class="nav-actions">
            <select class="lang-select" id="lang-select" aria-label="${t('common.nav.language')}">${languageOptionsHtml}</select>
            ${authActions}
          </div>
        </div>
      </div>
    `;

    mount.querySelectorAll('[data-open-payment]').forEach((button) => {
      button.addEventListener('click', () => openPaymentModal(button.dataset.openPayment));
    });

    const navToggle = document.getElementById('nav-toggle');
    const nav = document.getElementById('main-nav');
    if (navToggle && nav) {
      navToggle.addEventListener('click', () => nav.classList.toggle('is-open'));
    }

    const langSelect = document.getElementById('lang-select');
    if (langSelect) {
      langSelect.addEventListener('change', async (event) => {
        await setLanguage(event.target.value);
      });
    }
  }

  function renderFooter() {
    const mount = document.getElementById('footer-shell');
    if (!mount) return;

    mount.innerHTML = `
      <div class="site-footer__inner">
        <div>
          <div class="brand__title">LIKEGOD.NET</div>
          <p class="page-subtitle" data-i18n="footer.description"></p>
          <p class="muted" data-i18n="footer.entity"></p>
        </div>
        <div class="site-footer__links">
          <a class="inline-link" href="/terms" data-i18n="footer.terms"></a>
          <a class="inline-link" href="/privacy" data-i18n="footer.privacy"></a>
          <a class="inline-link" href="/refund" data-i18n="footer.refund"></a>
        </div>
        <div>
          <div class="info-pill">Telegram: <a href="https://t.me/likeagod_support" target="_blank" rel="noreferrer">@likeagod_support</a></div>
          <p class="muted" data-i18n="footer.copy"></p>
        </div>
      </div>
    `;
    applyTranslations(mount);
  }

  function ensureSharedUi() {
    if (!document.getElementById('toast-container')) {
      const toasts = document.createElement('div');
      toasts.id = 'toast-container';
      toasts.className = 'toast-container';
      document.body.appendChild(toasts);
    }

    if (!document.getElementById('shared-payment-modal')) {
      const wrapper = document.createElement('div');
      wrapper.innerHTML = `
        <div class="modal-backdrop" id="shared-payment-modal">
          <div class="modal">
            <div class="modal__header">
              <div>
                <div class="section-title__eyebrow" data-i18n="common.modal.billingEyebrow"></div>
                <h3 id="payment-modal-title"></h3>
                <p class="page-subtitle" id="payment-modal-text"></p>
              </div>
              <button class="modal__close" type="button" data-close-modal="shared-payment-modal">×</button>
            </div>
            <div class="form-fields">
              <div class="form-group">
                <label for="payment-method-select" data-i18n="common.modal.method"></label>
                <select id="payment-method-select" class="select"></select>
              </div>
              <div class="form-group">
                <label for="payment-amount-input" data-i18n="common.modal.amount"></label>
                <input id="payment-amount-input" class="input" type="number" min="1" step="0.5" value="5">
              </div>
              <div class="form-group" id="payment-address-group" hidden>
                <label for="payment-address-input" data-i18n="common.modal.telegram"></label>
                <input id="payment-address-input" class="input" type="text" data-i18n-placeholder="common.modal.telegramPlaceholder">
              </div>
              <div class="state-card" id="payment-warning" hidden data-i18n="common.modal.withdrawNotice"></div>
            </div>
            <div class="form-actions" style="margin-top:18px;">
              <button class="btn" type="button" id="payment-submit-btn"></button>
              <button class="btn-ghost" type="button" data-close-modal="shared-payment-modal" data-i18n="common.actions.close"></button>
            </div>
          </div>
        </div>
        <div class="modal-backdrop" id="shared-payment-result-modal">
          <div class="modal">
            <div class="modal__header">
              <div>
                <div class="section-title__eyebrow" data-i18n="common.modal.invoiceReady"></div>
                <h3 data-i18n="common.modal.completePayment"></h3>
              </div>
              <button class="modal__close" type="button" data-close-modal="shared-payment-result-modal">×</button>
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
      button.addEventListener('click', () => closeModal(button.dataset.closeModal));
    });
  }

  function openModal(id) {
    document.getElementById(id)?.classList.add('is-open');
  }

  function closeModal(id) {
    document.getElementById(id)?.classList.remove('is-open');
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

  async function openPaymentModal(type = 'deposit', options = {}) {
    if (!state.user) {
      showToast(t('common.errors.authRequired'), 'warning');
      return;
    }

    try {
      state.paymentContext = { type, onSuccess: options.onSuccess || null };
      const methods = await api(`/api/v1/payments/methods?type=${type}`, { headers: {} });
      const select = document.getElementById('payment-method-select');
      const modalTitle = document.getElementById('payment-modal-title');
      const modalText = document.getElementById('payment-modal-text');
      const submitButton = document.getElementById('payment-submit-btn');
      const addressGroup = document.getElementById('payment-address-group');
      const warning = document.getElementById('payment-warning');

      select.innerHTML = methods.map((method) => `<option value="${method.id}">${method.name} • ${method.commission_label}</option>`).join('');

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
      applyTranslations(document.getElementById('shared-payment-modal'));
      openModal('shared-payment-modal');
    } catch (error) {
      showToast(error.message, 'error');
    }
  }

  async function submitPaymentModal() {
    const methodId = Number(document.getElementById('payment-method-select').value);
    const amount = Number(document.getElementById('payment-amount-input').value || 0);
    const address = document.getElementById('payment-address-input').value.trim();
    const { type, onSuccess } = state.paymentContext;

    if (!amount || amount <= 0) {
      showToast(t('common.errors.invalidAmount'), 'warning');
      return;
    }

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
          document.getElementById('payment-result-link').href = payload.pay_url;
          openModal('shared-payment-result-modal');
        }
        showToast(t('common.toasts.invoiceCreated'), 'success');
      }

      closeModal('shared-payment-modal');
      if (typeof onSuccess === 'function') {
        await onSuccess(payload);
      }
      await refreshSession();
      renderNavbar();
    } catch (error) {
      showToast(error.message, 'error');
    }
  }

  async function setLanguage(lang) {
    await loadTranslations(lang);
    if (state.user) {
      try {
        await api('/user/update', {
          method: 'POST',
          body: JSON.stringify({ language: lang })
        });
        state.user.language = lang;
      } catch (error) {
        showToast(error.message, 'warning');
      }
    }
    renderNavbar();
    renderFooter();
    applyTranslations();
    document.dispatchEvent(new CustomEvent('likeagod:language-changed', { detail: { lang } }));
  }

  async function refreshSession() {
    await loadLandingData();
  }

  async function boot(options = {}) {
    ensureSharedUi();
    await loadLandingData();
    await loadTranslations(detectLanguage());
    renderNavbar();
    renderFooter();
    applyTranslations();
    if (options.titleKey) {
      document.title = t(options.titleKey);
    }
    if (typeof options.onReady === 'function') {
      await options.onReady();
    }
  }

  return {
    api,
    boot,
    closeModal,
    formatMoney,
    openPaymentModal,
    refreshSession,
    renderNavbar,
    setLanguage,
    showToast,
    state,
    statusLabel,
    t,
    applyTranslations,
    getUser: () => state.user,
    getLandingData: () => state.landingData
  };
})();
