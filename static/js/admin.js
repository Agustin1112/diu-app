/* DIU Admin JS */

// Color input preview
document.querySelectorAll('input[type="color"]').forEach(input => {
  const dot = document.createElement('div');
  dot.className = 'color-dot';
  dot.style.background = input.value;
  input.parentElement.appendChild(dot);
  input.addEventListener('input', () => { dot.style.background = input.value; });
});

// Auto-dismiss alerts
document.querySelectorAll('.admin-alert').forEach(el => {
  setTimeout(() => {
    el.style.opacity = '0';
    el.style.transition = 'opacity 0.4s';
    setTimeout(() => el.remove(), 400);
  }, 4000);
});

// Confirm deletes (extra safety)
document.querySelectorAll('form[data-confirm]').forEach(form => {
  form.addEventListener('submit', e => {
    if (!confirm(form.dataset.confirm)) e.preventDefault();
  });
});

// Search filter live (admin tables)
const adminSearch = document.querySelector('.admin-search input');
if (adminSearch) {
  adminSearch.addEventListener('input', function() {
    const q = this.value.toLowerCase();
    document.querySelectorAll('.admin-table tbody tr').forEach(row => {
      row.style.display = row.textContent.toLowerCase().includes(q) ? '' : 'none';
    });
  });
}
