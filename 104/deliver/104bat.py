import asyncio
from playwright.async_api import async_playwright, Page, BrowserContext
import json
import csv
import os
import time
from datetime import datetime
import argparse
import random
from fake_useragent import UserAgent
import sys
import re # 引入 re 模組，用於正則表達式提取 company_id

# 解決 CMD 輸出亂碼問題 (這行必須放在所有 print 語句和相關模組導入之後)
sys.stdout.reconfigure(encoding='utf-8')

# 輔助函數：儲存結果
def save_results(data, output_format='json'):
    if not os.path.exists("./output"):
        os.makedirs("./output")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    if output_format == 'json':
        filename = f"./output/104_company_info_{timestamp}.json"
        print(f"嘗試將資料儲存至 {filename}...")
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
            print(f"資料已成功儲存至 {filename}")
        except Exception as e:
            print(f"儲存 JSON 檔案時發生錯誤 {filename}: {e}")
    elif output_format == 'csv':
        filename = f"./output/104_company_info_{timestamp}.csv"
        print(f"嘗試將資料儲存至 {filename}...")
        if not data:
            print("沒有資料可儲存至 CSV。")
            return

        # 直接指定欄位順序，提升效率與穩定性
        keys = [
            "公司名稱", "公司網址", "產業類別", "公司地址", "主要服務", "資本額", "員工人數", "公司官網", "公司簡介"
        ]

        try:
            with open(filename, 'w', encoding='utf-8-sig', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=keys)
                writer.writeheader()
                writer.writerows(data)
            print(f"資料已成功儲存至 {filename}")
        except Exception as e:
            print(f"儲存 CSV 檔案時發生錯誤 {filename}: {e}")
    else:
        print("輸出格式無效。請選擇 'json' 或 'csv'。")

# 輔助函數：讀取公司清單
def read_company_list(input_file=None):
    import os
    company_names = []
    checked_sources = []
    def read_txt(path):
        with open(path, 'r', encoding='utf-8') as f:
            return [line.strip() for line in f if line.strip()]
    def read_csv(path):
        with open(path, 'r', encoding='utf-8-sig') as f:  # 強制帶 BOM，解決 Excel 亂碼
            reader = csv.reader(f)
            return [row[0].strip() for row in reader if row and row[0].strip() and '公司名稱' not in row[0]]

    if input_file:
        ext = os.path.splitext(input_file)[1].lower()
        if ext == '.txt':
            company_names = read_txt(input_file)
            print(f"[INFO] 使用來源檔案: {input_file}")
        elif ext == '.csv':
            company_names = read_csv(input_file)
            print(f"[INFO] 使用來源檔案: {input_file}")
        else:
            print(f"[錯誤] 不支援的公司清單檔案格式: {input_file}")
    else:
        # 依序檢查：當前目錄 txt > csv > ./104/txt > ./104/csv
        candidates = [
            'company_list.txt',
            'company_list.csv',
            os.path.join('104', 'company_list.txt'),
            os.path.join('104', 'company_list.csv'),
        ]
        for path in candidates:
            if os.path.exists(path):
                checked_sources.append(path)
                if path.endswith('.txt'):
                    company_names = read_txt(path)
                else:
                    company_names = read_csv(path)
                print(f"[INFO] 自動偵測到來源檔案: {path}")
                break
        if not company_names:
            print("[錯誤] 未找到公司名稱清單 company_list.txt 或 company_list.csv，請用 --input-file 指定！")
    return company_names

# 瀏覽器啟動參數
def args_for_browser():
    return [
        '--no-sandbox',
        '--disable-setuid-sandbox',
        '--disable-blink-features=AutomationControlled',
        '--no-default-browser-check',
        '--no-first-run',
        '--disable-infobars',
        '--start-maximized'
    ]

