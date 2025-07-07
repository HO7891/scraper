import asyncio
from playwright.async_api import async_playwright
import json
import csv
import os
from datetime import datetime
import sys
import argparse

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

# === LOG 設定區 ===
LOG_TO_FILE = True    # True=寫入本地log, False=只顯示於CMD（可於此一鍵切換）
LOG_FILENAME = "bizbat_log.txt"  # log檔名，預設與py同目錄
import os
LOGFILE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), LOG_FILENAME)

# log_print: 預設CMD顯示，log_to_file控制是否寫入本地檔

def log_print(msg, log_enable=True):
    if log_enable:
        print(msg)
    if LOG_TO_FILE:
        try:
            with open(LOGFILE_PATH, 'a', encoding='utf-8') as f:
                f.write(msg + '\n')
        except Exception as e:
            print(f"[ERROR] 寫入 log 檔失敗: {e}")

def fix_cmd_encoding():
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

def read_company_list(input_file, log_enable=False, logfile_path=None):
    if not os.path.exists(input_file):
        print(f"[ERROR] Input file not found: {input_file}")
        return []
    with open(input_file, 'r', encoding='utf-8') as f:
        company_list = [line.strip() for line in f if line.strip()]
    log_print(f"[INFO] 讀取公司列表完成，共 {len(company_list)} 筆", log_enable)
    return company_list

def save_results(data, log_enable=False, logfile_path=None):
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
    log_print(f"[SUCCESS] Data saved to {base}.json & {base}.csv", log_enable)

async def scrape_company_info(query_name, page, log_enable=False, logfile_path=None):
    await page.goto(BASE_URL)
    try:
        await page.fill(SELECTORS["search_input"], query_name)
        await page.click(SELECTORS["search_button"])
        await page.wait_for_load_state('networkidle', timeout=10000)
        result_links = page.locator(SELECTORS["first_result_link"])
        count = await result_links.count()
        if count == 0:
            log_print(f"[WARNING] No result for '{query_name}'", log_enable)
            return None
        await asyncio.sleep(2)  # 點擊首筆搜尋結果前等待2秒（配合查詢速度限制）
        await result_links.nth(0).click()
        await page.wait_for_load_state('networkidle', timeout=10000)
        log_print(f"[INFO] 完成查詢：{query_name}", log_enable)
        async def safe_inner_text(selector_key, field_name):
            try:
                return await page.inner_text(SELECTORS[selector_key], timeout=5000)
            except Exception as e:
                log_print(f"[WARNING] {query_name}: 欄位『{field_name}』查無資料 ({str(e)})", log_enable)
                return "查無資料"

        return {
            "查詢公司名稱": query_name,
            "公司名稱": await safe_inner_text("company_name", "公司名稱"),
            "統一編號": await safe_inner_text("unified_business_number", "統一編號"),
            "公司狀況": await safe_inner_text("company_status", "公司狀況"),
            "資本總額(元)": await safe_inner_text("capital", "資本總額(元)"),
            "代表人姓名": await safe_inner_text("representative", "代表人姓名"),
            "公司所在地": await safe_inner_text("company_address", "公司所在地"),
        }
    except Exception as e:
        print(f"[ERROR] {query_name}: {e}")
        return None

async def main():
    # log_enable 預設為 True，CMD print 永遠開啟
    log_enable = True

    fix_cmd_encoding()
    company_names = read_company_list(COMPANY_LIST_FILE, log_enable)
    if not company_names:
        print("[ERROR] No companies to process. Exiting.")
        return
    log_print(f"[INFO] Start scrape for {len(company_names)} companies.", log_enable)
    results = []
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        try:
            for idx, name in enumerate(company_names, 1):
                log_print(f"[INFO] 處理第 {idx}/{len(company_names)} 筆：{name}", log_enable)
                info = await scrape_company_info(name, page, log_enable)
                if info:
                    results.append(info)
        except Exception as e:
            print(f"[FATAL] 發生例外中斷：{e}")
            # 儲存目前已抓到的資料
            save_results(results, log_enable)
            # 截圖
            try:
                os.makedirs(OUTPUT_DIR, exist_ok=True)
                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                shot_path = os.path.join(OUTPUT_DIR, f"exception_{ts}.png")
                await page.screenshot(path=shot_path)
                print(f"[INFO] 已截圖於 {shot_path}")
                if LOG_TO_FILE:
                    with open(LOGFILE_PATH, 'a', encoding='utf-8') as f:
                        f.write(f"[FATAL] 發生例外中斷：{e}\n[INFO] 已截圖於 {shot_path}\n")
            except Exception as se:
                print(f"[ERROR] 截圖失敗: {se}")
        finally:
            await browser.close()
    save_results(results, log_enable)


if __name__ == "__main__":
    asyncio.run(main())
