"""Scraper for gymbeam.rs - Large multinational supplement e-commerce (Magento-based)."""

import re
from typing import List, Optional, Dict, Any
from bs4 import BeautifulSoup, Tag

from .base_store import BaseStoreScraper


class GymBeamScraper(BaseStoreScraper):
    STORE_NAME = "GymBeam"
    BASE_URL = "https://www.gymbeam.rs"
    MAX_PAGES = 80  # large catalog

    # Category URLs to scrape
    CATEGORY_URLS = [
        "/sport-i-fitnes.html",
        "/zdrava-hrana.html",
        "/zdravlje.html",
        "/odeca-i-oprema.html",
    ]

    def get_page_urls(self) -> List[str]:
        """Discover paginated URLs across GymBeam categories."""
        urls = []
        for cat_path in self.CATEGORY_URLS:
            cat_url = f"{self.BASE_URL}{cat_path}"
            soup = self.fetch_page(cat_url)
            if not soup:
                urls.append(cat_url)
                continue

            max_page = 1
            # Magento pagination: .pages-items li a
            pagination = soup.select('.pages-items a, .pagination a, .toolbar-amount, a.page')
            for link in pagination:
                href = link.get('href', '')
                text = link.get_text(strip=True)
                if text.isdigit():
                    max_page = max(max_page, int(text))
                else:
                    match = re.search(r'[?&]p=(\d+)', href)
                    if match:
                        max_page = max(max_page, int(match.group(1)))

            max_page = min(max_page, self.MAX_PAGES)
            for page in range(1, max_page + 1):
                sep = '&' if '?' in cat_url else '?'
                urls.append(f"{cat_url}{sep}p={page}")

        return urls

    def get_product_cards(self, soup: BeautifulSoup) -> List[Tag]:
        """Extract product cards from Magento-style product grid."""
        selectors = [
            '.product-item',
            '.product-items .product-item',
            'li.product-item',
            '.products-grid .item',
            '.product-card',
            '.products .product',
            'ol.products li',
            '.product-list-item',
        ]
        for selector in selectors:
            cards = soup.select(selector)
            if cards:
                return cards
        return []

    def parse_product_card(self, card: Tag) -> Optional[Dict[str, Any]]:
        """Parse a Magento-style product card from GymBeam."""
        # Product name - Magento uses .product-item-link or product name class
        name_el = card.select_one(
            '.product-item-link, .product-item-name a, .product-name a, '
            '.product-item-name, a.product-item-link, h2.product-name, h3'
        )
        name = self._find_text(name_el)
        if not name:
            return None

        # Product URL
        link = card.select_one('a.product-item-link, a.product-item-photo, a[href]')
        product_url = self._find_attr(link, 'href')

        # Image - Magento lazy loads
        image_url = ""
        img = card.select_one('.product-image-photo, .product-image img, img')
        if img:
            image_url = (
                img.get('data-src') or img.get('data-lazy') or
                img.get('src') or ""
            )

        # Prices - Magento pattern
        original_price = None
        discount_price = None

        # Check for special (sale) price
        old_price_el = card.select_one('.old-price .price, .old-price .price-wrapper [data-price-amount]')
        special_price_el = card.select_one('.special-price .price, .special-price .price-wrapper [data-price-amount]')

        if old_price_el and special_price_el:
            # Has sale price
            old_amount = old_price_el.get('data-price-amount') if old_price_el.has_attr('data-price-amount') else None
            special_amount = special_price_el.get('data-price-amount') if special_price_el.has_attr('data-price-amount') else None

            if old_amount:
                original_price = float(old_amount)
            else:
                original_price = self.parse_price(self._find_text(old_price_el))

            if special_amount:
                discount_price = float(special_amount)
            else:
                discount_price = self.parse_price(self._find_text(special_price_el))
        else:
            # Single price
            price_el = card.select_one(
                '.price, .price-wrapper [data-price-amount], '
                '.product-price, [data-price-amount]'
            )
            if price_el:
                amount = price_el.get('data-price-amount')
                if amount:
                    original_price = float(amount)
                else:
                    original_price = self.parse_price(self._find_text(price_el))

        # Category from breadcrumb or label
        category = ""
        cat_el = card.select_one('.product-category, .category-name, [class*="category"]')
        if cat_el:
            category = self._find_text(cat_el)

        # Discount badge
        if not category:
            badge = card.select_one('.product-label, .sale-label, .discount-label, .badge')
            if badge:
                badge_text = self._find_text(badge)
                if '%' in badge_text or 'popust' in badge_text.lower():
                    pass  # It's a discount badge, not a category

        # Stock
        in_stock = True
        out_of_stock = card.select_one('.out-of-stock, .unavailable, .outofstock')
        if out_of_stock:
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
