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
- **自動根據表格標題關鍵字判斷欄位位置，無須維護固定 selector，極度耐 HTML 結構異動**

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
- 查詢公司名稱：實際查詢時輸入的名稱
- 公司名稱：登記公司全名
- 統一編號：公司統編
- 登記現況：如「核准設立」等
- 資本總額(元)：登記資本額
- 代表人姓名：公司負責人
- 公司所在地：登記地址

## 輸入/輸出說明
- **輸入檔案**：
  - `company_list.txt`：每行一家公司名稱，UTF-8 編碼
- **輸出檔案**：
  - `output_biz/biz_company_info_YYYYMMDD_HHMMSS.json`
  - `output_biz/biz_company_info_YYYYMMDD_HHMMSS.csv`
  - `bizbat_log.txt`：詳細 log

## 查詢流程與程式邏輯
1. 讀取 `company_list.txt` 逐筆公司名稱。
2. 自動填入查詢、點擊搜尋，遍歷搜尋結果，優先點擊「登記現況：核准設立」公司。
3. 進入公司頁面後，自動遍歷表格每一列，根據標題關鍵字（如「公司名稱」、「統一編號」、「登記現況」等）自動擷取對應欄位內容。
4. 若找不到對應欄位，該欄自動回填「查無資料」。
5. 全部查詢結果自動儲存為 JSON/CSV，log 詳細記錄進度與錯誤。

### 錯誤處理
- 無搜尋結果、網路異常、HTML 結構異動等皆不會中斷主程式，並於 log 顯示警告。
- 欄位缺漏時自動回傳「查無資料」。
- 發生重大例外時會自動截圖並存於 `output_biz/`。

---
**如需自訂欄位或進階功能，請直接修改 `bizbat.py` 內 SELECTORS 或主程式邏輯。**