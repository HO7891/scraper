import requests
from bs4 import BeautifulSoup
import json
import csv
import time
import argparse
import os
import yaml
from datetime import datetime
from urllib.parse import urljoin, urlparse

# 用於模擬瀏覽器行為的請求頭
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
}

def get_page_content(url, retries=3):
    """
    發送 HTTP 請求獲取網頁內容，帶有重試機制。
    """
    for attempt in range(retries):
        try:
            print(f"  Fetching: {url} (Attempt {attempt + 1}/{retries})")
            response = requests.get(url, headers=HEADERS, timeout=15)
            response.raise_for_status()  # 如果狀態碼不是200，則拋出HTTPError
            response.encoding = 'utf-8' # 確保正確解碼中文內容
            return response.text
        except requests.exceptions.RequestException as e:
            print(f"  Error fetching {url}: {e}")
            if attempt < retries - 1:
                time.sleep(2) # 重試前等待
            else:
                print(f"  Max retries reached for {url}")
    return None

def extract_field(soup_element, field_config):
    """
    根據 field_config 從 BeautifulSoup 元素中提取指定數據。
    """
    selector = field_config.get('selector')
    attribute = field_config.get('attribute')
    default_value = field_config.get('default', '')

    if not selector:
        return default_value

    target_element = soup_element.select_one(selector)

    if not target_element:
        return default_value

    if attribute == 'innerText':
        return target_element.get_text(separator='\n', strip=True)
    elif attribute == 'innerHTML':
        return str(target_element) # Returns the HTML content including tags
    elif attribute and attribute in target_element.attrs:
        return target_element[attribute].strip()
    else:
        return target_element.get_text(separator='\n', strip=True) # Default to text if attribute is not specified or not found

def scrape_articles(config):
    """
    根據配置爬取文章列表和詳細內容。
    """
    scraped_articles = []
    current_page_url = config['base_url'] + config['listing_page']['start_path']
    base_domain = urlparse(config['base_url']).netloc

    print(f"--- Starting scraping from {current_page_url} ---")

    while current_page_url:
        print(f"\nProcessing listing page: {current_page_url}")
        page_content = get_page_content(current_page_url)
        if not page_content:
            print(f"Failed to get content for {current_page_url}. Stopping pagination.")
            break

        soup = BeautifulSoup(page_content, 'html.parser')
        article_link_selector = config['listing_page']['article_link_selector']
        article_url_attribute = config['listing_page']['article_url_attribute']
        next_page_selector = config['listing_page'].get('next_page_selector')

        found_on_page = 0
        for link_element in soup.select(article_link_selector):
            title = link_element.get_text(strip=True)
            relative_url = link_element.get(article_url_attribute)

            if not relative_url:
                print(f"  Warning: No '{article_url_attribute}' found for an article link with title '{title}'. Skipping.")
                continue

            # 確保 URL 是絕對路徑
            full_article_url = urljoin(current_page_url, relative_url)

            # 檢查是否在同一個網域下，避免爬到外部連結
            if urlparse(full_article_url).netloc != base_domain:
                print(f"  Skipping external link: {full_article_url}")
                continue

            article_info = {'title': title, 'url': full_article_url}

            # 應用過濾器
            is_match = True
            for f in config.get('filters', []):
                field_to_filter = f.get('field')
                strategy = f.get('strategy')
                value = f.get('value')

                if field_to_filter not in article_info: # Only title is directly available here
                    is_match = False # If filter applies to non-title field, we decide to process it later
                    break
                
                if strategy == 'starts_with' and not article_info[field_to_filter].startswith(value):
                    is_match = False
                    break
                elif strategy == 'contains' and value not in article_info[field_to_filter]:
                    is_match = False
                    break
                # 可以添加更多過濾策略 (例如 regex)

            if is_match:
                scraped_articles.append(article_info)
                found_on_page += 1
                print(f"  Identified: {article_info['title']}")
            else:
                print(f"  Filtered out: {article_info['title']}")

        print(f"  Found {found_on_page} eligible articles on this page.")
        
        # 尋找下一頁連結
        next_page_link = None
        if next_page_selector:
            next_page_element = soup.select_one(next_page_selector)
            if next_page_element:
                next_page_href = next_page_element.get('href')
                if next_page_href:
                    next_page_link = urljoin(current_page_url, next_page_href)
        
        # 防止無限循環或意外連結
        if next_page_link and next_page_link != current_page_url and urlparse(next_page_link).netloc == base_domain:
            current_page_url = next_page_link
            time.sleep(config.get('page_load_delay', 1)) # 換頁間隔
        else:
            current_page_url = None # 沒有下一頁或連結無效，停止
            print("No next page found or invalid next page link. Stopping pagination.")


    print(f"\n--- Total {len(scraped_articles)} articles identified from listing pages. ---")

    # 爬取文章詳細內容
    for i, article in enumerate(scraped_articles):
        print(f"\nProcessing content for ({i+1}/{len(scraped_articles)}): {article['title']}")
        article_page_content = get_page_content(article['url'])
        if not article_page_content:
            print(f"  Failed to get article content for {article['url']}")
            for field in config['article_page']['fields']:
                article[field['name']] = "Error: Content not fetched"
            continue
        
        article_soup = BeautifulSoup(article_page_content, 'html.parser')
        
        for field_config in config['article_page']['fields']:
            field_name = field_config['name']
            article[field_name] = extract_field(article_soup, field_config)
            print(f"  - Extracted {field_name}. Length: {len(article[field_name]) if article[field_name] else 0}")
        
        time.sleep(config.get('article_load_delay', 0.5)) # 文章內容間隔

    return scraped_articles

