import pytest
import os
import threading
from src.main import Scraper, download_worker, download_queue
from src import const
from src import utils  # 導入 utils 模塊
import logging
import time

@pytest.fixture
def setup_test_environment(tmp_path, monkeypatch):
    # 設置測試環境
    test_download_dir = tmp_path / "test_download"
    test_download_dir.mkdir()
    

    # 修改 utils.py 中可能硬編碼的下載路徑
    original_join = os.path.join
    def patched_join(*args):
        if args and args[0] == 'download':
            return original_join(str(test_download_dir), *args[1:])
        return original_join(*args)
    monkeypatch.setattr('os.path.join', patched_join)
    
    # 設置 logger
    logger = logging.getLogger("test_logger")
    logger.setLevel(logging.INFO)
    
    # 創建一個實際的 Scraper 實例
    test_url = "https://www.v2ph.com/album/Weekly-Big-Comic-Spirits-2016-No22-23"
    # test_url = "https://www.v2ph.com/album/amem784a.html"
    
    scraper = Scraper(test_url, dry_run=False, logger=logger)
    
    # 確保 Scraper 使用正確的下載目錄
    scraper.destination = str(test_download_dir)
    
    return scraper, test_download_dir

def test_download_images(setup_test_environment, caplog):
    scraper, test_download_dir = setup_test_environment

    # 啟動下載工作線程
    download_thread = threading.Thread(target=download_worker, args=(scraper.logger,), daemon=True)
    download_thread.start()
    
    # 使用 scrape_start 方法來觸發實際的下載過程
    scraper.scrape_start()
    
    # 等待下載完成
    timeout = 120  # 等待120秒
    start_time = time.time()
    while download_queue.unfinished_tasks > 0:
        if time.time() - start_time > timeout:
            pytest.fail("下載超時")
        time.sleep(1)
    
    # 發送退出信號給工作線程
    download_queue.put((None, None))
    download_thread.join(timeout=5)
    
    # 檢查是否有圖片被下載到測試目錄
    downloaded_files = os.listdir(test_download_dir / os.listdir(test_download_dir)[0])
    assert len(downloaded_files) > 0, "沒有圖片被下載到測試目錄"
    
    # 檢查下載的文件是否為圖片（簡單檢查副檔名）
    image_extensions = ('.jpg', '.jpeg', '.png', '.gif')
    assert any(file.endswith(image_extensions) for file in downloaded_files), "下載的文件不是圖片"

    # 檢查日誌，確保沒有使用原始的 'download' 路徑
    assert 'File already exists: \'download/' not in caplog.text, "下載器仍在使用原始的 'download' 路徑"

    # 輸出下載的文件列表，用於調試
    print("下載的文件列表:")
    for file in downloaded_files:
        print(file)

    print("日誌內容:")
    print(caplog.text)

# 運行測試
if __name__ == "__main__":
    pytest.main(["-v", __file__])