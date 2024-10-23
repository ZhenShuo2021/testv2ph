# V2PH Downloader
微圖坊下載器

## 使用方式
### 前置需求
1. 安裝 Chrome 瀏覽器
2. Python 版本 > 3.10

<!-- 第一次使用時開啟終端，輸入以下指令啟動 Chrome 並登入微圖坊帳號
```sh
# MacOS
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome --remote-debugging-port=9222 --user-data-dir="./chrome_profile" --disable-infobars --disable-extensions --start-maximized

# Windows
start chrome -ArgumentList "--remote-debugging-port=9222", "--user-data-dir=%cd%\chrome_profile", "--disable-infobars", "--disable-extensions", "--start-maximized"
``` -->

3. 安裝 Python 依賴套件
```sh
git clone -q https://github.com/ZhenShuo2021/V2PH-Downloader  # 或是直接下載 repo
cd V2PH-Downloader                           # 進入資料夾
python -m venv .venv                         # 創建虛擬環境，下一步是進入虛擬環境
source .venv/bin/activate                    # Windows指令: .venv\Scripts\activate
pip install -r requirements.txt              # 安裝依賴套件
```

完成前置作業後即可執行腳本，首次執行時需要手動登入網站。在 `.env` 檔案中填入帳號密碼腳本會自動登入，但可能會遇到機器人驗證的問題。
```sh
python run.py <url>
```

### 參數
- url: 下載目標的網址。
- --bot: 選擇自動化工具。完全體感不負責任分析 drission 比較不會遇到 Cloudflare 封鎖。
- --dry-run: 僅進行模擬下載，不會實際下載檔案。
- --terminate: 程式結束後是否關閉 Chrome 視窗。
- -q: 安靜模式。
- -v: 偵錯模式。
- --verbose: 設定日誌顯示等級，數值為 1~5 之間。

## 設定
在 `config.yaml` 中可以調整設定，例如捲動長度、捲動步長與速率限制等：

- download_dir: 預設下載在專案資料夾中的 download 內。
- rate_limit: 下載速度限制，預設 400 夠用也不會被封鎖。
- album_log: 紀錄下載過的 album 頁面網址，重複的會跳過。
- log_dir: 設定程式執行日誌的位置。

## 補充
1. 這不是破解腳本，只是下載工具，該有的限制還是有。
2. 換頁或者下載速度設定太快可能會觸發 Cloudflare 封鎖，請小心。
3. 請謹慎使用，不要又把好網站搞到關掉了，難得有資源收錄完整的。
4. 從頁面中間開始下載不會被視作重複下載，以方便補齊缺失檔案。
