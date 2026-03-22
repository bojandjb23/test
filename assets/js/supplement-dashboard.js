/**
 * Supplement Discount Dashboard - Frontend Logic
 *
 * Handles: data loading, product card rendering, filtering,
 * sorting, search, weekly summary, and lazy loading.
 */

// ---- State ----
let allProducts = [];
let filteredProducts = [];
let weeklySummary = {};
let storeData = {};
let currentViewMode = 'discounts'; // 'discounts' or 'all'
let displayedCount = 0;
const BATCH_SIZE = 60;

// Active filters
let activeStores = new Set();
let activeCategory = '';
let minDiscount = 0;
let searchQuery = '';
let currentSort = 'discount_desc';

// ---- Initialization ----
document.addEventListener('DOMContentLoaded', () => {
    loadData();
});

function loadData() {
    const dataEl = document.getElementById('supplementsData');
    if (!dataEl) {
        showError('Nema podataka za prikaz.');
        return;
    }

    let raw = dataEl.textContent.trim();
    if (!raw || raw === '/* __SUPPLEMENT_DATA_PLACEHOLDER__ */') {
        showError('Dashboard jos nije generisan. Pokrenite: python supplement_scraper.py');
        return;
    }

    try {
        storeData = JSON.parse(raw);
    } catch (e) {
        showError('Greska pri ucitavanju podataka: ' + e.message);
        return;
    }

    allProducts = storeData.products || [];
    weeklySummary = storeData.weekly_summary || {};

    // Update header
    if (storeData.scraped_at) {
        const date = new Date(storeData.scraped_at);
        document.getElementById('lastUpdated').textContent =
            `Poslednje azuriranje: ${formatDate(date)}`;
    }

    // Build dynamic filters
    buildStoreFilters();
    buildCategoryFilter();
    renderWeeklySummary();

    // Footer
    const stores = storeData.stores_scraped || [];
    document.getElementById('storeCount').textContent = stores.length;
    document.getElementById('footerStores').textContent = stores.join(' | ');

    // Wire up event listeners
    setupEventListeners();

    // Initial render
    applyFiltersAndRender();
}

// ---- Filter UI Building ----
function buildStoreFilters() {
    const container = document.getElementById('storeFilters');
    const stores = [...new Set(allProducts.map(p => p.store))].sort();

    // All stores active by default
    activeStores = new Set(stores);

    container.innerHTML = stores.map(store => {
        const count = allProducts.filter(p => p.store === store).length;
        return `<span class="store-chip active" data-store="${escapeHtml(store)}" onclick="toggleStore(this)">${escapeHtml(store)} (${count})</span>`;
    }).join('');
}

function buildCategoryFilter() {
    const select = document.getElementById('categoryFilter');
    const categories = [...new Set(allProducts.map(p => p.category).filter(Boolean))].sort();

    select.innerHTML = '<option value="">Sve kategorije</option>' +
        categories.map(cat =>
            `<option value="${escapeHtml(cat)}">${escapeHtml(cat)}</option>`
        ).join('');
}

// ---- Event Listeners ----
function setupEventListeners() {
    // Search (debounced)
    const searchInput = document.getElementById('searchInput');
    let searchTimeout;
    searchInput.addEventListener('input', () => {
        clearTimeout(searchTimeout);
        searchTimeout = setTimeout(() => {
            searchQuery = searchInput.value.trim().toLowerCase();
            applyFiltersAndRender();
        }, 250);
    });

    // Category
    document.getElementById('categoryFilter').addEventListener('change', (e) => {
        activeCategory = e.target.value;
        applyFiltersAndRender();
    });

    // Discount range
    const discountRange = document.getElementById('discountRange');
    discountRange.addEventListener('input', (e) => {
        minDiscount = parseInt(e.target.value, 10);
        document.getElementById('discountRangeValue').textContent = minDiscount + '%';
        applyFiltersAndRender();
    });

    // Sort
    document.getElementById('sortSelect').addEventListener('change', (e) => {
        currentSort = e.target.value;
        applyFiltersAndRender();
    });
}

// ---- View Mode ----
function setViewMode(mode) {
    currentViewMode = mode;
    document.getElementById('btnDiscountsOnly').classList.toggle('active', mode === 'discounts');
    document.getElementById('btnAllProducts').classList.toggle('active', mode === 'all');
    applyFiltersAndRender();
}

// ---- Store Toggle ----
function toggleStore(chip) {
    const store = chip.dataset.store;
    if (activeStores.has(store)) {
        activeStores.delete(store);
        chip.classList.remove('active');
    } else {
        activeStores.add(store);
        chip.classList.add('active');
    }
    applyFiltersAndRender();
}

// ---- Summary Toggle ----
function toggleSummary() {
    const content = document.getElementById('summaryContent');
    const icon = document.getElementById('summaryToggle');
    content.classList.toggle('hidden');
    icon.classList.toggle('collapsed');
}

