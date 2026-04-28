let menuData = [];
let cart = [];

const categoryContainer = document.getElementById('category-container');
const productContainer = document.getElementById('product-container');
const cartContainer = document.getElementById('cart-items');
const totalPriceEl = document.getElementById('total-price');
const checkoutBtn = document.getElementById('checkout-btn');
const itemCountEl = document.getElementById('item-count');

async function init() {
    try {
        const response = await fetch('/api/menu');
        menuData = await response.json();
        renderCategories();
        renderProducts(menuData[0].id); // First category by default
    } catch (err) {
        console.error('Failed to load menu:', err);
    }
}

function renderCategories() {
    categoryContainer.innerHTML = menuData.map((cat, index) => `
        <button class="category-btn ${index === 0 ? 'active' : ''}" 
                onclick="switchCategory(this, ${cat.id})">
            ${cat.name}
        </button>
    `).join('');
}

function switchCategory(btn, catId) {
    document.querySelectorAll('.category-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    renderProducts(catId);
}

function renderProducts(catId) {
    const cat = menuData.find(c => c.id === catId);
    if (!cat) return;

    productContainer.innerHTML = cat.products.map(prod => `
        <div class="product-card glass" onclick="addToCart(${prod.id}, '${prod.name}', ${prod.price})">
            <div class="product-image">
                <img src="${prod.image}" alt="${prod.name}">
            </div>
            <div class="product-info">
                <div class="product-name">${prod.name}</div>
                <div class="product-price">$${prod.price.toFixed(2)}</div>
            </div>
        </div>
    `).join('');
}

function addToCart(id, name, price) {
    const existing = cart.find(item => item.id === id);
    if (existing) {
        existing.quantity += 1;
    } else {
        cart.push({ id, name, price, quantity: 1 });
    }
    updateUI();
}

function updateQuantity(id, delta) {
    const idx = cart.findIndex(item => item.id === id);
    if (idx > -1) {
        cart[idx].quantity += delta;
        if (cart[idx].quantity <= 0) {
            cart.splice(idx, 1);
        }
    }
    updateUI();
}

function updateUI() {
    const totalCount = cart.reduce((acc, item) => acc + item.quantity, 0);
    const totalPrice = cart.reduce((acc, item) => acc + (item.price * item.quantity), 0);

    itemCountEl.textContent = `${totalCount} 個項目`;
    totalPriceEl.textContent = `$${totalPrice.toFixed(2)}`;
    checkoutBtn.disabled = cart.length === 0;

    cartContainer.innerHTML = cart.map(item => `
        <div class="cart-item">
            <div class="item-info">
                <span class="item-name">${item.name}</span>
                <span class="item-price">$${item.price.toFixed(2)}</span>
            </div>
            <div class="item-controls">
                <button class="qty-btn" onclick="updateQuantity(${item.id}, -1)">-</button>
                <span>${item.quantity}</span>
                <button class="qty-btn" onclick="updateQuantity(${item.id}, 1)">+</button>
            </div>
        </div>
    `).join('');
}

checkoutBtn.addEventListener('click', async () => {
    try {
        const response = await fetch('/api/order', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ items: cart })
        });
        const result = await response.json();
        if (result.success) {
            alert(`訂單 #${result.order_id} 成功！總計: $${result.total}`);
            cart = [];
            updateUI();
        }
    } catch (err) {
        alert('結帳失敗，請稍後再試！');
    }
});

init();