# 核心邏輯：透過名稱搜尋公司並獲取其 ID
async def find_company_id_by_name(target_company_name: str, page: Page, headless_mode: bool, debug_screenshot: bool) -> str | None:
    """
    透過公司名稱在 104 網站上搜尋，並返回第一個匹配公司的 company_id。
    :param target_company_name: 要搜尋的公司名稱。
    :param page: Playwright Page 物件。
    :param headless_mode: 是否為無頭模式 (用於 CAPTCHA 提示)。
    :return: 找到的公司 ID (字串) 或 None (如果未找到)。
    """
    print(f"\n--- 正在搜尋公司名稱: {target_company_name} 以取得 Company ID ---")
    search_url = "https://www.104.com.tw/company/search/" # 公司搜尋頁面 (注意: 是 /company/search/ 而非 /company/main/)
    
    try:
        # 導航至公司搜尋頁面
        await page.goto(search_url, wait_until='domcontentloaded', timeout=45000)
        await page.wait_for_timeout(random.uniform(500, 1000))

        # 偵錯用：截圖搜尋頁面剛載入時的狀態
        if debug_screenshot:
            await page.screenshot(path=f"./output/debug_search_page_before_typing_{target_company_name}.png")

        # 檢查是否被重定向到 CAPTCHA 或反爬蟲頁面
        if any(keyword in page.url.lower() for keyword in ['captcha', 'bot_challenge', 'cloudflare']):
            print(f"  偵測到 CAPTCHA/bot 挑戰頁面 for 搜尋頁面。")
            if not headless_mode:
                print("  請在瀏覽器視窗中解決 CAPTCHA 後，回到終端機按 Enter 鍵繼續...")
                input()
                await page.wait_for_timeout(random.uniform(5000, 8000)) 
                # 再次檢查 CAPTCHA 是否解決
                if any(keyword in page.url.lower() for keyword in ['captcha', 'bot_challenge', 'cloudflare']):
                    print("  CAPTCHA 仍未解決，無法繼續。")
                    return None
            else:
                print("  無頭模式無法處理 CAPTCHA，終止搜尋。")
                return None

        # 找到搜尋框並輸入公司名稱
        search_input_selector = 'input[placeholder^="關鍵字"]' # 只選第一個關鍵字 input
        search_button_selector = 'button.btn.btn-primary.search-btn' # 搜尋按鈕的選擇器

        search_input = page.locator(search_input_selector).first
        await search_input.wait_for(state='visible', timeout=10000)
        await search_input.fill(target_company_name)
        print(f"  已輸入 '{target_company_name}' 到搜尋框。")
        
        # 送出 Enter 鍵觸發搜尋
        await search_input.press('Enter')
        print("  送出 Enter 鍵觸發搜尋...")
        
        # 等待搜尋結果的公司連結元素出現（桌機版 class）
        company_link_selector = 'a.company-name-link--pc'
        await page.wait_for_selector(company_link_selector, timeout=15000)
        await page.wait_for_timeout(random.uniform(300, 600)) # 額外等待，模擬人類行為

        # 偵錯用：截圖搜尋結果頁面
        if debug_screenshot:
            await page.screenshot(path=f"./output/debug_search_results_page_{target_company_name}.png")

        # 檢查是否有「沒有找到公司」的提示 (根據 104 實際提示文字調整)
        no_results_locator = page.locator("text=目前站臺並無此公司")
        if await no_results_locator.is_visible():
             print(f"  搜尋 '{target_company_name}' 未找到結果。")
             return None

        # 獲取搜尋結果中第一個真的可見的公司連結的 href 屬性
        company_links = page.locator(company_link_selector)
        count = await company_links.count()
        first_visible_link = None
        for i in range(count):
            link = company_links.nth(i)
            if await link.is_visible():
                first_visible_link = link
                break
        if not first_visible_link:
            print(f"  沒有找到任何可見的公司連結。")
            return None
        href = await first_visible_link.get_attribute('href')
        
        if not href:
            print(f"  找到公司連結但無法提取其 href 屬性。")
            return None
        
        # 若為 r.104.com.tw 跳轉連結，需先 decode 取出真正的公司網址
        import urllib.parse
        if href.startswith("https://r.104.com.tw/m104?url="):
            parsed = urllib.parse.urlparse(href)
            query = urllib.parse.parse_qs(parsed.query)
            real_url = query.get("url", [""])[0]
            real_url = urllib.parse.unquote(real_url)
        else:
            real_url = href

        # 從 real_url 中提取 company_id
        match = re.search(r'/company/([^/?#]+)', real_url)
        if match:
            company_id = match.group(1)
            print(f"  成功從 '{target_company_name}' 的搜尋結果中提取到 Company ID: {company_id}")
            return company_id
        else:
            print(f"  無法從 URL '{real_url}' 中提取 Company ID。URL 不符合預期格式。")
            return None

    except Exception as e:
        print(f"  搜尋 '{target_company_name}' 時發生錯誤: {e}")
        print(f"  請檢查 output/debug_search_results_page_{target_company_name}.png 截圖和您 F12 檢查的選擇器。")
        await page.screenshot(path=f"./output/fail_search_for_{target_company_name}.png")
        return None

