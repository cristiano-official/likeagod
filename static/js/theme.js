/* theme.js — theme persistence + toggle.
   Theme is stored as an int (0 = dark, 1 = light) to match the backend `theme`
   field. Applies data-theme on <html>, saves to localStorage, and (when logged
   in) syncs to /user/update.
   Public API on window.Theme:
     Theme.init(user)   -> resolve + apply initial theme
     Theme.apply(value) -> apply a theme value (0/1 or 'dark'/'light')
     Theme.toggle()     -> flip theme, persist, sync to server if logged in
     Theme.current      -> 'dark' | 'light'
*/
window.Theme = (() => {
  const STORAGE_KEY = 'likeagod.theme';
  let current = 'dark';

  function normalize(value) {
    if (value === 'light' || value === 1 || value === '1') return 1;
    return 0;
  }

  function apply(value) {
    const n = normalize(value);
    current = n === 1 ? 'light' : 'dark';
    document.documentElement.setAttribute('data-theme', current);
    localStorage.setItem(STORAGE_KEY, String(n));
    return current;
  }

  function init(user) {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored !== null) return apply(stored);
    if (user && user.theme !== undefined && user.theme !== null) return apply(user.theme);
    return apply(0);
  }

  function toggle() {
    const next = current === 'dark' ? 1 : 0;
    apply(next);
    // Sync to server if a session exists; ignore failures silently.
    if (window.App && window.App.user) {
      window.App.api('POST', '/user/update', { theme: next }).catch(() => {});
    }
    document.dispatchEvent(new CustomEvent('theme:changed', { detail: { theme: current } }));
    return current;
  }

  return {
    STORAGE_KEY,
    get current() { return current; },
    normalize,
    apply,
    init,
    toggle
  };
})();
