"""Books to Scrape のスクレイピングロジック。"""

import csv
import logging
import time
from dataclasses import dataclass, fields
from typing import Iterator
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://books.toscrape.com/"

RATING_MAP = {
    "One": 1,
    "Two": 2,
    "Three": 3,
    "Four": 4,
    "Five": 5,
}

logger = logging.getLogger(__name__)


@dataclass
class Book:
    title: str
    price: float
    rating: int
    in_stock: bool
    url: str


class ScraperError(Exception):
    """HTTP エラーやパースエラーをまとめる例外。"""


class BookScraper:
    def __init__(
        self,
        base_url: str = BASE_URL,
        delay: float = 1.0,
        session: requests.Session | None = None,
    ) -> None:
        self.base_url = base_url
        self.delay = delay
        self._session = session or requests.Session()
        self._session.headers["User-Agent"] = (
            "Mozilla/5.0 (compatible; BookScraperCLI/1.0; "
            "+https://github.com/sou4862ii-art/web-scraper-cli)"
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def fetch_books(self, max_books: int = 20) -> list[Book]:
        """カタログページを辿って書籍情報を返す。

        max_books=0 のとき全件取得。
        """
        books: list[Book] = []
        for book in self._iter_books():
            books.append(book)
            logger.info("[%d] %s", len(books), book.title)
            if max_books and len(books) >= max_books:
                break
        return books

    def save_csv(self, books: list[Book], path: str) -> None:
        """UTF-8 BOM 付き CSV で保存する (Excel 対応)。"""
        column_names = [f.name for f in fields(Book)]
        with open(path, "w", newline="", encoding="utf-8-sig") as fh:
            writer = csv.DictWriter(fh, fieldnames=column_names)
            writer.writeheader()
            for book in books:
                writer.writerow(
                    {
                        "title": book.title,
                        "price": book.price,
                        "rating": book.rating,
                        "in_stock": book.in_stock,
                        "url": book.url,
                    }
                )
        logger.debug("Saved %d records to %s", len(books), path)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _iter_books(self) -> Iterator[Book]:
        """ページネーションを辿りながら Book を yield する。"""
        page_url: str | None = self.base_url
        first = True
        while page_url:
            if not first:
                time.sleep(self.delay)
            first = False

            soup = self._get_soup(page_url)
            yield from self._parse_page(soup, page_url)

            next_tag = soup.select_one("li.next a")
            page_url = urljoin(page_url, next_tag["href"]) if next_tag else None

    def _get_soup(self, url: str) -> BeautifulSoup:
        logger.debug("GET %s", url)
        try:
            resp = self._session.get(url, timeout=10)
            resp.raise_for_status()
        except requests.RequestException as exc:
            raise ScraperError(f"Request failed: {url}") from exc
        return BeautifulSoup(resp.text, "lxml")

    def _parse_page(self, soup: BeautifulSoup, page_url: str) -> list[Book]:
        books = []
        for article in soup.select("article.product_pod"):
            books.append(self._parse_article(article, page_url))
        return books

    def _parse_article(self, article: BeautifulSoup, page_url: str) -> Book:
        # タイトル
        title_tag = article.select_one("h3 a")
        title = title_tag["title"] if title_tag else ""

        # 詳細ページ URL
        href = title_tag["href"] if title_tag else ""
        # catalogue/ から始まる相対パスを絶対 URL に変換
        book_url = urljoin(page_url, href)

        # 価格 (£ を除いて float に)
        price_tag = article.select_one("p.price_color")
        price_text = price_tag.get_text(strip=True) if price_tag else "0"
        price = float(price_text.replace("£", "").replace("Â", "").strip())

        # 評価 (クラス名 "rating One" など)
        rating_tag = article.select_one("p.star-rating")
        rating_class = rating_tag["class"][1] if rating_tag else "Zero"
        rating = RATING_MAP.get(rating_class, 0)

        # 在庫
        avail_tag = article.select_one("p.availability")
        in_stock = "In stock" in avail_tag.get_text() if avail_tag else False

        return Book(
            title=title,
            price=price,
            rating=rating,
            in_stock=in_stock,
            url=book_url,
        )
