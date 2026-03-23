"""Scraper for rs.proteini.si - Regional supplement store (Slovenia-based, serves Serbia)."""

import re
from typing import List, Optional, Dict, Any
from bs4 import BeautifulSoup, Tag

from .base_store import BaseStoreScraper


class ProteiniSiScraper(BaseStoreScraper):
    STORE_NAME = "Proteini.si"
    BASE_URL = "https://rs.proteini.si"
    MAX_PAGES = 40

    CATEGORY_URLS = [
        "/kategorija/proteini/",
        "/kategorija/kreatin/",
        "/kategorija/amino-kiseline/",
        "/kategorija/vitamini-minerali/",
        "/kategorija/pre-workout/",
        "/kategorija/spalivaci-masti/",
        "/kategorija/zdrava-hrana/",
        "/kategorija/sportska-oprema/",
    ]

    def get_page_urls(self) -> List[str]:
        urls = []
        for cat_path in self.CATEGORY_URLS:
            cat_url = f"{self.BASE_URL}{cat_path}"
            soup = self.fetch_page(cat_url)
            if not soup:
                urls.append(cat_url)
                continue

            max_page = 1
            pagination = soup.select('.pagination a, .page-numbers a, a.page-link')
            for link in pagination:
                text = link.get_text(strip=True)
                href = link.get('href', '')
                if text.isdigit():
                    max_page = max(max_page, int(text))
                else:
                    match = re.search(r'[?&]page=(\d+)', href) or re.search(r'/page/(\d+)', href) or re.search(r'/(\d+)/?$', href)
                    if match:
                        max_page = max(max_page, int(match.group(1)))

            max_page = min(max_page, self.MAX_PAGES)
            for page in range(1, max_page + 1):
                if page == 1:
                    urls.append(cat_url)
                else:
                    # Try standard pagination patterns
                    urls.append(f"{cat_url}?page={page}")

        return urls

    def _category_from_url(self, url: str) -> str:
        mapping = {
            'proteini': 'Proteini',
            'kreatin': 'Kreatin',
            'amino-kiseline': 'Amino kiseline',
            'vitamini-minerali': 'Vitamini i minerali',
            'pre-workout': 'Pre-workout',
            'spalivaci-masti': 'Spalivači masti',
            'zdrava-hrana': 'Zdrava hrana',
            'sportska-oprema': 'Sportska oprema',
        }
        for key, value in mapping.items():
            if key in url:
                return value
        return ""

    def get_product_cards(self, soup: BeautifulSoup) -> List[Tag]:
        selectors = [
            '.product-card',
            '.product-item',
            '.product-box',
            'li.product',
            '.products .product',
            '.product-grid .item',
            '.product-list .product',
            '[data-product-id]',
            '.grid-item.product',
        ]
        for selector in selectors:
            cards = soup.select(selector)
            if cards:
                return cards
        return []

    def parse_product_card(self, card: Tag) -> Optional[Dict[str, Any]]:
        """Parse a product card from Proteini.si."""
        name_el = card.select_one(
            '.product-card__title, .product-name, .product-title, '
            'h2, h3, a.product-link, .name'
        )
        name = self._find_text(name_el)
        if not name:
            link = card.select_one('a[href]')
            if link:
                name = link.get('title', '') or self._find_text(link)
        if not name:
            return None

        link = card.select_one('a[href]')
        product_url = self._find_attr(link, 'href')
        image_url = self._find_image_url(card)

        original_price = None
        discount_price = None

        # Check for sale price patterns
        old_el = card.select_one(
            '.old-price, .price-old, del, .regular-price, '
            '.price--compare, s, .was-price, .original-price'
        )
        new_el = card.select_one(
            '.special-price, .price-new, ins, .sale-price, '
            '.price--sale, .current-price, .discount-price'
        )

        if old_el and new_el:
            original_price = self.parse_price(self._find_text(old_el))
            discount_price = self.parse_price(self._find_text(new_el))
        else:
            price_el = card.select_one('.price, .product-price, .amount, [class*="price"]')
            if price_el:
                original_price = self.parse_price(self._find_text(price_el))

        category = ""
        cat_el = card.select_one('.product-category, .category')
        if cat_el:
            category = self._find_text(cat_el)

        in_stock = True
        stock_el = card.select_one('.out-of-stock, .sold-out, .unavailable')
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

    def scrape_all(self) -> List[Dict[str, Any]]:
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
            category = self._category_from_url(url)
            cards = self.get_product_cards(soup)
            for card in cards:
                try:
                    product = self.parse_product_card(card)
                    if product and product.get("name"):
                        if not product["category"] and category:
                            product["category"] = category
                        self.products.append(product)
                except Exception as e:
                    logger.warning(f"[{self.STORE_NAME}] Parse error: {e}")

        logger.info(f"[{self.STORE_NAME}] Scraped {len(self.products)} products")
        return self.products
