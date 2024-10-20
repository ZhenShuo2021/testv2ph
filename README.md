# V2PH Downloader
微圖坊下載器

## 使用方式
需要安裝 Chrome

第一次使用時開啟終端，輸入以下指令啟動 Chrome 並登入微圖坊帳號
```sh
# MacOS
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome --remote-debugging-port=9222 --user-data-dir="./chrome_profile" --disable-infobars --disable-extensions --start-maximized

# Windows
start chrome -ArgumentList "--remote-debugging-port=9222", "--user-data-dir=%cd%\chrome_profile", "--disable-infobars", "--disable-extensions", "--start-maximized"
```

安裝 Python 依賴套件
```sh
git clone -q https://github.com/ZhenShuo2021/V2PH-Downloader  # 或是直接下載 repo
cd V2PH-Downloader                           # 進入資料夾
python -m venv .venv                         # 創建虛擬環境，下一步是進入虛擬環境
source .venv/bin/activate                    # Windows指令: .venv\Scripts\activate
pip install -r requirements.txt              # 安裝依賴套件
```

前置作業完成後就可以直接執行腳本
```sh
python -m src.main <url> <--dry-run>
```

參數
- url: 目標下載的頁面網址。
- --dry-run: 可選參數，僅進行模擬下載，不會實際下載檔案。
- --terminate: 下載結束後是否關閉 Chrome 視窗。

## 設定
在 src/const.py 中可以調整設定，例如捲動長度、捲動步長與速率限制等：

```py
MIN_SCROLL_LENGTH = 1500
MAX_SCROLL_LENGTH = 4000
MIN_SCROLL_STEP = 50
MAX_SCROLL_STEP = 250
RATE_LIMIT = 400
DOWNLOAD_DIR = "download"
PROFILE_PATH = "chrome_profile"
ALBUM_LOG_FILE = "downloaded_albums.txt"
LOG_PATH = "./v2ph"
```

- DOWNLOAD_DIR: 預設下載在專案資料夾中的 download 內
- RATE_LIMIT: 下載速度限制，400就很夠用
- ALBUM_LOG_FILE: 紀錄 album 網址，重複的會跳過
- LOG_PATH: 運行日誌

## 補充
1. 這不是破解腳本，只是下載工具，該有的限制還是有。
2. 換頁或者下載速度設定太快可能會吃到 Cloudflare 封鎖，請小心。
3. 請謹慎使用，不要又把好網站搞到關掉了，難得有資源收錄完整的。

## Todo
[突破 Cloudflare turnstile](https://github.com/g1879/DrissionPage/issues/297)，自動登入腳本都寫好了就差被擋住。
