window.LikeGodI18n = (() => {
  const storageKey = 'likeagod.language';
  const supportedLanguages = ['en', 'ru', 'zh', 'es'];
  const languageOptions = [
    { code: 'en', label: 'EN', name: 'English', flag: '🇺🇸' },
    { code: 'ru', label: 'RU', name: 'Русский', flag: '🇷🇺' },
    { code: 'zh', label: 'ZH', name: '中文', flag: '🇨🇳' },
    { code: 'es', label: 'ES', name: 'Español', flag: '🇪🇸' }
  ];

  function getNestedValue(source, path) {
    return path.split('.').reduce((acc, key) => (acc && acc[key] !== undefined ? acc[key] : undefined), source);
  }

  function interpolate(template, params = {}) {
    return String(template).replace(/\{(\w+)\}/g, (_, key) => params[key] ?? '');
  }

  function detectLanguage(user) {
    const stored = localStorage.getItem(storageKey);
    if (stored && supportedLanguages.includes(stored)) return stored;
    if (user?.language && supportedLanguages.includes(user.language)) return user.language;
    const browserLang = (navigator.language || 'en').slice(0, 2).toLowerCase();
    return supportedLanguages.includes(browserLang) ? browserLang : 'en';
  }

  async function loadTranslations(lang) {
    const selected = supportedLanguages.includes(lang) ? lang : 'en';
    const response = await fetch(`/static/i18n/${selected}.json`, { credentials: 'same-origin' });
    if (!response.ok) {
      if (selected !== 'en') return loadTranslations('en');
      throw new Error('Unable to load translations');
    }
    const translations = await response.json();
    localStorage.setItem(storageKey, selected);
    document.documentElement.lang = selected;
    return { lang: selected, translations };
  }

  function t(translations, key, params = {}) {
    const value = getNestedValue(translations, key);
    if (typeof value === 'string') return interpolate(value, params);
    return key;
  }

  function applyTranslations(translations, root = document) {
    root.querySelectorAll('[data-i18n]').forEach((element) => {
      element.textContent = t(translations, element.dataset.i18n);
    });

    root.querySelectorAll('[data-i18n-html]').forEach((element) => {
      element.innerHTML = t(translations, element.dataset.i18nHtml);
    });

    root.querySelectorAll('[data-i18n-placeholder]').forEach((element) => {
      element.placeholder = t(translations, element.dataset.i18nPlaceholder);
    });

    root.querySelectorAll('[data-i18n-title]').forEach((element) => {
      element.title = t(translations, element.dataset.i18nTitle);
    });

    root.querySelectorAll('[data-i18n-value]').forEach((element) => {
      element.value = t(translations, element.dataset.i18nValue);
    });
  }

  return {
    storageKey,
    supportedLanguages,
    languageOptions,
    detectLanguage,
    loadTranslations,
    t,
    applyTranslations
  };
})();
