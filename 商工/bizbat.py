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
    "查詢公司名稱", "公司名稱", "統一編號", "登記現況", "資本總額(元)", "代表人姓名", "公司所在地"
]
SELECTORS = {
    "search_input": "#qryCond",
    "search_button": "#qryBtn",
    "first_result_link": "#vParagraph > div > div.panel-heading > a",
    # 其餘欄位將用標題自動判斷
}

FIELD_KEYWORDS = {
    "company_name": "公司名稱",
    "unified_business_number": "統一編號",
    "company_status": "登記現況",
    "capital": "資本總額",
    "representative": "代表人",
    "company_address": "公司所在地",
}

# 自動根據標題關鍵字抓取欄位內容
async def extract_field_by_title(page, field_keyword):
    trs = page.locator("#tabCmpyContent > div > table > tbody > tr")
    count = await trs.count()
    for i in range(count):
        tds = trs.nth(i).locator("td")
        td_count = await tds.count()
        if td_count < 2:
            continue
        title = await tds.nth(0).inner_text()
        if field_keyword in title:
            value = await tds.nth(1).inner_text()
            return value.strip()
    return "查無資料"

async def extract_all_fields(page, field_keywords):
    result = {}
    for key, keyword in field_keywords.items():
        result[key] = await extract_field_by_title(page, keyword)
    return result

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
        # 取得所有搜尋結果的div
        result_panels = page.locator("#vParagraph > div")
        count = await result_panels.count()
        if count == 0:
            log_print(f"[WARNING] No result for '{query_name}'", log_enable)
            return None
        await asyncio.sleep(2)  # 點擊搜尋結果前等待2秒（配合查詢速度限制）
        selected_idx = None
        for i in range(count):
            panel = result_panels.nth(i)
            try:
                status_div = panel.locator("div").nth(1)  # 第2個div為狀態
                status_text = await status_div.inner_text(timeout=2000)
            except Exception:
                status_text = ""
            if "登記現況：核准設立" in status_text and selected_idx is None:
                selected_idx = i
        if selected_idx is None:
            selected_idx = 0
        # 點擊該panel下的a連結
        target_panel = result_panels.nth(selected_idx)
        link = target_panel.locator("div.panel-heading > a")
        await link.click()
        await page.wait_for_load_state('networkidle', timeout=10000)
        log_print(f"[INFO] 完成查詢：{query_name}", log_enable)
        # 自動依 tr 標題關鍵字抓取所有欄位
        fields = await extract_all_fields(page, FIELD_KEYWORDS)
        result = {"查詢公司名稱": query_name}
        # 對應中文欄位名稱
        mapping = {
            "company_name": "公司名稱",
            "unified_business_number": "統一編號",
            "company_status": "登記現況",
            "capital": "資本總額(元)",
            "representative": "代表人姓名",
            "company_address": "公司所在地",
        }
        for k, v in mapping.items():
            result[v] = fields.get(k, "查無資料")
        return result

    except Exception as e:
        print(f"[ERROR] {query_name}: {e}")
        return None

import time  # for timing

async def main():
    # log_enable 預設為 True，CMD print 永遠開啟
    log_enable = True

    start_time = time.time()
    log_print(f"[INFO] 啟動時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", log_enable)

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
            end_time = time.time()
            elapsed = end_time - start_time
            log_print(f"[INFO] 結束時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", log_enable)
            log_print(f"[INFO] 總運行時間: {elapsed:.2f} 秒", log_enable)
            await browser.close()
    save_results(results, log_enable)


if __name__ == "__main__":
    asyncio.run(main())
