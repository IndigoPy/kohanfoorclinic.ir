
document.addEventListener('DOMContentLoaded', function () {

  // ---------- ۱. فرمت‌کردن قیمت با جداکننده هزارگان حین تایپ ----------
  function formatNumber(raw) {
    const digits = raw.replace(/[^\d]/g, '');
    if (!digits) return '';
    return Number(digits).toLocaleString('en-US');
  }

  document.addEventListener('input', function (e) {
    if (e.target.classList.contains('amount-display')) {
      const hiddenId = e.target.dataset.target;
      const hidden = document.getElementById(hiddenId);
      const digits = e.target.value.replace(/[^\d]/g, '');
      e.target.value = formatNumber(e.target.value);
      if (hidden) hidden.value = digits;
      validateAmountField(e.target);
    }
  });

  function validateAmountField(displayInput) {
    const max = parseInt(displayInput.dataset.max || '0', 10);
    const raw = parseInt((displayInput.value || '0').replace(/[^\d]/g, ''), 10) || 0;
    const feedback = displayInput.closest('.col-md-4, .mb-3')?.querySelector('.invalid-feedback-custom');
    const submitBtn = displayInput.closest('form')?.querySelector('button[type="submit"]');

    if (max > 0 && raw > max) {
      displayInput.classList.add('is-invalid');
      if (feedback) feedback.classList.remove('d-none');
      if (submitBtn) submitBtn.disabled = true;
    } else {
      displayInput.classList.remove('is-invalid');
      if (feedback) feedback.classList.add('d-none');
      if (submitBtn) submitBtn.disabled = false;
    }
  }

  // فرمت‌کردن مقادیر اولیه هنگام باز شدن مودال
  document.addEventListener('shown.bs.modal', function (e) {
    e.target.querySelectorAll('.amount-display').forEach(function (input) {
      input.value = formatNumber(input.value);
      validateAmountField(input);
    });
  });

  // ---------- ۲. جلوگیری نهایی از ارسال فرم با مبلغ نامعتبر ----------
  document.addEventListener('submit', function (e) {
    const form = e.target;
    if (!form.classList.contains('payment-form') && !form.querySelector) return;
    const amountDisplay = form.querySelector('.amount-display');
    if (amountDisplay) {
      const max = parseInt(amountDisplay.dataset.max || '0', 10);
      const raw = parseInt((amountDisplay.value || '0').replace(/[^\d]/g, ''), 10) || 0;
      if (raw <= 0) {
        e.preventDefault();
        alert('مبلغ پرداخت را وارد کنید.');
      } else if (max > 0 && raw > max) {
        e.preventDefault();
        alert('مبلغ وارد شده از باقی‌مانده سفارش بیشتر است.');
      }
    }
  });

  // ---------- ۳. ماشین‌حساب مینیاتوری ----------
  const calc = document.getElementById('miniCalculator');
  const calcDisplay = document.getElementById('calcDisplay');
  let calcTargetId = null;
  let calcExpr = '';

  document.addEventListener('click', function (e) {
    const toggleBtn = e.target.closest('.calc-toggle');
    if (toggleBtn) {
      calcTargetId = toggleBtn.dataset.target;
      calcExpr = '';
      calcDisplay.value = '0';
      const rect = toggleBtn.getBoundingClientRect();
      calc.style.top = (rect.bottom + 6) + 'px';
      calc.style.left = Math.max(10, rect.left - 150) + 'px';
      calc.classList.remove('d-none');
      return;
    }

    if (!calc.contains(e.target) && !e.target.closest('.calc-toggle')) {
      calc.classList.add('d-none');
    }

    const keyBtn = e.target.closest('.calc-key');
    if (keyBtn) {
      const key = keyBtn.dataset.key;
      if (key === 'C') {
        calcExpr = '';
      } else if (key === '⌫') {
        calcExpr = calcExpr.slice(0, -1);
      } else if (key === '=') {
        // فقط ارقام و عملگرهای مجاز پذیرفته می‌شود (بدون eval مستقیم روی ورودی خام)
        if (/^[0-9+\-*/.\s]+$/.test(calcExpr)) {
          try {
            const result = Function('"use strict"; return (' + calcExpr + ')')();
            calcExpr = String(Math.round(result));
          } catch (err) {
            calcExpr = '0';
          }
        } else {
          calcExpr = '0';
        }
      } else {
        calcExpr += key;
      }
      calcDisplay.value = calcExpr || '0';
    }
  });

  document.getElementById('calcDisplay') && document.getElementById('calcDisplay').addEventListener('dblclick', function () {
    // درج نتیجه با دابل‌کلیک روی صفحه‌نمایش ماشین‌حساب
    insertCalcResult();
  });

  // درج نتیجه با کلیک روی «=» وقتی عبارت کامل محاسبه شده (کلیک دوم روی =)
  document.addEventListener('click', function (e) {
    const keyBtn = e.target.closest('.calc-key[data-key="="]');
    if (keyBtn && calcTargetId) {
      insertCalcResult();
    }
  });

  function insertCalcResult() {
    if (!calcTargetId) return;
    const hidden = document.getElementById(calcTargetId);
    const displayInput = document.querySelector('.amount-display[data-target="' + calcTargetId + '"]');
    const value = parseInt(calcDisplay.value, 10) || 0;
    if (hidden) hidden.value = value;
    if (displayInput) {
      displayInput.value = formatNumber(String(value));
      validateAmountField(displayInput);
    }
    calc.classList.add('d-none');
  }
});
