# 書籍情報スクレイパー CLI

[![CI](https://github.com/sou4862ii-art/web-scraper-cli/actions/workflows/tests.yml/badge.svg)](https://github.com/sou4862ii-art/web-scraper-cli/actions/workflows/tests.yml)
[![Python](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12-blue)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

[books.toscrape.com](https://books.toscrape.com/)（スクレイピング練習用公認サイト）から書籍情報を収集し、Excel で開ける CSV ファイルに出力するコマンドラインツールです。

---

## 目次

- [機能概要](#機能概要)
- [技術スタック](#技術スタック)
- [セットアップ](#セットアップ)
- [使い方](#使い方)
- [出力フォーマット](#出力フォーマット)
- [開発・テスト](#開発テスト)
- [設計のポイント](#設計のポイント)
- [ライセンス](#ライセンス)

---

## 機能概要

| 機能 | 詳細 |
|---|---|
| 取得項目 | タイトル・価格・評価（1〜5）・在庫状況・URL |
| ページネーション | 全 50 ページ（1000 件）の自動走査 |
| 出力形式 | UTF-8 BOM 付き CSV（Excel 直接開封対応） |
| 件数制限 | `-n` オプションで取得件数を柔軟に指定 |
| レート制限 | `--delay` でサーバーへの負荷を調節 |
| ログ | `-v` で詳細なリクエストログを表示 |

---

## 技術スタック

| カテゴリ | 採用技術 | 選定理由 |
|---|---|---|
| HTTP クライアント | [requests](https://requests.readthedocs.io/) | シンプルな API、豊富な実績 |
| HTML パーサー | [BeautifulSoup4](https://www.crummy.com/software/BeautifulSoup/) + lxml | CSS セレクタで直感的に要素を取得 |
| CLI フレームワーク | argparse（標準ライブラリ） | 外部依存ゼロ、十分な機能 |
| テスト | [pytest](https://docs.pytest.org/) + unittest.mock | モックで実サイトを叩かない設計 |
| CI | GitHub Actions | Python 3.10/3.11/3.12 マトリックス |

---

## セットアップ

### 前提条件

- Python 3.10 以上

### インストール

```bash
# リポジトリをクローン
git clone https://github.com/sou4862ii-art/web-scraper-cli.git
cd web-scraper-cli

# 仮想環境を作成・有効化（推奨）
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# 依存パッケージをインストール
pip install -r requirements.txt
```

---

## 使い方

```bash
python -m src.cli [オプション]
```

### オプション一覧

| オプション | デフォルト | 説明 |
|---|---|---|
| `-o`, `--output` | `books.csv` | 出力先 CSV ファイルパス |
| `-n`, `--max-books` | `20` | 取得件数（`0` で全件 1000 件） |
| `--delay` | `1.0` | ページ間の待機秒数（サーバー負荷対策） |
| `-v`, `--verbose` | false | 詳細ログを標準エラーに出力 |

### 実行例

```bash
# 基本: 20 件取得して books.csv に保存
python -m src.cli

# 50 件取得、出力先を指定
python -m src.cli -n 50 -o output/books_50.csv

# 全件取得（約 1000 件）、待機時間を短縮
python -m src.cli -n 0 --delay 0.5

# 詳細ログ付きで実行
python -m src.cli -v -n 10
```

### 実行例（出力）

```
スクレイピング開始 (取得上限: 20件)
完了: 20 件を books.csv に保存しました。
```

---

## 出力フォーマット

UTF-8 BOM 付き CSV。Excel で文字化けせずに直接開けます。

| カラム名 | 型 | 説明 |
|---|---|---|
| `title` | str | 書籍タイトル |
| `price` | float | 価格（英ポンド） |
| `rating` | int | 評価（1〜5） |
| `in_stock` | bool | 在庫あり: `True` / なし: `False` |
| `url` | str | 詳細ページの URL |

```csv
title,price,rating,in_stock,url
A Light in the Attic,51.77,3,True,https://books.toscrape.com/catalogue/a-light-in-the-attic_1000/index.html
Tipping the Velvet,53.74,1,False,https://books.toscrape.com/catalogue/tipping-the-velvet_999/index.html
```

---

## 開発・テスト

```bash
# 開発用依存をインストール
pip install -r requirements-dev.txt

# テスト実行
pytest tests/ -v

# カバレッジ付きで実行
pytest tests/ --cov=src --cov-report=term-missing
```

### テスト設計

- **実サイトへのアクセスは一切行いません。** `unittest.mock` で HTTP レスポンスをモック化しています。
- テスト対象ごとにクラスを分離し、単体テストと統合シナリオを明確に区別しています。

```
tests/
└── test_scraper.py
    ├── TestParsePage   # HTML パース処理の単体テスト
    ├── TestFetchBooks  # ページネーション・エラーハンドリングのテスト
    ├── TestSaveCsv     # CSV 出力・BOM 付与のテスト
    └── TestCli         # CLI 引数パース・終了コードのテスト
```

---

## 設計のポイント

### 関心の分離

```
src/
├── scraper.py  # HTTP 取得 / HTML パース / CSV 保存
└── cli.py      # 引数解析 / ログ設定 / エントリーポイント
```

`BookScraper` クラスに `session` を外部注入できる設計にすることで、テスト時にモックセッションを渡せます。

### ページネーション

「次へ」ボタン（`li.next a`）を辿り、存在しなくなるまでリクエストを続けます。各リクエスト間に `--delay` 秒のウェイトを挟みサーバーへの配慮をしています。

### エラーハンドリング

HTTP エラー・接続エラーはいずれも `ScraperError` に変換し、CLI 層で捕捉して exit code `1` を返します。

### Excel 対応 CSV

`encoding="utf-8-sig"` を指定することで、BOM（Byte Order Mark）付き UTF-8 として保存します。Windows の Excel は BOM を参照して文字コードを自動判定するため、文字化けが発生しません。

---

## ライセンス

[MIT License](LICENSE)
