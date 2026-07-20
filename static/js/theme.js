window.LikeGodTheme = (() => {
  const storageKey = 'likeagod.theme';

  function normalize(theme) {
    return Number(theme) === 1 ? 1 : 0;
  }

  function applyTheme(theme) {
    const normalized = normalize(theme);
    document.documentElement.setAttribute('data-theme', normalized === 1 ? 'light' : 'dark');
    localStorage.setItem(storageKey, String(normalized));
    return normalized;
  }

  function resolveInitialTheme(user) {
    const stored = localStorage.getItem(storageKey);
    if (stored !== null) return normalize(stored);
    if (user && user.theme !== undefined && user.theme !== null) return normalize(user.theme);
    return 0;
  }

  return {
    storageKey,
    applyTheme,
    resolveInitialTheme,
    normalize
  };
})();
