import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
from typing import List, Dict

# ----------- 1. 設定 selector 模板 -----------
# 請根據實際需求填寫 selector
# 範例：
# SELECTORS = {
#     '標題': 'h1.article-title',
#     '內容': 'div.content',
#     '作者': 'span.author',
#     '日期': 'time.date',
# }
SELECTORS = {
    # '欄位名稱': 'CSS Selector 或 XPath'
}
# 支援 CSS Selector，若需 XPath 可自行擴充 parse_with_selectors 函數。

# ----------- 2. 批次讀取網址 -----------
def load_urls_from_txt(file_path: str) -> List[str]:
    """從 txt 檔案讀取網址清單，每行一個網址。"""
    with open(file_path, 'r', encoding='utf-8') as f:
        urls = [line.strip() for line in f if line.strip()]
    return urls

def load_urls_from_csv(file_path: str, url_column: str) -> List[str]:
    """從 CSV 檔案讀取網址清單，指定欄位。"""
    df = pd.read_csv(file_path)
    return df[url_column].dropna().tolist()

# ----------- 3. 網頁爬取主流程 -----------
def fetch_page(url: str, timeout: int = 10) -> str:
    resp = requests.get(url, timeout=timeout)
    resp.raise_for_status()
    return resp.text

def parse_with_selectors(html: str, selectors: Dict[str, str]) -> Dict[str, str]:
    soup = BeautifulSoup(html, 'html.parser')
    result = {}
    for field, selector in selectors.items():
        elem = soup.select_one(selector)
        result[field] = elem.get_text(strip=True) if elem else ''
    return result

# ----------- 3.5. Log 機制 -----------
def print_log(msg: str):
    print(f"[LOG] {time.strftime('%Y-%m-%d %H:%M:%S')} - {msg}")

# ----------- 4. 批次處理 -----------
def batch_scrape(urls: List[str], selectors: Dict[str, str], delay: float = 1.0) -> pd.DataFrame:
    data = []
    for idx, url in enumerate(urls, 1):
        print_log(f"({idx}/{len(urls)}) 開始處理: {url}")
        try:
            html = fetch_page(url)
            row = parse_with_selectors(html, selectors)
            row['url'] = url
            data.append(row)
            print_log(f"完成: {url}")
        except Exception as e:
            print_log(f"[ERROR] {url}: {e}")
            data.append({'url': url, **{k: '' for k in selectors}})
        time.sleep(delay)
    return pd.DataFrame(data)

# ----------- 5. 儲存結果 -----------
def save_to_csv(df: pd.DataFrame, file_path: str):
    df.to_csv(file_path, index=False, encoding='utf-8-sig')

# ----------- 6. 主程式範例 -----------
if __name__ == "__main__":
    # 1. 讀取網址清單模板說明：
    # 請將欲爬取的網址一行一個寫在 template/urls.txt
    # 範例：
    # https://example.com/page1
    # https://example.com/page2
    urls = load_urls_from_txt('urls.txt')
    # urls = load_urls_from_csv('urls.csv', 'url')  # 若有 csv 請取消註解

    print_log(f"共載入 {len(urls)} 筆網址，開始批次爬取...")

    # 2. 執行批次爬取
    df = batch_scrape(urls, SELECTORS, delay=1)

    # 3. 儲存結果
    save_to_csv(df, 'result.csv')
    print_log("批次爬取完成，已儲存 result.csv")
