"""CLI エントリーポイント。"""

import argparse
import io
import logging
import sys

from .scraper import BookScraper, ScraperError

# Windows のコンソールが CP932 でも日本語を正しく出力する
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
if sys.stderr.encoding and sys.stderr.encoding.lower() != "utf-8":
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")


def _non_negative_int(text: str) -> int:
    value = int(text)
    if value < 0:
        raise argparse.ArgumentTypeError("0 以上の整数を指定してください")
    return value


def _non_negative_float(text: str) -> float:
    value = float(text)
    if value < 0:
        raise argparse.ArgumentTypeError("0 以上の数を指定してください")
    return value


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="book-scraper",
        description="books.toscrape.com から書籍情報を取得して CSV に出力します。",
    )
    parser.add_argument(
        "-o",
        "--output",
        default="books.csv",
        help="出力 CSV ファイルパス (デフォルト: books.csv)",
    )
    parser.add_argument(
        "-n",
        "--max-books",
        type=_non_negative_int,
        default=20,
        metavar="N",
        help="取得件数 (デフォルト: 20、0 で全件)",
    )
    parser.add_argument(
        "--delay",
        type=_non_negative_float,
        default=1.0,
        metavar="SEC",
        help="ページ間の待機秒数 (デフォルト: 1.0)",
    )
    parser.add_argument(
        "--retries",
        type=_non_negative_int,
        default=2,
        metavar="N",
        help="通信に失敗したときの再試行回数 (デフォルト: 2)",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="詳細ログを表示する",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
        level=level,
        stream=sys.stderr,
    )

    scraper = BookScraper(delay=args.delay, retries=args.retries)
    try:
        print(
            f"スクレイピング開始 (取得上限: {'全件' if args.max_books == 0 else args.max_books}件)",
            flush=True,
        )
        books = scraper.fetch_books(max_books=args.max_books)
        scraper.save_csv(books, args.output)
        print(f"完了: {len(books)} 件を {args.output} に保存しました。")
        if getattr(scraper, "skipped", 0):
            print(f"注意: 読み取れなかった書籍 {scraper.skipped} 件を飛ばしました。")
        return 0
    except ScraperError as exc:
        logging.error("スクレイピングに失敗しました: %s", exc)
        return 1
    except OSError as exc:
        logging.error("ファイル書き込みに失敗しました: %s", exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())
