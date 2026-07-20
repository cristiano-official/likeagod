window.LikeGodPayments = (() => {
  function escapeHtml(value) {
    if (window.LikeGodApp?.escapeHtml) return window.LikeGodApp.escapeHtml(value);
    return String(value ?? '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  function icon(name) {
    const n = String(name || '').toLowerCase();
    if (n.includes('telegram') || n.includes('cryptobot')) {
      return `<svg viewBox='0 0 24 24' aria-hidden='true'><circle cx='12' cy='12' r='11' fill='#2AABEE'/><path d='m6.7 11.8 9.7-4.1c.45-.18.84.11.69.82l-1.65 7.77c-.12.56-.45.7-.9.43l-2.5-1.85-1.2 1.16c-.13.13-.24.24-.5.24l.18-2.56 4.65-4.2c.2-.18-.05-.28-.31-.1l-5.75 3.62-2.48-.77c-.54-.17-.56-.54.11-.8Z' fill='#fff'/></svg>`;
    }
    if (n.includes('visa') || n.includes('mastercard') || n.includes('сбп') || n.includes('sbp') || n.includes('aaio')) {
      return `<svg viewBox='0 0 88 24' aria-hidden='true'><rect x='0.5' y='0.5' width='87' height='23' rx='8' fill='rgba(255,255,255,.08)' stroke='rgba(255,255,255,.18)'/><text x='8' y='15' font-size='9' font-weight='700' fill='#1A1F71'>VISA</text><circle cx='47' cy='12' r='5.5' fill='#EB001B'/><circle cx='53.5' cy='12' r='5.5' fill='#F79E1B' fill-opacity='.9'/><text x='64' y='15' font-size='7' font-weight='700' fill='#F5F7FA'>СБП</text></svg>`;
    }
    if (n.includes('wallet') || n.includes('usdt') || n.includes('crypto')) {
      return `<svg viewBox='0 0 24 24' aria-hidden='true'><circle cx='12' cy='12' r='11' fill='#26A17B'/><path d='M13.9 10.25V8.87h3.18V6.78H6.92v2.09h3.18v1.37c-2.58.12-4.52.63-4.52 1.25s1.94 1.13 4.52 1.25v4.4h3.8v-4.4c2.57-.12 4.51-.63 4.51-1.25s-1.94-1.13-4.51-1.24Zm0 2.1v.01c-.06 0-.37.03-1.06.03-.55 0-.93-.02-1.07-.03v-.01c-2.13-.09-3.72-.45-3.72-.88s1.59-.8 3.72-.88v1.39c.15.01.53.04 1.08.04.65 0 .98-.03 1.05-.04v-1.39c2.12.09 3.7.45 3.7.88s-1.58.78-3.7.87Z' fill='#fff'/></svg>`;
    }
    return `<svg viewBox='0 0 24 24' aria-hidden='true'><rect x='3' y='5' width='18' height='14' rx='4' fill='rgba(255,255,255,.16)' stroke='rgba(255,255,255,.25)'/><path d='M7 12h10' stroke='#F97316' stroke-width='2' stroke-linecap='round'/></svg>`;
  }

  function renderMethodCards(methods, selectedId) {
    return methods.map((method) => {
      const isActive = Number(selectedId) === Number(method.id);
      return `<button class='payment-card ${isActive ? 'is-active' : ''}' type='button' data-payment-method='${method.id}'>
        <span class='payment-card__logo'>${icon(method.name)}</span>
        <span class='payment-card__meta'>
          <strong>${escapeHtml(method.name)}</strong>
          <small>${escapeHtml(method.commission_label || method.currency_code || '')}</small>
        </span>
      </button>`;
    }).join('');
  }

  return { renderMethodCards };
})();