# 核心邏輯：抓取單一公司詳細資訊
async def scrape_single_company_info(company_id: str, page: Page, debug_screenshot: bool):
    """
    抓取單一公司 ID 的詳細資訊。
    :param company_id: 104 公司連結中的 ID 部分，例如 '5fw9oqo'
    :param page: Playwright Page 物件 (為了避免獨立啟動瀏覽器，直接傳入)。
    """
    print(f"\n--- 正在抓取公司 ID: {company_id} 的詳細資訊 ---")

    company_detail_url = f"https://www.104.com.tw/company/{company_id}?tab=cmp_1"
    scraped_data_entry = {}

    # ===== 協助函數：多 selector 嘗試抓欄位 =====
    async def 抓欄位(selector_list, 欄位名, get_text_func=None, extra_fallback=None):
        for sel in selector_list:
            try:
                el = page.locator(sel).first
                if await el.count() == 0:
                    continue
                await el.wait_for(state='attached', timeout=5000)
                if get_text_func:
                    text = await get_text_func(el)
                else:
                    text = await el.inner_text()
                if text and text.strip():
                    return text.strip()
            except Exception as e:
                print(f"[警告] {欄位名} selector 失敗: {sel}，錯誤: {e}")
        # 額外備用
        if extra_fallback:
            try:
                return await extra_fallback()
            except Exception as e:
                print(f"[警告] {欄位名} 額外備用抓取失敗: {e}")
        print(f"[錯誤] 無法抓取 {欄位名}")
        return f"N/A_{欄位名}"

    try:
        print(f"  導航至公司詳情頁: {company_detail_url}")
        await page.goto(company_detail_url, wait_until='domcontentloaded', timeout=45000)
        await page.wait_for_timeout(random.uniform(500, 1000)) # 隨機等待 0.5-1 秒確保頁面加載
        if debug_screenshot:
            await page.screenshot(path=f"./output/debug_detail_page_{company_id}.png")
            try:
                html_content = await page.content()
                html_filename = f"./output/dump_detail_html_{company_id}.html"
                with open(html_filename, 'w', encoding='utf-8') as f:
                    f.write(html_content)
                print(f"  當前頁面 HTML 已保存至: {html_filename}")
            except Exception as html_err:
                print(f"  保存 HTML 失敗: {html_err}")

        # 檢查是否被重定向到 CAPTCHA 或反爬蟲頁面
        if any(keyword in page.url.lower() for keyword in ['captcha', 'bot_challenge', 'cloudflare']):
            print(f"  偵測到 CAPTCHA/bot 挑戰頁面 for 詳細頁面。無法繼續抓取。")
            return None

        # ===== 主要欄位抓取（僅抓實際存在且需要的欄位） =====
        # 公司名稱
        公司名稱 = await 抓欄位([
            'div.company-main__name h1',
            'h1.d-inline',
            'h1',
        ], '公司名稱')
        scraped_data_entry['公司名稱'] = 公司名稱
        scraped_data_entry['公司網址'] = company_detail_url
        print(f"  公司名稱: {公司名稱}")


        # 產業類別（a.t3.jb-link.jb-link-blue）
        公司產業 = await 抓欄位([
            'a.t3.jb-link.jb-link-blue',
        ], '產業類別')
        scraped_data_entry['產業類別'] = 公司產業
        print(f"  產業類別: {公司產業}")

        # 主要服務/產品、資本額、員工人數（遍歷所有 p.t3.mb-0 判斷內容）
        公司地址 = "N/A_公司地址"
        主要服務 = "N/A_主要服務"
        資本額 = "N/A_資本額"
        員工人數 = "N/A_員工人數"
        try:
            all_p = page.locator('p.t3.mb-0')
            for i in range(await all_p.count()):
                txt = (await all_p.nth(i).inner_text()).strip()
                if not txt or txt == "暫不提供":
                    continue
                # 地址判斷：有「地址」或明顯地址格式
                if "地址" in txt or (any(x in txt for x in ["路", "街", "號"]) and len(txt) > 6):
                    公司地址 = txt.replace("地址", "").strip()
                # 資本額判斷：有「資本額」或金額格式或查詢字眼
                elif ("資本額" in txt or re.search(r"[億萬,0-9]+元", txt) or ("元" in txt or "萬" in txt or "億" in txt and "查詢" in txt)):
                    資本額 = re.sub(r"經濟部商業司查詢|查詢", "", txt.replace("資本額", "")).strip()
                elif "員工人數" in txt:
                    員工人數 = txt.replace("員工人數", "").strip()
                elif re.match(r'^[\d,]+人$', txt):
                    員工人數 = txt
                elif txt not in [公司產業] and not any(key in txt for key in ["地址", "資本額", "員工人數"]):
                    主要服務 = txt
        except Exception as e:
            print(f"[警告] 主要服務/產品/資本額/員工人數/地址抓取失敗: {e}")
        scraped_data_entry['公司地址'] = 公司地址
        scraped_data_entry['主要服務'] = 主要服務
        scraped_data_entry['資本額'] = 資本額
        scraped_data_entry['員工人數'] = 員工人數
        print(f"  公司地址: {公司地址}")
        print(f"  主要服務: {主要服務}")
        print(f"  資本額: {資本額}")
        print(f"  員工人數: {員工人數}")

        # 公司官網（a[data-gtm-content='公司網址']，直接取 href）
        async def 網址_get_text(el):
            return await el.get_attribute('href')
        公司官網 = await 抓欄位([
            "a[data-gtm-content='公司網址']",
        ], '公司官網', get_text_func=網址_get_text)
        scraped_data_entry['公司官網'] = 公司官網
        print(f"  公司官網: {公司官網}")

        # 公司簡介
        company_desc_el = page.locator('div.company-main__content').first.or_(
            page.locator('div.profile-content__text').first)
        try:
            company_desc = await company_desc_el.inner_text()
        except Exception:
            try:
                company_desc = await page.locator('meta[name="description"]').get_attribute('content')
            except Exception:
                company_desc = "N/A_公司簡介"
        scraped_data_entry['公司簡介'] = company_desc.strip()
        print(f"    公司簡介: {company_desc[:50]}...") # 打印前50字


        print(f"  成功抓取 {公司名稱.strip()} 的詳細資訊。")
        
    except Exception as e:
        print(f"  抓取公司 ID {company_id} 詳細資訊失敗: {e}")
        await page.screenshot(path=f"./output/fail_detail_page_{company_id}.png")
        scraped_data_entry = None
    
    return scraped_data_entry

