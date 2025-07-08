# bizbat.py 使用說明

## 程式用途
本程式可自動查詢台灣經濟部商工登記公示資料網，批次擷取公司基本資料，並輸出成 CSV/JSON 檔案，支援自動 log、運行時間統計、異常自動截圖與詳細錯誤記錄。

## 主要功能
- 依 `company_list.txt` 內公司名稱逐筆查詢公司資訊
- 自動儲存查詢結果為 JSON 與 CSV
- 於 CMD 與 log 檔顯示即時進度與錯誤訊息
- 支援 headless/headful 模式切換（預設 headless）
- 執行過程自動記錄啟動、結束時間與總運行秒數
- 發生例外時自動截圖並詳細記錄於 log

## 執行環境需求
- Python 3.7 以上
- Playwright 及其瀏覽器
  ```sh
  pip install playwright
  playwright install
  ```

## 使用方式
1. 準備查詢公司名稱清單，存於 `company_list.txt`，每行一家公司名稱，UTF-8 編碼。
2. 執行程式（預設 headless 模式，log 會同時寫入檔案）：
   ```sh
   python bizbat.py
   ```
   若需顯示瀏覽器視窗，請將 `headless=True` 改為 `headless=False`。
3. 查詢結果將自動儲存於 `output_biz/` 資料夾，檔名含執行時間戳。
4. 執行過程會自動產生 `bizbat_log.txt`，記錄所有進度與錯誤。

## 參數/設定說明
- `LOG_TO_FILE`：控制是否寫入 log 檔（預設 True）
- `LOG_FILENAME`：log 檔名
- `OUTPUT_DIR`：輸出結果資料夾
- `company_list.txt`：公司名稱清單，每行一家公司

## 欄位說明
- 查詢公司名稱
- 公司名稱
- 統一編號
- 公司狀況
- 資本總額(元)
- 代表人姓名
- 公司所在地

## 輸入/輸出說明
- **輸入檔案**：
  - `company_list.txt`：每行一家公司名稱，UTF-8 編碼
- **輸出檔案**：
  - `output_biz/biz_company_info_YYYYMMDD_HHMMSS.json`
  - `output_biz/biz_company_info_YYYYMMDD_HHMMSS.csv`
  - `bizbat_log.txt`：詳細 log

## 常見問題
- 若出現 `[ERROR] Input file not found: company_list.txt`，請確認檔案存在且內容正確
- 查詢過程遇到網路問題會跳過該公司，並於 log 顯示警告
- 發生重大例外時會自動截圖並存於 `output_biz/`

---
**如需自訂欄位或進階功能，請直接修改 `bizbat.py` 內 SELECTORS 或主程式邏輯。**