/* ============================================
   DIU — MAIN JS (Flask version)
   ============================================ */

// ── Nav scroll ─────────────────────────────
const nav = document.getElementById('main-nav');
window.addEventListener('scroll', () => {
  nav?.classList.toggle('scrolled', window.scrollY > 20);
}, { passive: true });

// ── Cart ───────────────────────────────────
async function fetchCart() {
  const res  = await fetch('/api/cart');
  const cart = await res.json();
  renderCart(cart);
}

async function addToCart(productId) {
  const res  = await fetch('/api/cart/add', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ id: productId })
  });
  const data = await res.json();
  if (data.ok) {
    renderCart(data.cart);
    updateCartCount(data.count);
    showToast('Producto agregado al carrito', 'success');
  } else {
    showToast(data.msg || 'Error al agregar', 'error');
  }
}

async function removeFromCart(productId) {
  const res  = await fetch('/api/cart/remove', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ id: productId })
  });
  const data = await res.json();
  if (data.ok) { renderCart(data.cart); updateCartCount(data.count); }
}

async function updateQty(productId, qty) {
  const res  = await fetch('/api/cart/update', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ id: productId, qty })
  });
  const data = await res.json();
  if (data.ok) { renderCart(data.cart); updateCartCount(data.count); }
}

function updateCartCount(count) {
  const el = document.getElementById('cart-count');
  if (!el) return;
  el.textContent = count;
  el.style.display = count > 0 ? 'flex' : 'none';
}

function renderCart(cart) {
  const body    = document.getElementById('cart-body');
  const totalEl = document.getElementById('cart-total-num');
  if (!body) return;

  const totalQty = cart.reduce((s, i) => s + i.qty, 0);
  if (totalEl) totalEl.textContent = totalQty > 0 ? `${totalQty} producto${totalQty !== 1 ? 's' : ''}` : 'Vacío';

  if (!cart.length) {
    body.innerHTML = '<div class="cart-empty"><div class="cart-empty-icon">🛒</div><p>Tu carrito está vacío</p></div>';
    return;
  }

  body.innerHTML = cart.map(item => `
    <div class="cart-item">
      <div class="cart-item-icon">${item.icon}</div>
      <div style="flex:1;min-width:0">
        <div class="cart-item-name">${item.name}</div>
        <div class="cart-item-desc">${item.unit || ''}</div>
        <div class="cart-item-qty">
          <button class="qty-btn" onclick="updateQty(${item.id}, ${item.qty - 1})">−</button>
          <span class="qty-num">${item.qty}</span>
          <button class="qty-btn" onclick="updateQty(${item.id}, ${item.qty + 1})">+</button>
          <button onclick="removeFromCart(${item.id})" style="margin-left:4px;background:none;border:none;cursor:pointer;font-size:13px;color:var(--gray-400)">✕</button>
        </div>
      </div>
      <div class="cart-item-price">Consultar</div>
    </div>
  `).join('');
}

// ── Cart drawer ─────────────────────────────
function openCart() {
  document.getElementById('cart-overlay')?.classList.add('open');
  document.getElementById('cart-drawer')?.classList.add('open');
  document.body.style.overflow = 'hidden';
  fetchCart();
}

function closeCart() {
  document.getElementById('cart-overlay')?.classList.remove('open');
  document.getElementById('cart-drawer')?.classList.remove('open');
  document.body.style.overflow = '';
}

document.getElementById('cart-btn')?.addEventListener('click', openCart);
document.getElementById('cart-close')?.addEventListener('click', closeCart);
document.getElementById('cart-overlay')?.addEventListener('click', closeCart);

// ── "Add to cart" buttons ───────────────────
document.addEventListener('click', e => {
  const btn = e.target.closest('.js-add-cart');
  if (!btn) return;
  const id = parseInt(btn.dataset.id);
  if (id) addToCart(id);
});

// ── Toast ───────────────────────────────────
function showToast(message, type = '') {
  const container = document.getElementById('toast-container');
  if (!container) return;
  const toast = document.createElement('div');
  toast.className = 'toast' + (type === 'success' ? ' toast-success' : '');
  toast.innerHTML = `<span class="toast-icon">${type === 'success' ? '✓' : 'ℹ'}</span> ${message}`;
  container.appendChild(toast);
  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transform = 'translateY(8px)';
    toast.style.transition = 'all 0.3s ease';
    setTimeout(() => toast.remove(), 350);
  }, 2800);
}

// ── Reveal on scroll ────────────────────────
const revealObserver = new IntersectionObserver(entries => {
  entries.forEach(e => {
    if (e.isIntersecting) {
      e.target.classList.add('visible');
      revealObserver.unobserve(e.target);
    }
  });
}, { threshold: 0.1, rootMargin: '0px 0px -40px 0px' });

document.querySelectorAll('.reveal').forEach(el => revealObserver.observe(el));

// ── Auto-dismiss flash messages ─────────────
document.querySelectorAll('.flash').forEach(el => {
  setTimeout(() => {
    el.style.opacity = '0';
    el.style.transform = 'translateY(-8px)';
    el.style.transition = 'all 0.4s ease';
    setTimeout(() => el.remove(), 400);
  }, 4000);
});

// ── Init ────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  fetch('/api/cart')
    .then(r => r.json())
    .then(cart => updateCartCount(cart.reduce((s, i) => s + i.qty, 0)));
});

// ── Mobile hamburger menu ───────────────────
const hamburger   = document.getElementById('hamburger');
const mobileMenu  = document.getElementById('mobile-menu');

hamburger?.addEventListener('click', () => {
  const isOpen = mobileMenu.classList.toggle('open');
  hamburger.classList.toggle('open', isOpen);
  document.body.style.overflow = isOpen ? 'hidden' : '';
});

// Cerrar menú al hacer click en un link
mobileMenu?.querySelectorAll('a').forEach(link => {
  link.addEventListener('click', () => {
    mobileMenu.classList.remove('open');
    hamburger?.classList.remove('open');
    document.body.style.overflow = '';
  });
});

// Cerrar al hacer click fuera
document.addEventListener('click', e => {
  if (mobileMenu?.classList.contains('open') &&
      !mobileMenu.contains(e.target) &&
      !hamburger?.contains(e.target)) {
    mobileMenu.classList.remove('open');
    hamburger?.classList.remove('open');
    document.body.style.overflow = '';
  }
});