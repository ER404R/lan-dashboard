document.addEventListener('DOMContentLoaded', function () {

  // Dialog: open
  document.querySelectorAll('[data-dialog-open]').forEach(function (btn) {
    btn.addEventListener('click', function () {
      document.getElementById(btn.dataset.dialogOpen).showModal();
    });
  });

  // Dialog: close
  document.querySelectorAll('[data-dialog-close]').forEach(function (btn) {
    btn.addEventListener('click', function () {
      btn.closest('dialog').close();
    });
  });

  // Confirm before form submit
  document.querySelectorAll('[data-confirm]').forEach(function (form) {
    form.addEventListener('submit', function (e) {
      if (!confirm(form.dataset.confirm)) e.preventDefault();
    });
  });

  // Select arrow toggle (rating form)
  function updateSelectArrow(sel) {
    sel.classList.toggle('select--no-arrow', sel.value !== '' && sel.value !== 'none');
  }
  document.querySelectorAll('.rating-form select').forEach(function (sel) {
    updateSelectArrow(sel);
    sel.addEventListener('change', function () { updateSelectArrow(sel); });
  });

});