// ---- Filter + Sort + Render Pipeline ----
function applyFiltersAndRender() {
    // Filter
    filteredProducts = allProducts.filter(p => {
        // View mode
        if (currentViewMode === 'discounts' && (p.discount_percent || 0) <= 0) return false;

        // Store
        if (!activeStores.has(p.store)) return false;

        // Category
        if (activeCategory && p.category !== activeCategory) return false;

        // Min discount
        if (minDiscount > 0 && (p.discount_percent || 0) < minDiscount) return false;

        // Search
        if (searchQuery) {
            const haystack = (p.name + ' ' + (p.category || '') + ' ' + p.store).toLowerCase();
            if (!haystack.includes(searchQuery)) return false;
        }

        return true;
    });

    // Sort
    sortProducts(filteredProducts, currentSort);

    // Update count
    const countEl = document.getElementById('resultsCount');
    const discountedCount = filteredProducts.filter(p => (p.discount_percent || 0) > 0).length;
    countEl.textContent = `${filteredProducts.length} proizvoda | ${discountedCount} na popustu`;

    // Render
    displayedCount = 0;
    document.getElementById('productGrid').innerHTML = '';
    loadMore();
}

function sortProducts(products, criterion) {
    products.sort((a, b) => {
        switch (criterion) {
            case 'discount_desc':
                return (b.discount_percent || 0) - (a.discount_percent || 0);
            case 'discount_asc':
                return (a.discount_percent || 0) - (b.discount_percent || 0);
            case 'price_asc':
                return getEffectivePrice(a) - getEffectivePrice(b);
            case 'price_desc':
                return getEffectivePrice(b) - getEffectivePrice(a);
            case 'name_asc':
                return a.name.localeCompare(b.name, 'sr');
            case 'name_desc':
                return b.name.localeCompare(a.name, 'sr');
            case 'savings_desc':
                return getSavings(b) - getSavings(a);
            default:
                return 0;
        }
    });
}

function getEffectivePrice(product) {
    return product.discount_price || product.original_price || 0;
}

function getSavings(product) {
    if (product.original_price && product.discount_price) {
        return product.original_price - product.discount_price;
    }
    return 0;
}

// ---- Lazy Loading ----
function loadMore() {
    const grid = document.getElementById('productGrid');
    const end = Math.min(displayedCount + BATCH_SIZE, filteredProducts.length);
    const fragment = document.createDocumentFragment();

    for (let i = displayedCount; i < end; i++) {
        fragment.appendChild(createProductCard(filteredProducts[i]));
    }

    grid.appendChild(fragment);
    displayedCount = end;

    // Toggle load more button
    const loadMoreContainer = document.getElementById('loadMoreContainer');
    const noResults = document.getElementById('noResults');

    if (displayedCount < filteredProducts.length) {
        loadMoreContainer.style.display = 'block';
        document.getElementById('loadMoreBtn').textContent =
            `Ucitaj jos (${filteredProducts.length - displayedCount} preostalo)`;
    } else {
        loadMoreContainer.style.display = 'none';
    }

    noResults.style.display = filteredProducts.length === 0 ? 'block' : 'none';
}

// ---- Product Card Rendering ----
function createProductCard(product) {
    const card = document.createElement('div');
    card.className = 'product-card';

    const hasDiscount = product.discount_percent > 0 && product.discount_price;
    const effectivePrice = hasDiscount ? product.discount_price : product.original_price;
    const savings = hasDiscount ? (product.original_price - product.discount_price) : 0;

    // Discount badge tier
    let badgeTier = '';
    if (hasDiscount) {
        if (product.discount_percent >= 40) badgeTier = 'tier-high';
        else if (product.discount_percent >= 20) badgeTier = 'tier-medium';
        else badgeTier = 'tier-low';
    }

    card.innerHTML = `
        <div class="card-image">
            ${product.image_url
                ? `<img src="${escapeHtml(product.image_url)}" alt="${escapeHtml(product.name)}" loading="lazy" onerror="this.parentElement.innerHTML='<span class=\\'no-image\\'>Nema slike</span>'">`
                : '<span class="no-image">Nema slike</span>'
            }
            ${hasDiscount
                ? `<span class="discount-badge ${badgeTier}">-${product.discount_percent}%</span>`
                : ''
            }
            ${!product.in_stock
                ? `<div class="out-of-stock-overlay"><span class="out-of-stock-label">Nema na stanju</span></div>`
                : ''
            }
        </div>
        <div class="card-info">
            <div class="product-name" title="${escapeHtml(product.name)}">${escapeHtml(product.name)}</div>
            ${product.category
                ? `<span class="product-category">${escapeHtml(product.category)}</span>`
                : ''
            }
            <div class="price-section">
                ${hasDiscount
                    ? `<span class="original-price">${formatPrice(product.original_price)}</span>
                       <span class="discount-price">${formatPrice(product.discount_price)}</span>
                       <div class="savings">Usteda: ${formatPrice(savings)}</div>`
                    : `<span class="regular-price">${formatPrice(product.original_price)}</span>`
                }
            </div>
        </div>
        <div class="card-footer">
            <span class="store-name">${escapeHtml(product.store)}</span>
            <a href="${escapeHtml(product.product_url)}" target="_blank" rel="noopener noreferrer" class="buy-link">
                Kupi <span class="arrow">&rarr;</span>
            </a>
        </div>
    `;

    return card;
}

