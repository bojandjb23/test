"""Scraper for fitlab.rs - Niš-based supplement store (likely WooCommerce)."""

import re
from typing import List, Optional, Dict, Any
from bs4 import BeautifulSoup, Tag

from .base_store import BaseStoreScraper


class FitLabScraper(BaseStoreScraper):
    STORE_NAME = "FitLab"
    BASE_URL = "https://fitlab.rs"
    MAX_PAGES = 30

    CATEGORY_URLS = [
        "/product-category/proteini/",
        "/product-category/kreatin/",
        "/product-category/amino-kiseline/",
        "/product-category/vitamini-i-minerali/",
        "/product-category/pre-workout/",
        "/product-category/snekovi-i-napici/",
        "/product-category/za-mrsavljenje/",
        "/product-category/zdravlje/",
    ]

    def get_page_urls(self) -> List[str]:
        """Build paginated URLs for each category."""
        urls = []
        for cat_path in self.CATEGORY_URLS:
            cat_url = f"{self.BASE_URL}{cat_path}"
            soup = self.fetch_page(cat_url)
            if not soup:
                urls.append(cat_url)
                continue

            max_page = 1
            pagination = soup.select('.page-numbers a, .woocommerce-pagination a, .pagination a')
            for link in pagination:
                text = link.get_text(strip=True)
                href = link.get('href', '')
                if text.isdigit():
                    max_page = max(max_page, int(text))
                else:
                    match = re.search(r'/page/(\d+)', href)
                    if match:
                        max_page = max(max_page, int(match.group(1)))

            max_page = min(max_page, self.MAX_PAGES)
            for page in range(1, max_page + 1):
                if page == 1:
                    urls.append(cat_url)
                else:
                    urls.append(f"{cat_url}page/{page}/")

        return urls

    def _extract_category_from_url(self, url: str) -> str:
        """Extract category name from URL path."""
        category_map = {
            'proteini': 'Proteini',
            'kreatin': 'Kreatin',
            'amino-kiseline': 'Amino kiseline',
            'vitamini-i-minerali': 'Vitamini i minerali',
            'pre-workout': 'Pre-workout',
            'snekovi-i-napici': 'Snekovi i napici',
            'za-mrsavljenje': 'Za mršavljenje',
            'zdravlje': 'Zdravlje',
        }
        for key, value in category_map.items():
            if key in url:
                return value
        return ""

    def get_product_cards(self, soup: BeautifulSoup) -> List[Tag]:
        """Extract WooCommerce product cards."""
        selectors = [
            'li.product',
            '.products .product',
            '.product-item',
            '.product-card',
            'ul.products li',
            '.shop-product',
        ]
        for selector in selectors:
            cards = soup.select(selector)
            if cards:
                return cards
        return []

    def parse_product_card(self, card: Tag) -> Optional[Dict[str, Any]]:
        """Parse a WooCommerce product card from FitLab."""
        # Name
        name_el = card.select_one(
            '.woocommerce-loop-product__title, h2.woocommerce-loop-product__title, '
            'h2, h3, .product-title, .product-name'
        )
        name = self._find_text(name_el)
        if not name:
            link = card.select_one('a.woocommerce-LoopProduct-link, a[href]')
            if link:
                name = link.get('title', '') or self._find_text(link)
        if not name:
            return None

        # URL
        link = card.select_one('a.woocommerce-LoopProduct-link, a[href]')
        product_url = self._find_attr(link, 'href')

        # Image
        image_url = self._find_image_url(card)

        # Prices (WooCommerce del/ins pattern)
        original_price = None
        discount_price = None

        del_el = card.select_one('del .woocommerce-Price-amount, del .amount, del')
        ins_el = card.select_one('ins .woocommerce-Price-amount, ins .amount, ins')

        if del_el and ins_el:
            original_price = self.parse_price(self._find_text(del_el))
            discount_price = self.parse_price(self._find_text(ins_el))
        else:
            price_el = card.select_one(
                '.price .woocommerce-Price-amount, .price .amount, '
                '.price, span.price'
            )
            if price_el:
                original_price = self.parse_price(self._find_text(price_el))

        # Category from the page URL context (set by scrape_all override or from card)
        category = ""
        cat_el = card.select_one('.product-category, .posted_in a')
        if cat_el:
            category = self._find_text(cat_el)

        # Stock
        in_stock = 'outofstock' not in card.get('class', [])

        # Sale badge
        sale_badge = card.select_one('.onsale, .sale-badge')

        return self.make_product(
            name=name,
            category=category,
            image_url=image_url,
            original_price=original_price,
            discount_price=discount_price,
            product_url=product_url,
            in_stock=in_stock,
        )

    def scrape_all(self) -> List[Dict[str, Any]]:
        """Override to inject category from URL context."""
        self.products = []
        urls = self.get_page_urls()

        if not urls:
            return self.products

        from tqdm import tqdm
        import logging
        logger = logging.getLogger(__name__)

        for url in tqdm(urls, desc=f"Scraping {self.STORE_NAME}", unit="page"):
            soup = self.fetch_page(url)
            if not soup:
                continue

            category = self._extract_category_from_url(url)
            cards = self.get_product_cards(soup)

            for card in cards:
                try:
                    product = self.parse_product_card(card)
                    if product and product.get("name"):
                        if not product["category"] and category:
                            product["category"] = category
                        self.products.append(product)
                except Exception as e:
                    logger.warning(f"[{self.STORE_NAME}] Failed to parse product card: {e}")

        logger.info(f"[{self.STORE_NAME}] Scraped {len(self.products)} products")
        return self.products
