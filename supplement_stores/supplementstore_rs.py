"""Scraper for supplementstore.rs - Belgrade-based supplement store."""

from typing import List, Optional, Dict, Any
from bs4 import BeautifulSoup, Tag

from .base_store import BaseStoreScraper


class SupplementStoreScraper(BaseStoreScraper):
    STORE_NAME = "Supplement Store"
    BASE_URL = "https://www.supplementstore.rs"
    MAX_PAGES = 50  # safety limit

    def get_page_urls(self) -> List[str]:
        """Discover paginated URLs from /svi-proizvodi."""
        urls = []
        first_url = f"{self.BASE_URL}/svi-proizvodi"
        soup = self.fetch_page(first_url)
        if not soup:
            return [first_url]

        # Try to find pagination
        max_page = 1
        # Common patterns: ?page=N, /page/N, or pagination links
        pagination = soup.select('.pagination a, .page-numbers a, nav.woocommerce-pagination a, .paging a')
        for link in pagination:
            href = link.get('href', '')
            text = link.get_text(strip=True)
            # Extract page number from URL or text
            if text.isdigit():
                max_page = max(max_page, int(text))
            else:
                import re
                page_match = re.search(r'[?&]page=(\d+)', href) or re.search(r'/page/(\d+)', href)
                if page_match:
                    max_page = max(max_page, int(page_match.group(1)))

        max_page = min(max_page, self.MAX_PAGES)

        for page in range(1, max_page + 1):
            # Try both URL patterns
            if '?' in first_url:
                urls.append(f"{first_url}&page={page}")
            else:
                urls.append(f"{first_url}?page={page}")

        return urls if urls else [first_url]

    def get_product_cards(self, soup: BeautifulSoup) -> List[Tag]:
        """Extract product cards using multiple selector strategies."""
        # Try various common e-commerce product card selectors
        selectors = [
            '.product-card',
            '.product-item',
            '.product-box',
            '.product',
            'li.product',
            '.products .product',
            '.product-grid-item',
            '.collection-product',
            '.grid-product',
            '[data-product]',
            '.product-list .item',
            '.shop-product',
        ]
        for selector in selectors:
            cards = soup.select(selector)
            if cards:
                return cards
        return []

    def parse_product_card(self, card: Tag) -> Optional[Dict[str, Any]]:
        """Parse a product card from supplementstore.rs."""
        # Product name
        name_el = (
            card.select_one('.product-card__title, .product-name, .product-title, '
                           '.woocommerce-loop-product__title, h2, h3, .title')
        )
        name = self._find_text(name_el)
        if not name:
            # Try link text
            link = card.select_one('a[href]')
            if link:
                name = link.get('title', '') or self._find_text(link)

        if not name:
            return None

        # Product URL
        link = card.select_one('a[href]')
        product_url = self._find_attr(link, 'href') if link else ""

        # Image
        image_url = self._find_image_url(card)

        # Prices - look for original (crossed out) and sale price
        original_price = None
        discount_price = None

        # Pattern 1: del/ins tags (WooCommerce standard)
        del_el = card.select_one('del .amount, del .woocommerce-Price-amount, del')
        ins_el = card.select_one('ins .amount, ins .woocommerce-Price-amount, ins')
        if del_el and ins_el:
            original_price = self.parse_price(self._find_text(del_el))
            discount_price = self.parse_price(self._find_text(ins_el))
        else:
            # Pattern 2: separate price classes
            old_price_el = card.select_one('.old-price, .regular-price, .price-old, .price-regular, .original-price')
            new_price_el = card.select_one('.special-price, .sale-price, .price-new, .price-sale, .current-price')
            if old_price_el and new_price_el:
                original_price = self.parse_price(self._find_text(old_price_el))
                discount_price = self.parse_price(self._find_text(new_price_el))
            else:
                # Pattern 3: single price element
                price_el = card.select_one('.price, .product-price, .amount, [class*="price"]')
                if price_el:
                    original_price = self.parse_price(self._find_text(price_el))

        # Category
        category = ""
        cat_el = card.select_one('.product-category, .category, .product-cat, [class*="category"]')
        if cat_el:
            category = self._find_text(cat_el)

        # Stock status
        in_stock = True
        stock_el = card.select_one('.out-of-stock, .sold-out, .outofstock')
        if stock_el:
            in_stock = False

        return self.make_product(
            name=name,
            category=category,
            image_url=image_url,
            original_price=original_price,
            discount_price=discount_price,
            product_url=product_url,
            in_stock=in_stock,
        )
