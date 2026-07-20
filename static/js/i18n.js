/* i18n.js — async locale loader with safe fallback.
   Public API on window.I18n:
     I18n.loadLocale(lang)  -> Promise, fetches /static/i18n/{lang}.json
     I18n.t(key, params)    -> string, NEVER returns a dotted path
     I18n.applyI18n(root)   -> processes data-i18n / data-i18n-html /
                               data-i18n-placeholder / data-i18n-title
     I18n.setLanguage(lang) -> load + apply, persists to localStorage
     I18n.current           -> active language code
*/
window.I18n = (() => {
  const STORAGE_KEY = 'likeagod.language';
  const SUPPORTED = ['en', 'ru', 'zh', 'es'];
  const OPTIONS = [
    { code: 'en', label: 'EN', name: 'English' },
    { code: 'ru', label: 'RU', name: 'Русский' },
    { code: 'zh', label: 'ZH', name: '中文' },
    { code: 'es', label: 'ES', name: 'Español' }
  ];

  let dict = {};
  let current = 'en';

  function nested(source, path) {
    return path.split('.').reduce(
      (acc, k) => (acc && acc[k] !== undefined ? acc[k] : undefined),
      source
    );
  }

  function interpolate(str, params) {
    return String(str).replace(/\{(\w+)\}/g, (_, k) =>
      params && params[k] !== undefined ? params[k] : ''
    );
  }

  // camelCase / dotted last-segment -> "Title Case"
  function humanize(key) {
    const last = String(key).split('.').pop() || key;
    const spaced = last
      .replace(/([a-z0-9])([A-Z])/g, '$1 $2')
      .replace(/[_-]+/g, ' ')
      .trim();
    return spaced.replace(/\b\w/g, (c) => c.toUpperCase());
  }

  function t(key, params) {
    if (!key) return '';
    const value = nested(dict, key);
    if (typeof value === 'string') return interpolate(value, params || {});
    // Missing key: warn (dev) and NEVER surface the dotted path.
    console.warn('[i18n] Missing key:', key);
    return humanize(key);
  }

  function detect(user) {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored && SUPPORTED.includes(stored)) return stored;
    if (user && user.language && SUPPORTED.includes(user.language)) return user.language;
    const browser = (navigator.language || 'en').slice(0, 2).toLowerCase();
    return SUPPORTED.includes(browser) ? browser : 'en';
  }

  async function loadLocale(lang) {
    const selected = SUPPORTED.includes(lang) ? lang : 'en';
    try {
      const res = await fetch(`/static/i18n/${selected}.json`, { credentials: 'same-origin' });
      if (!res.ok) throw new Error('load failed');
      dict = await res.json();
      current = selected;
    } catch (err) {
      if (selected !== 'en') return loadLocale('en');
      console.warn('[i18n] Failed to load dictionary', err);
      dict = {};
      current = 'en';
    }
    localStorage.setItem(STORAGE_KEY, current);
    document.documentElement.lang = current;
    return current;
  }

  function applyI18n(root) {
    const scope = root || document;

    scope.querySelectorAll('[data-i18n]').forEach((el) => {
      el.textContent = t(el.dataset.i18n);
    });
    scope.querySelectorAll('[data-i18n-html]').forEach((el) => {
      el.innerHTML = t(el.dataset.i18nHtml);
    });
    scope.querySelectorAll('[data-i18n-placeholder]').forEach((el) => {
      el.placeholder = t(el.dataset.i18nPlaceholder);
    });
    scope.querySelectorAll('[data-i18n-title]').forEach((el) => {
      el.title = t(el.dataset.i18nTitle);
    });
  }

  async function setLanguage(lang) {
    await loadLocale(lang);
    applyI18n(document);
    document.dispatchEvent(new CustomEvent('i18n:changed', { detail: { lang: current } }));
    return current;
  }

  return {
    STORAGE_KEY,
    SUPPORTED,
    OPTIONS,
    get current() { return current; },
    detect,
    loadLocale,
    applyI18n,
    setLanguage,
    t
  };
})();
