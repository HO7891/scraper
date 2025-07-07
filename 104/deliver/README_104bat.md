# 104bat.py 使用說明

## 主要功能
- 單筆或批次查詢 104 公司詳細資訊，支援自動判斷來源檔(txt/csv)或 CLI 指定
- 統一輸出 csv/json 結果
- 支援 headless、debug 截圖等參數

## 使用方式

### 1. 單筆查詢
```
python 104bat.py 台積電
```

### 2. 批次查詢（指定來源檔案）
```
python 104bat.py -i company_list.txt
python 104bat.py --input-file company_list.csv
```

### 3. 批次查詢（自動尋找清單）
```
python 104bat.py
```
（會自動尋找當前或 ./104/ 目錄下的 company_list.txt/csv）

## 主要欄位
- 公司名稱、公司網址、產業類別、公司地址、主要服務、資本額、員工人數、公司官網、公司簡介

## 參數說明
- `台積電`：直接查詢該公司
- `-i` 或 `--input-file`：指定公司名稱清單檔案
- `--headless`：無頭模式
- `--debug-screenshot`：啟用 debug 截圖

## 其他
- 欄位自動判斷、反爬蟲處理、log/錯誤提示皆已內建
- 輸出檔案自動加時間戳
