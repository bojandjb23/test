"""Scraper for titaniumsport.rs - Ćuprija-based supplement store (likely WooCommerce)."""

import re
from typing import List, Optional, Dict, Any
from bs4 import BeautifulSoup, Tag

from .base_store import BaseStoreScraper


class TitaniumSportScraper(BaseStoreScraper):
    STORE_NAME = "TitaniumSport"
    BASE_URL = "https://www.titaniumsport.rs"
    MAX_PAGES = 30

    CATEGORY_URLS = [
        "/kategorija-proizvoda/suplementi/",
        "/kategorija-proizvoda/proteini/",
        "/kategorija-proizvoda/kreatin/",
        "/kategorija-proizvoda/amino-kiseline/",
        "/kategorija-proizvoda/vitamini/",
        "/kategorija-proizvoda/spalivaci-masti/",
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
            pagination = soup.select('.page-numbers a, .woocommerce-pagination a')
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

    def _category_from_url(self, url: str) -> str:
        mapping = {
            'proteini': 'Proteini',
            'kreatin': 'Kreatin',
            'amino-kiseline': 'Amino kiseline',
            'vitamini': 'Vitamini',
            'spalivaci-masti': 'Spalivači masti',
            'suplementi': 'Suplementi',
        }
        for key, value in mapping.items():
            if key in url:
                return value
        return ""

    def get_product_cards(self, soup: BeautifulSoup) -> List[Tag]:
        selectors = [
            'li.product',
            '.products .product',
            '.product-item',
            'ul.products li',
            '.product-card',
        ]
        for selector in selectors:
            cards = soup.select(selector)
            if cards:
                return cards
        return []

    def parse_product_card(self, card: Tag) -> Optional[Dict[str, Any]]:
        """Parse a WooCommerce product card."""
        name_el = card.select_one(
            '.woocommerce-loop-product__title, h2, h3, .product-title'
        )
        name = self._find_text(name_el)
        if not name:
            return None

        link = card.select_one('a.woocommerce-LoopProduct-link, a[href]')
        product_url = self._find_attr(link, 'href')
        image_url = self._find_image_url(card)

        original_price = None
        discount_price = None

        del_el = card.select_one('del .woocommerce-Price-amount, del')
        ins_el = card.select_one('ins .woocommerce-Price-amount, ins')

        if del_el and ins_el:
            original_price = self.parse_price(self._find_text(del_el))
            discount_price = self.parse_price(self._find_text(ins_el))
        else:
            price_el = card.select_one('.price .woocommerce-Price-amount, .price, .amount')
            if price_el:
                original_price = self.parse_price(self._find_text(price_el))

        category = ""
        cat_el = card.select_one('.product-category, .category')
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

    def scrape_all(self) -> List[Dict[str, Any]]:
        """Override to inject category from URL."""
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