// ---- Weekly Summary ----
function renderWeeklySummary() {
    if (!weeklySummary || !weeklySummary.total_discounted) {
        document.getElementById('weeklySummary').style.display = 'none';
        return;
    }

    // Stats
    const statsHtml = `
        <div class="stat-box">
            <div class="stat-value">${weeklySummary.total_products || 0}</div>
            <div class="stat-label">Ukupno proizvoda</div>
        </div>
        <div class="stat-box">
            <div class="stat-value">${weeklySummary.total_discounted}</div>
            <div class="stat-label">Na popustu</div>
        </div>
        <div class="stat-box">
            <div class="stat-value">${weeklySummary.avg_discount_percent}%</div>
            <div class="stat-label">Prosecni popust</div>
        </div>
        <div class="stat-box">
            <div class="stat-value">${weeklySummary.new_discounts_count || 0}</div>
            <div class="stat-label">Novi popusti ove nedelje</div>
        </div>
    `;
    document.getElementById('summaryStats').innerHTML = statsHtml;

    // Store breakdown
    const storeBreakdown = weeklySummary.by_store || {};
    const storeHtml = Object.entries(storeBreakdown)
        .sort((a, b) => b[1].count - a[1].count)
        .map(([store, data]) =>
            `<div class="breakdown-item">
                <span class="label">${escapeHtml(store)}</span>
                <span class="value">${data.count} proizvoda <span class="badge">~${data.avg_discount}%</span></span>
            </div>`
        ).join('');
    document.querySelector('#storeBreakdown .breakdown-list').innerHTML = storeHtml || '<p style="font-size:0.85rem;color:#86868b">Nema podataka</p>';

    // Category breakdown
    const catBreakdown = weeklySummary.by_category || {};
    const catHtml = Object.entries(catBreakdown)
        .sort((a, b) => b[1].count - a[1].count)
        .slice(0, 10)
        .map(([cat, data]) =>
            `<div class="breakdown-item">
                <span class="label">${escapeHtml(cat)}</span>
                <span class="value">${data.count} <span class="badge">~${data.avg_discount}%</span></span>
            </div>`
        ).join('');
    document.querySelector('#categoryBreakdown .breakdown-list').innerHTML = catHtml || '<p style="font-size:0.85rem;color:#86868b">Nema podataka</p>';

    // Top deals
    const topDeals = (weeklySummary.top_discounts || []).slice(0, 5);
    const topHtml = topDeals.map(p =>
        `<div class="breakdown-item">
            <span class="label">${escapeHtml(truncate(p.name, 30))}</span>
            <span class="value"><span class="badge">-${p.discount_percent}%</span> ${formatPrice(p.discount_price)}</span>
        </div>`
    ).join('');
    document.querySelector('#topDeals .breakdown-list').innerHTML = topHtml || '<p style="font-size:0.85rem;color:#86868b">Nema podataka</p>';

    // Week changes
    let changesHtml = '';
    if (weeklySummary.new_discounts_count > 0) {
        changesHtml += `<div class="breakdown-item"><span class="label">Novi popusti</span><span class="value badge" style="background:#e8f5e9;color:#2e7d32">+${weeklySummary.new_discounts_count}</span></div>`;
    }
    if (weeklySummary.ended_discounts_count > 0) {
        changesHtml += `<div class="breakdown-item"><span class="label">Zavrseni popusti</span><span class="value badge" style="background:#fce4ec;color:#c62828">-${weeklySummary.ended_discounts_count}</span></div>`;
    }
    if (weeklySummary.deeper_discounts_count > 0) {
        changesHtml += `<div class="breakdown-item"><span class="label">Veci popusti</span><span class="value badge" style="background:#e8f5e9;color:#2e7d32">${weeklySummary.deeper_discounts_count}</span></div>`;
    }
    if (!changesHtml) {
        changesHtml = '<p style="font-size:0.85rem;color:#86868b">Prvo prikupljanje - nema poredjenja</p>';
    }
    document.querySelector('#weekChanges .breakdown-list').innerHTML = changesHtml;
}

// ---- Utility Functions ----
function formatPrice(price) {
    if (price == null || isNaN(price)) return '';
    return price.toLocaleString('sr-RS', {
        minimumFractionDigits: 0,
        maximumFractionDigits: 0,
    }) + ' RSD';
}

function formatDate(date) {
    return date.toLocaleString('sr-RS', {
        year: 'numeric',
        month: 'long',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
    });
}

function escapeHtml(str) {
    if (!str) return '';
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

function truncate(str, maxLen) {
    if (!str) return '';
    return str.length > maxLen ? str.slice(0, maxLen) + '...' : str;
}

function showError(msg) {
    const grid = document.getElementById('productGrid');
    grid.innerHTML = `<div class="no-results" style="display:block;grid-column:1/-1;"><p>${escapeHtml(msg)}</p></div>`;
}
