import re
from pathlib import Path
from typing import Dict, List
import pandas as pd
from playwright.sync_api import sync_playwright

from src.config import ANTI_BOT_MARKERS
from src.utils import export_excel as utils_export_excel


def parse_ref_code(text: str) -> str:
    if not text:
        return ""
    m = re.match(r"^\[?\[([^\]]+)\]", text)
    return m.group(1).strip() if m else ""


def build_browser_context(playwright):
    browser = playwright.chromium.launch(
        headless=True,
        args=["--disable-blink-features=AutomationControlled"],
    )
    context = browser.new_context(
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        locale="zh-CN",
        viewport={"width": 1920, "height": 1080},
        extra_http_headers={
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Referer": "https://www.ssgdfs.com/cn/main",
        },
    )
    context.add_init_script(
        """
        Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
        Object.defineProperty(navigator, 'platform', { get: () => 'Win32' });
        Object.defineProperty(navigator, 'languages', { get: () => ['zh-CN', 'zh', 'en-US', 'en'] });
        window.chrome = { runtime: {} };
        """
    )
    return browser, context


def open_search_page(page, keyword: str, start_count: int) -> None:
    url = (
        "https://www.ssgdfs.com/cn/search/resultsTotal"
        f"?startCount={start_count}&offShop=&suggestReSearchReq=true"
        f"&orReSearchReq=true&query={keyword}"
    )
    response = page.goto(url, wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(1800)

    body_text = page.inner_text("body") if page.locator("body").count() else ""
    body_lower = body_text.lower()
    status = response.status if response else None
    if status in {403, 406} or any(marker in body_lower for marker in ANTI_BOT_MARKERS):
        raise RuntimeError("命中风控页，请稍后重试或先手动访问站点后再执行。")


def extract_page_items(page, keyword: str):
    return page.evaluate(
        r"""
        ([kw]) => {
          const rows = [];
          const cards = Array.from(document.querySelectorAll('li.prodCont'));
          for (const li of cards) {
            const brand = (li.querySelector('.brandName')?.textContent || '').trim();
            const name = (li.querySelector('.prodName')?.textContent || '').trim();
            const price = (li.querySelector('.saleDollar')?.textContent || '').replace(/\s+/g, '');
            const a = li.querySelector('a[data-param3]');
            const dataParam3 = a ? (a.getAttribute('data-param3') || '') : '';
            const onclick = a ? (a.getAttribute('onclick') || '') : '';

            let goosCd = '';
            const m = onclick.match(/goos_cd\s*:\s*'([^']+)'/i);
            if (m) goosCd = m[1];

            rows.push({
              keyword: kw,
              brand,
              name,
              price,
              dataParam3,
              goosCd
            });
          }

          const totalMatch = (document.body?.innerText || '').match(/(\d+)\s*个结果/);
          const totalCount = totalMatch ? Number(totalMatch[1]) : 0;
          const listCount = Number(document.querySelector('#filterSelects')?.getAttribute('data-list-count') || 40);
          return { rows, totalCount, listCount };
        }
        """,
        [keyword],
    )


def scrape(keyword: str) -> List[Dict]:
    merged = {}

    def row_key(row: dict) -> str:
        code = (row.get("goosCd") or "").strip()
        if code:
            return f"code:{code}"
        return "fallback:" + "|".join(
            [
                (row.get("brand") or "").strip(),
                (row.get("name") or "").strip(),
                parse_ref_code(row.get("dataParam3", "")),
            ]
        )

    with sync_playwright() as p:
        browser, context = build_browser_context(p)
        page = context.new_page()
        page.goto("https://www.ssgdfs.com/cn/main", wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(2500)

        for round_idx in range(1, 3):
            before = len(merged)
            open_search_page(page, keyword, 0)
            first = extract_page_items(page, keyword)
            total = first["totalCount"] or len(first["rows"])
            page_size = first["listCount"] or 40

            for r in first["rows"]:
                merged[row_key(r)] = r

            for start in range(page_size, total, page_size):
                open_search_page(page, keyword, start)
                data = extract_page_items(page, keyword)
                for r in data["rows"]:
                    merged[row_key(r)] = r
                print(f"第{round_idx}轮抓取分页 startCount={start}，当前累计 {len(merged)}")

            added = len(merged) - before
            print(f"第{round_idx}轮完成：新增 {added} 条，累计 {len(merged)} 条")
            if added == 0:
                break

        browser.close()

    all_rows = list(merged.values())
    cleaned = []
    for row in all_rows:
        cleaned.append(
            {
                "关键词": row.get("keyword", ""),
                "品牌": row.get("brand", ""),
                "商品名": row.get("name", ""),
                "销售价": row.get("price", ""),
                "RefNO": parse_ref_code(row.get("dataParam3", "")),
                "商品编码": row.get("goosCd", ""),
            }
        )

    cleaned = [r for r in cleaned if r["商品名"] or r["RefNO"] or r["商品编码"]]
    return cleaned


def export_excel(rows, keyword: str, output_dir: Path) -> Path:
    return utils_export_excel(rows, keyword, output_dir)
