"""BookScraper のユニットテスト。実際のサイトは叩かない。"""

import csv
import io
import textwrap
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import requests

from src.scraper import Book, BookScraper, ScraperError

# ---------------------------------------------------------------------------
# テスト用 HTML フィクスチャ
# ---------------------------------------------------------------------------

PAGE1_HTML = textwrap.dedent("""\
    <!DOCTYPE html>
    <html>
    <body>
      <section>
        <ol class="row">
          <li>
            <article class="product_pod">
              <p class="star-rating Three"></p>
              <h3><a href="catalogue/a-light-in-the-attic_1000/index.html"
                     title="A Light in the Attic">A Light in the Attic</a></h3>
              <p class="price_color">£51.77</p>
              <p class="availability">In stock</p>
            </article>
          </li>
          <li>
            <article class="product_pod">
              <p class="star-rating One"></p>
              <h3><a href="catalogue/tipping-the-velvet_999/index.html"
                     title="Tipping the Velvet">Tipping the Velvet</a></h3>
              <p class="price_color">£53.74</p>
              <p class="availability">Out of stock</p>
            </article>
          </li>
        </ol>
        <ul class="pager">
          <li class="next"><a href="catalogue/page-2.html">next</a></li>
        </ul>
      </section>
    </body>
    </html>
""")

PAGE2_HTML = textwrap.dedent("""\
    <!DOCTYPE html>
    <html>
    <body>
      <section>
        <ol class="row">
          <li>
            <article class="product_pod">
              <p class="star-rating Five"></p>
              <h3><a href="catalogue/soumission_998/index.html"
                     title="Soumission">Soumission</a></h3>
              <p class="price_color">£50.10</p>
              <p class="availability">In stock</p>
            </article>
          </li>
        </ol>
      </section>
    </body>
    </html>
""")


def _make_response(html: str, status: int = 200) -> MagicMock:
    resp = MagicMock(spec=requests.Response)
    resp.status_code = status
    resp.text = html
    resp.raise_for_status = MagicMock(
        side_effect=None if status < 400 else requests.HTTPError(response=resp)
    )
    return resp


# ---------------------------------------------------------------------------
# _parse_page のテスト
# ---------------------------------------------------------------------------


class TestParsePage:
    def setup_method(self):
        self.scraper = BookScraper(delay=0)

    def test_parses_title(self):
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(PAGE1_HTML, "lxml")
        books = self.scraper._parse_page(soup, "https://books.toscrape.com/")
        assert books[0].title == "A Light in the Attic"

    def test_parses_price(self):
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(PAGE1_HTML, "lxml")
        books = self.scraper._parse_page(soup, "https://books.toscrape.com/")
        assert books[0].price == pytest.approx(51.77)

    def test_parses_rating_three(self):
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(PAGE1_HTML, "lxml")
        books = self.scraper._parse_page(soup, "https://books.toscrape.com/")
        assert books[0].rating == 3

    def test_parses_rating_one(self):
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(PAGE1_HTML, "lxml")
        books = self.scraper._parse_page(soup, "https://books.toscrape.com/")
        assert books[1].rating == 1

    def test_in_stock_true(self):
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(PAGE1_HTML, "lxml")
        books = self.scraper._parse_page(soup, "https://books.toscrape.com/")
        assert books[0].in_stock is True

    def test_in_stock_false(self):
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(PAGE1_HTML, "lxml")
        books = self.scraper._parse_page(soup, "https://books.toscrape.com/")
        assert books[1].in_stock is False

    def test_url_is_absolute(self):
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(PAGE1_HTML, "lxml")
        books = self.scraper._parse_page(soup, "https://books.toscrape.com/")
        assert books[0].url.startswith("https://books.toscrape.com/")


# ---------------------------------------------------------------------------
# fetch_books のテスト (HTTP をモック)
# ---------------------------------------------------------------------------