async def unified_main():
    import argparse
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group()
    group.add_argument('company_name', nargs='?', type=str, help='要查詢的公司名稱')
    group.add_argument('-i', '--input-file', type=str, default=None, help='公司名稱清單檔案（txt 或 csv）')
    parser.add_argument('--headless', action='store_true', help='是否啟用無頭模式')
    parser.add_argument('--debug-screenshot', action='store_true', help='是否保存 debug 截圖/HTML')
    args = parser.parse_args()

    from playwright.async_api import async_playwright
    from fake_useragent import UserAgent

    all_scraped_data = []
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=args.headless, args=args_for_browser())
        context = await browser.new_context(
            user_agent=UserAgent().random,
            viewport={"width": 1280, "height": 800},
            locale="zh-TW"
        )
        page = await context.new_page()
        if args.company_name:
            cname = args.company_name
            print(f"[單筆查詢] 公司名稱: {cname}")
            company_id = await find_company_id_by_name(cname, page, args.headless, args.debug_screenshot)
            if not company_id:
                print(f"  [查詢失敗] 找不到 {cname} 的公司 ID。")
            else:
                print(f"  [查詢成功] {cname} 的 104 公司 ID: {company_id}")
                scraped_data_entry = await scrape_single_company_info(company_id, page, args.debug_screenshot)
                if scraped_data_entry:
                    print(f"  [LOG] 來源名稱: {cname}，104 首筆名稱: {scraped_data_entry.get('公司名稱', 'N/A')}")
                    all_scraped_data.append(scraped_data_entry)
                    save_results(all_scraped_data, output_format='csv')
                    save_results(all_scraped_data, output_format='json')
                else:
                    print(f"  [查詢失敗] 無法抓取 {cname} 詳細資料。")
        else:
            company_names = read_company_list(args.input_file)
            if not company_names:
                print("[錯誤] 沒有可查詢的公司名稱，請檢查來源檔案！")
                return
            print(f"[批次查詢] 將查詢公司數量: {len(company_names)}")
            for idx, cname in enumerate(company_names, 1):
                print(f"\n[批次 {idx}/{len(company_names)}] 來源公司名稱: {cname}")
                company_id = await find_company_id_by_name(cname, page, args.headless, args.debug_screenshot)
                if not company_id:
                    print(f"  [查詢失敗] 找不到 {cname} 的公司 ID，略過。")
                    continue
                print(f"  [查詢成功] {cname} 的 104 公司 ID: {company_id}")
                scraped_data_entry = await scrape_single_company_info(company_id, page, args.debug_screenshot)
                if scraped_data_entry:
                    print(f"  [LOG] 來源名稱: {cname}，104 首筆名稱: {scraped_data_entry.get('公司名稱', 'N/A')}")
                    all_scraped_data.append(scraped_data_entry)
                else:
                    print(f"  [查詢失敗] 無法抓取 {cname} 詳細資料。")
            if all_scraped_data:
                save_results(all_scraped_data, output_format='csv')
                save_results(all_scraped_data, output_format='json')
            else:
                print("[INFO] 無任何公司資料可匯出。")
        await browser.close()

if __name__ == "__main__":
    import asyncio
    asyncio.run(unified_main())