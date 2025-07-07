import asyncio
from playwright.async_api import async_playwright
import json
import csv
import os
from datetime import datetime
import sys

BASE_URL = "https://findbiz.nat.gov.tw/fts/query/QueryBar/queryInit.do"
OUTPUT_DIR = "./output_biz"
COMPANY_LIST_FILE = "company_list.txt"
CSV_HEADERS = [
    "查詢公司名稱", "公司名稱", "統一編號", "公司狀況", "資本總額(元)", "代表人姓名", "公司所在地"
]
SELECTORS = {
    "search_input": "#qryCond",
    "search_button": "#qryBtn",
    "first_result_link": "#vParagraph > div > div.panel-heading > a",
    "company_name": "#tabCmpyContent > div > table > tbody > tr:nth-child(4) > td:nth-child(2)",
    "unified_business_number": "#tabCmpyContent > div > table > tbody > tr:nth-child(1) > td:nth-child(2)",
    "company_status": "#tabCmpyContent > div > table > tbody > tr:nth-child(2) > td:nth-child(2)",
    "capital": "#tabCmpyContent > div > table > tbody > tr:nth-child(6) > td:nth-child(2)",
    "representative": "#tabCmpyContent > div > table > tbody > tr:nth-child(10) > td:nth-child(2)",
    "company_address": "#tabCmpyContent > div > table > tbody > tr:nth-child(11) > td:nth-child(2)",
}

def fix_cmd_encoding():
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

def read_company_list(input_file):
    if not os.path.exists(input_file):
        print(f"[ERROR] Input file not found: {input_file}")
        return []
    with open(input_file, 'r', encoding='utf-8') as f:
        return [line.strip() for line in f if line.strip()]

def save_results(data):
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base = os.path.join(OUTPUT_DIR, f"biz_company_info_{timestamp}")
    with open(base + ".json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    if data:
        with open(base + ".csv", "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=CSV_HEADERS)
            writer.writeheader()
            writer.writerows(data)
    print(f"[SUCCESS] Data saved to {base}.json & {base}.csv")

async def scrape_company_info(query_name, page):
    await page.goto(BASE_URL)
    try:
        await page.fill(SELECTORS["search_input"], query_name)
        await page.click(SELECTORS["search_button"])
        await page.wait_for_load_state('networkidle', timeout=10000)
        result_links = page.locator(SELECTORS["first_result_link"])
        count = await result_links.count()
        if count == 0:
            print(f"[WARNING] No result for '{query_name}'")
            return None
        await asyncio.sleep(2)  # 點擊首筆搜尋結果前等待2秒（配合查詢速度限制）
        await result_links.nth(0).click()
        await page.wait_for_load_state('networkidle', timeout=10000)
        return {
            "查詢公司名稱": query_name,
            "公司名稱": await page.inner_text(SELECTORS["company_name"]),
            "統一編號": await page.inner_text(SELECTORS["unified_business_number"]),
            "公司狀況": await page.inner_text(SELECTORS["company_status"]),
            "資本總額(元)": await page.inner_text(SELECTORS["capital"]),
            "代表人姓名": await page.inner_text(SELECTORS["representative"]),
            "公司所在地": await page.inner_text(SELECTORS["company_address"]),
        }
    except Exception as e:
        print(f"[ERROR] {query_name}: {e}")
        return None

async def main():
    fix_cmd_encoding()
    company_names = read_company_list(COMPANY_LIST_FILE)
    if not company_names:
        print("[ERROR] No companies to process. Exiting.")
        return
    print(f"[INFO] Start scrape for {len(company_names)} companies.")
    results = []
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        for name in company_names:
            info = await scrape_company_info(name, page)
            if info:
                results.append(info)
        await browser.close()
    save_results(results)

if __name__ == "__main__":
    asyncio.run(main())