class TestFetchBooks:
    def _make_scraper(self, side_effects: list) -> BookScraper:
        session = MagicMock(spec=requests.Session)
        session.headers = {}
        session.get = MagicMock(side_effect=side_effects)
        return BookScraper(delay=0, session=session)

    def test_returns_requested_count(self):
        scraper = self._make_scraper(
            [_make_response(PAGE1_HTML), _make_response(PAGE2_HTML)]
        )
        books = scraper.fetch_books(max_books=1)
        assert len(books) == 1

    def test_paginates_to_next_page(self):
        scraper = self._make_scraper(
            [_make_response(PAGE1_HTML), _make_response(PAGE2_HTML)]
        )
        books = scraper.fetch_books(max_books=3)
        assert len(books) == 3
        assert books[2].title == "Soumission"

    def test_stops_at_last_page_when_max_is_zero(self):
        scraper = self._make_scraper(
            [_make_response(PAGE1_HTML), _make_response(PAGE2_HTML)]
        )
        books = scraper.fetch_books(max_books=0)
        assert len(books) == 3

    def test_raises_scraper_error_on_http_error(self):
        scraper = self._make_scraper([_make_response("", status=500)])
        with pytest.raises(ScraperError):
            scraper.fetch_books(max_books=1)

    def test_raises_scraper_error_on_connection_error(self):
        session = MagicMock(spec=requests.Session)
        session.headers = {}
        session.get = MagicMock(side_effect=requests.ConnectionError("timeout"))
        scraper = BookScraper(delay=0, session=session)
        with pytest.raises(ScraperError):
            scraper.fetch_books(max_books=1)


# ---------------------------------------------------------------------------
# save_csv のテスト
# ---------------------------------------------------------------------------


class TestSaveCsv:
    BOOKS = [
        Book(title="Test Book", price=9.99, rating=4, in_stock=True, url="https://example.com/1"),
        Book(title="Another Book", price=14.50, rating=2, in_stock=False, url="https://example.com/2"),
    ]

    def test_creates_file(self, tmp_path: Path):
        scraper = BookScraper(delay=0)
        out = tmp_path / "out.csv"
        scraper.save_csv(self.BOOKS, str(out))
        assert out.exists()

    def test_csv_has_header(self, tmp_path: Path):
        scraper = BookScraper(delay=0)
        out = tmp_path / "out.csv"
        scraper.save_csv(self.BOOKS, str(out))
        content = out.read_text(encoding="utf-8-sig")
        assert content.startswith("title,price,rating,in_stock,url")

    def test_csv_row_count(self, tmp_path: Path):
        scraper = BookScraper(delay=0)
        out = tmp_path / "out.csv"
        scraper.save_csv(self.BOOKS, str(out))
        rows = list(csv.DictReader(out.open(encoding="utf-8-sig")))
        assert len(rows) == 2

    def test_csv_values(self, tmp_path: Path):
        scraper = BookScraper(delay=0)
        out = tmp_path / "out.csv"
        scraper.save_csv(self.BOOKS, str(out))
        rows = list(csv.DictReader(out.open(encoding="utf-8-sig")))
        assert rows[0]["title"] == "Test Book"
        assert float(rows[0]["price"]) == pytest.approx(9.99)
        assert int(rows[0]["rating"]) == 4

    def test_utf8_bom(self, tmp_path: Path):
        """Excel が正しく開けるよう BOM が付いていること。"""
        scraper = BookScraper(delay=0)
        out = tmp_path / "out.csv"
        scraper.save_csv(self.BOOKS, str(out))
        raw = out.read_bytes()
        assert raw[:3] == b"\xef\xbb\xbf", "UTF-8 BOM が存在しない"


# ---------------------------------------------------------------------------
# CLI のテスト
# ---------------------------------------------------------------------------


class TestCli:
    def test_help_exits_zero(self):
        from src.cli import build_parser

        parser = build_parser()
        with pytest.raises(SystemExit) as exc_info:
            parser.parse_args(["--help"])
        assert exc_info.value.code == 0

    def test_default_args(self):
        from src.cli import build_parser

        parser = build_parser()
        args = parser.parse_args([])
        assert args.output == "books.csv"
        assert args.max_books == 20
        assert args.delay == pytest.approx(1.0)
        assert args.verbose is False

    def test_main_returns_zero_on_success(self, tmp_path: Path):
        from src.cli import main

        out = tmp_path / "result.csv"
        with patch("src.cli.BookScraper") as MockScraper:
            instance = MockScraper.return_value
            instance.fetch_books.return_value = [
                Book("X", 1.0, 3, True, "https://example.com")
            ]
            code = main(["-o", str(out), "-n", "1"])
        assert code == 0

    def test_main_returns_one_on_scraper_error(self, tmp_path: Path):
        from src.cli import main

        out = tmp_path / "result.csv"
        with patch("src.cli.BookScraper") as MockScraper:
            instance = MockScraper.return_value
            instance.fetch_books.side_effect = ScraperError("boom")
            code = main(["-o", str(out)])
        assert code == 1
