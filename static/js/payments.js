/* payments.js — deposit / withdraw flow used by the shared modal.
   Depends on window.App (api, toast, closeModal) and window.I18n (t).
   Public API on window.Payments:
     Payments.loadMethods(type)      -> Promise<method[]>
     Payments.initModal(mode, root)  -> wires the modal skeleton built by app.js
     Payments.cancelInvoice()        -> cancels the active pending deposit
   The modal skeleton (built in app.js) provides these hooks by id:
     #pay-methods, #pay-amount, #pay-telegram (withdraw only), #pay-submit
*/
window.Payments = (() => {
  const t = (k, p) => window.I18n.t(k, p);

  function loadMethods(type) {
    return window.App.api('GET', `/api/v1/payments/methods?type=${type}`).catch(() => []);
  }

  // simple text badge from currency / alias — no external logos
  function badgeText(method) {
    return (method.currency_code || method.gateway_alias || method.name || '??')
      .slice(0, 4)
      .toUpperCase();
  }

  function renderMethods(container, methods, state) {
    container.innerHTML = '';
    if (!methods.length) {
      container.innerHTML = `<p class="method-meta">${t('common.errors.selectMethod')}</p>`;
      return;
    }
    methods.forEach((method, i) => {
      const opt = document.createElement('button');
      opt.type = 'button';
      opt.className = 'method-option' + (i === 0 ? ' selected' : '');
      opt.innerHTML = `
        <span class="method-badge">${badgeText(method)}</span>
        <span>
          <span class="method-name">${method.name}</span><br>
          <span class="method-meta">min ${method.min_amount} ${method.currency_code} · ${method.commission_label || ''}</span>
        </span>`;
      opt.addEventListener('click', () => {
        state.methodId = method.id;
        container.querySelectorAll('.method-option').forEach((el) => el.classList.remove('selected'));
        opt.classList.add('selected');
      });
      container.appendChild(opt);
    });
    state.methodId = methods[0].id;
  }

  async function initModal(mode, root) {
    const scope = root || document;
    const methodsBox = scope.querySelector('#pay-methods');
    const amountInput = scope.querySelector('#pay-amount');
    const telegramInput = scope.querySelector('#pay-telegram');
    const submitBtn = scope.querySelector('#pay-submit');
    if (!methodsBox || !submitBtn) return;

    const state = { methodId: null };
    const methods = await loadMethods(mode);
    renderMethods(methodsBox, methods, state);

    submitBtn.addEventListener('click', async () => {
      if (!state.methodId) { window.App.toast(t('common.errors.selectMethod'), 'error'); return; }
      const amount = parseFloat(amountInput && amountInput.value);
      if (!amount || amount <= 0) { window.App.toast(t('common.errors.invalidAmount'), 'error'); return; }

      submitBtn.disabled = true;
      try {
        if (mode === 'deposit') {
          const res = await window.App.api('POST', '/api/v1/payments/deposit', {
            method_id: state.methodId,
            amount
          });
          window.App.toast(t('common.toasts.invoiceCreated'), 'success');
          if (res && res.pay_url) {
            showInvoice(scope, res.pay_url);
            window.open(res.pay_url, '_blank', 'noopener');
          }
        } else {
          const address = telegramInput ? telegramInput.value.trim() : '';
          await window.App.api('POST', '/api/v1/payments/withdraw', {
            method_id: state.methodId,
            amount,
            address
          });
          window.App.toast(t('common.toasts.saved'), 'success');
          window.App.closeModal();
        }
      } catch (err) {
        window.App.toast(err.message || t('common.errors.genericError'), 'error');
      } finally {
        submitBtn.disabled = false;
      }
    });
  }

  function showInvoice(scope, url) {
    const body = scope.querySelector('.modal-body');
    const footer = scope.querySelector('.modal-footer');
    if (!body) return;
    body.innerHTML = `
      <div class="state-card" style="text-align:left">
        <h3>${t('common.modal.invoiceReady')}</h3>
        <p>${t('common.modal.invoiceText')}</p>
      </div>`;
    if (footer) {
      footer.innerHTML = `
        <button class="btn-secondary" data-close>${t('common.actions.close')}</button>
        <a class="btn" href="${url}" target="_blank" rel="noopener">${t('common.modal.completePayment')}</a>`;
      const closeBtn = footer.querySelector('[data-close]');
      if (closeBtn) closeBtn.addEventListener('click', () => window.App.closeModal());
    }
  }

  async function cancelInvoice() {
    try {
      await window.App.api('POST', '/api/v1/payments/cancel', {});
      window.App.toast(t('profile.billing.invoiceCancelled'), 'success');
      return true;
    } catch (err) {
      window.App.toast(err.message || t('common.errors.genericError'), 'error');
      return false;
    }
  }

  return { loadMethods, initModal, cancelInvoice };
})();