def save_results(data, output_format, filename_prefix="scraped_data"):
    """
    將結果儲存到指定格式的檔案。
    """
    output_dir = "output"
    os.makedirs(output_dir, exist_ok=True) # 使用 exist_ok=True 避免重複創建報錯

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    file_path_base = os.path.join(output_dir, f"{filename_prefix}_{timestamp}")

    if output_format == "json":
        file_path = f"{file_path_base}.json"
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"\nResults saved to {file_path}")
    elif output_format == "csv":
        file_path = f"{file_path_base}.csv"
        if not data:
            print("No data to save to CSV.")
            return

        # 動態獲取所有欄位名稱
        all_fieldnames = set()
        for item in data:
            all_fieldnames.update(item.keys())
        fieldnames = sorted(list(all_fieldnames)) # 排序以保持一致性

        with open(file_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore') # extrasaction='ignore' 忽略未在fieldnames中定義的鍵
            writer.writeheader()
            writer.writerows(data)
        print(f"\nResults saved to {file_path}")
    elif output_format == "txt":
        file_path = f"{file_path_base}.txt"
        with open(file_path, 'w', encoding='utf-8') as f:
            for item in data:
                f.write(f"--- Title: {item.get('title', 'N/A')} ---\n")
                f.write(f"URL: {item.get('url', 'N/A')}\n")
                
                for key, value in item.items():
                    if key not in ['title', 'url']: # 排除已處理的欄位
                        f.write(f"{key.capitalize()}:\n{value}\n")
                f.write("\n")
            f.write(f"\n--- Total {len(data)} articles ---\n")
        print(f"\nResults saved to {file_path}")
    else:
        print(f"Unsupported output format: {output_format}")

def load_config(config_file):
    """
    從 YAML 檔案中載入配置。
    """
    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        print(f"Error: Configuration file '{config_file}' not found.")
        exit(1)
    except yaml.YAMLError as e:
        print(f"Error parsing configuration file '{config_file}': {e}")
        exit(1)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Universal web scraper with YAML configuration.")
    parser.add_argument(
        '-c', '--config',
        required=True,
        help="Path to the YAML configuration file."
    )
    parser.add_argument(
        '-f', '--format',
        choices=['json', 'csv', 'txt'],
        help="Override output format specified in config (json, csv, txt). Default comes from config."
    )
    args = parser.parse_args()

    config = load_config(args.config)
    
    # 允許命令行參數覆蓋配置文件中的輸出格式
    output_format = args.format if args.format else config.get('output_format', 'json')

    if not config:
        print("Configuration not loaded. Exiting.")
        exit(1)

    scraped_data = scrape_articles(config)

    if scraped_data:
        save_results(scraped_data, output_format, config.get('website_name', 'scraped_data').replace(" ", "_").lower())
    else:
        print("No data was scraped.")
