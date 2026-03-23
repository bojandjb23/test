"""Scraper for exyu-fitness.rs - 20+ year veteran supplement store."""

import re
from typing import List, Optional, Dict, Any
from bs4 import BeautifulSoup, Tag

from .base_store import BaseStoreScraper


class ExYuFitnessScraper(BaseStoreScraper):
    STORE_NAME = "ExYu Fitness"
    BASE_URL = "https://www.exyu-fitness.rs"
    MAX_PAGES = 40

    def get_page_urls(self) -> List[str]:
        """Discover paginated URLs from the shop page."""
        urls = []
        first_url = f"{self.BASE_URL}/shop/"
        soup = self.fetch_page(first_url)
        if not soup:
            return [first_url]

        max_page = 1
        pagination = soup.select('.page-numbers a, .woocommerce-pagination a, .pagination a')
        for link in pagination:
            text = link.get_text(strip=True)
            href = link.get('href', '')
            if text.isdigit():
                max_page = max(max_page, int(text))
            else:
                match = re.search(r'/page/(\d+)', href) or re.search(r'[?&]page=(\d+)', href)
                if match:
                    max_page = max(max_page, int(match.group(1)))

        max_page = min(max_page, self.MAX_PAGES)
        for page in range(1, max_page + 1):
            if page == 1:
                urls.append(first_url)
            else:
                urls.append(f"{first_url}page/{page}/")

        return urls

    def get_product_cards(self, soup: BeautifulSoup) -> List[Tag]:
        selectors = [
            'li.product',
            '.products .product',
            'ul.products li',
            '.product-item',
            '.product-card',
            '.product-box',
            '.grid-product',
        ]
        for selector in selectors:
            cards = soup.select(selector)
            if cards:
                return cards
        return []

    def parse_product_card(self, card: Tag) -> Optional[Dict[str, Any]]:
        """Parse a product card from ExYu Fitness."""
        name_el = card.select_one(
            '.woocommerce-loop-product__title, h2, h3, '
            '.product-title, .product-name'
        )
        name = self._find_text(name_el)
        if not name:
            link = card.select_one('a[href]')
            if link:
                name = link.get('title', '') or self._find_text(link)
        if not name:
            return None

        link = card.select_one('a.woocommerce-LoopProduct-link, a[href]')
        product_url = self._find_attr(link, 'href')
        image_url = self._find_image_url(card)

        original_price = None
        discount_price = None

        del_el = card.select_one('del .woocommerce-Price-amount, del .amount, del')
        ins_el = card.select_one('ins .woocommerce-Price-amount, ins .amount, ins')

        if del_el and ins_el:
            original_price = self.parse_price(self._find_text(del_el))
            discount_price = self.parse_price(self._find_text(ins_el))
        else:
            old_el = card.select_one('.price-old, .old-price, .regular-price')
            new_el = card.select_one('.price-new, .special-price, .sale-price')
            if old_el and new_el:
                original_price = self.parse_price(self._find_text(old_el))
                discount_price = self.parse_price(self._find_text(new_el))
            else:
                price_el = card.select_one('.price, .product-price, .amount')
                if price_el:
                    original_price = self.parse_price(self._find_text(price_el))

        category = ""
        cat_el = card.select_one('.product-category, .category, .posted_in a')
        if cat_el:
            category = self._find_text(cat_el)

        in_stock = 'outofstock' not in ' '.join(card.get('class', []))

        return self.make_product(
            name=name,
            category=category,
            image_url=image_url,
            original_price=original_price,
            discount_price=discount_price,
            product_url=product_url,
            in_stock=in_stock,
        )
