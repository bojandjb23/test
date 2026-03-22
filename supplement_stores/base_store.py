"""Base class for all supplement store scrapers."""

import re
import time
import logging
import unicodedata
from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from datetime import datetime

import requests
from bs4 import BeautifulSoup, Tag
from tqdm import tqdm

logger = logging.getLogger(__name__)


class BaseStoreScraper(ABC):
    """Abstract base class for supplement store scrapers.

    Each store scraper implements three methods:
      - get_page_urls(): returns all paginated listing URLs to crawl
      - get_product_cards(soup): extracts product card elements from a page
      - parse_product_card(card): parses a single card into a product dict
    """

    STORE_NAME: str = ""
    BASE_URL: str = ""
    DELAY: float = 1.5  # seconds between requests

    def __init__(self, session: Optional[requests.Session] = None, delay: float = None):
        self.session = session or self._create_session()
        self.delay = delay if delay is not None else self.DELAY
        self.products: List[Dict[str, Any]] = []
        self._last_request_time = 0.0

    @staticmethod
    def _create_session() -> requests.Session:
        session = requests.Session()
        session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "sr-Latn-RS,sr;q=0.9,en;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
        })
        return session

    def _rate_limit(self):
        """Enforce delay between requests."""
        elapsed = time.time() - self._last_request_time
        if elapsed < self.delay:
            time.sleep(self.delay - elapsed)
        self._last_request_time = time.time()

    def fetch_page(self, url: str, retries: int = 3) -> Optional[BeautifulSoup]:
        """GET a URL with retries and rate limiting, return BeautifulSoup or None."""
        for attempt in range(retries):
            try:
                self._rate_limit()
                response = self.session.get(url, timeout=30)
                response.raise_for_status()
                return BeautifulSoup(response.content, "html.parser")
            except requests.RequestException as e:
                wait = 2 ** attempt
                logger.warning(
                    f"[{self.STORE_NAME}] Attempt {attempt + 1}/{retries} failed for {url}: {e}. "
                    f"Retrying in {wait}s..."
                )
                if attempt < retries - 1:
                    time.sleep(wait)
        logger.error(f"[{self.STORE_NAME}] Failed to fetch {url} after {retries} attempts")
        return None

    @staticmethod
    def parse_price(price_str: str) -> Optional[float]:
        """Normalize Serbian price strings to float.

        Handles formats like:
          '4.199,00 RSD' -> 4199.0
          '4199 din'     -> 4199.0
          '4,199.00'     -> 4199.0
          '4199.00'      -> 4199.0
          '4199'         -> 4199.0
        """
        if not price_str:
            return None

        # Remove currency labels and whitespace
        cleaned = re.sub(r'[^\d.,]', '', price_str.strip())
        # Strip trailing dots/commas (e.g., from "din.")
        cleaned = cleaned.strip('.,') if cleaned else ''
        if not cleaned:
            return None

        # Find positions of last dot and last comma
        last_dot = cleaned.rfind('.')
        last_comma = cleaned.rfind(',')

        if last_dot > -1 and last_comma > -1:
            # Both present: whichever comes last is the decimal separator
            if last_comma > last_dot:
                # e.g. "4.199,00" -> dot is thousands, comma is decimal
                cleaned = cleaned.replace('.', '').replace(',', '.')
            else:
                # e.g. "4,199.00" -> comma is thousands, dot is decimal
                cleaned = cleaned.replace(',', '')
        elif last_comma > -1:
            # Only comma: could be decimal (e.g., "4199,00") or thousands ("4,199")
            parts_after_comma = cleaned.split(',')[-1]
            if len(parts_after_comma) == 2:
                # Likely decimal: "4199,00"
                cleaned = cleaned.replace(',', '.')
            else:
                # Likely thousands: "4,199"
                cleaned = cleaned.replace(',', '')
        elif last_dot > -1:
            # Only dot: check if it's a thousands separator (Serbian convention)
            # If digits after last dot are exactly 3, treat as thousands separator
            parts_after_dot = cleaned.split('.')[-1]
            if len(parts_after_dot) == 3:
                cleaned = cleaned.replace('.', '')
            # Otherwise treat as decimal (e.g., "4199.00")

        try:
            return float(cleaned)
        except ValueError:
            logger.warning(f"Could not parse price: '{price_str}' -> '{cleaned}'")
            return None

    @staticmethod
    def compute_discount_percent(original: float, discounted: float) -> int:
        """Calculate discount percentage, rounded to nearest integer."""
        if not original or original <= 0:
            return 0
        pct = (1 - discounted / original) * 100
        return max(0, round(pct))

    @staticmethod
    def slugify(text: str) -> str:
        """Generate URL-safe slug from text."""
        text = unicodedata.normalize('NFKD', text)
        text = text.encode('ascii', 'ignore').decode('ascii')
        text = re.sub(r'[^\w\s-]', '', text.lower())
        return re.sub(r'[-\s]+', '-', text).strip('-')

    def make_product(
        self,
        name: str,
        category: str,
        image_url: str,
        original_price: Optional[float],
        discount_price: Optional[float],
        product_url: str,
        in_stock: bool = True,
    ) -> Dict[str, Any]:
        """Create a standardized product dict."""
        if original_price and discount_price and discount_price < original_price:
            discount_percent = self.compute_discount_percent(original_price, discount_price)
        else:
            discount_percent = 0
            if discount_price and original_price and discount_price >= original_price:
                discount_price = None

        # Ensure absolute URLs
        if image_url and not image_url.startswith('http'):
            image_url = self.BASE_URL.rstrip('/') + '/' + image_url.lstrip('/')
        if product_url and not product_url.startswith('http'):
            product_url = self.BASE_URL.rstrip('/') + '/' + product_url.lstrip('/')

        return {
            "id": f"{self.slugify(self.STORE_NAME)}_{self.slugify(name)}",
            "name": name.strip(),
            "store": self.STORE_NAME,
            "store_url": self.BASE_URL,
            "category": category.strip() if category else "Ostalo",
            "image_url": image_url,
            "original_price": original_price,
            "discount_price": discount_price,
            "discount_percent": discount_percent,
            "currency": "RSD",
            "product_url": product_url,
            "in_stock": in_stock,
            "date_scraped": datetime.now().strftime("%Y-%m-%d"),
        }

    @abstractmethod
    def get_page_urls(self) -> List[str]:
        """Return all paginated product listing URLs to crawl."""
        ...

    @abstractmethod
    def get_product_cards(self, soup: BeautifulSoup) -> List[Tag]:
        """Extract product card elements from a listing page."""
        ...

    @abstractmethod
    def parse_product_card(self, card: Tag) -> Optional[Dict[str, Any]]:
        """Parse a single product card into a product dict. Returns None on failure."""
        ...

    def scrape_all(self) -> List[Dict[str, Any]]:
        """Orchestrate scraping: get URLs -> fetch pages -> parse cards -> return products."""
        self.products = []
        urls = self.get_page_urls()

        if not urls:
            logger.warning(f"[{self.STORE_NAME}] No page URLs to scrape")
            return self.products

        logger.info(f"[{self.STORE_NAME}] Scraping {len(urls)} page(s)...")

        for url in tqdm(urls, desc=f"Scraping {self.STORE_NAME}", unit="page"):
            soup = self.fetch_page(url)
            if not soup:
                continue

            cards = self.get_product_cards(soup)
            for card in cards:
                try:
                    product = self.parse_product_card(card)
                    if product and product.get("name"):
                        self.products.append(product)
                except Exception as e:
                    logger.warning(f"[{self.STORE_NAME}] Failed to parse product card: {e}")
                    continue

        logger.info(f"[{self.STORE_NAME}] Scraped {len(self.products)} products")
        return self.products

    def _find_text(self, element: Optional[Tag], default: str = "") -> str:
        """Safely extract text from a BeautifulSoup element."""
        if element is None:
            return default
        return element.get_text(strip=True)

    def _find_attr(self, element: Optional[Tag], attr: str, default: str = "") -> str:
        """Safely extract an attribute from a BeautifulSoup element."""
        if element is None:
            return default
        return element.get(attr, default) or default

    def _find_image_url(self, card: Tag) -> str:
        """Extract image URL from a product card, handling lazy loading patterns."""
        img = card.find('img')
        if not img:
            return ""
        # Try common lazy-load attributes first, then src
        for attr in ['data-src', 'data-lazy-src', 'data-original', 'srcset', 'src']:
            val = img.get(attr, '')
            if val:
                # For srcset, take the first URL
                if attr == 'srcset' and ',' in val:
                    val = val.split(',')[0].split()[0]
                elif attr == 'srcset':
                    val = val.split()[0]
                if val.startswith('http') or val.startswith('/'):
                    return val
        return ""
