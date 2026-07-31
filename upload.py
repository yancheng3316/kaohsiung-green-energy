import os
import json
import time
import urllib.request
import urllib.error
from datetime import datetime, timedelta

# ==========================================
# 1. 環境變數設定（讀取 GitHub Secrets）
# ==========================================
SOLAREDGE_API_KEY = os.environ.get("SOLAREDGE_API_KEY")
KAOHSIUNG_API_TOKEN = os.environ.get("KAOHSIUNG_API_TOKEN")

# 您在高雄綠能平台的案場編號/設備編號（若程式碼中有硬編碼請依實際修改）
# SITE_ID = "您的案場編號" 

if not SOLAREDGE_API_KEY or not KAOHSIUNG_API_TOKEN:
    print("錯誤：未偵測到 API Key 或 Token，請檢查 GitHub Secrets 設定。")
    exit(1)

# ==========================================
# 2. 從 SolarEdge 讀取即時數據
# ==========================================
print("正在從 SolarEdge 讀取發電數據...")

# SolarEdge API URL (以概略即時數據為例)
solaredge_url = f"https://monitoringapi.solaredge.com/site/12345/overview?api_key={SOLAREDGE_API_KEY}" # 請確認您的 Site ID

try:
    req = urllib.request.Request(solaredge_url)
    with urllib.request.urlopen(req, timeout=20) as response:
        se_data = json.loads(response.read().decode('utf-8'))
        
    # 解析數據 (依 SolarEdge 回傳格式)
    overview = se_data.get("overview", {})
    current_power_kw = overview.get("currentPower", {}).get("power", 0) / 1000.0  # W 轉 kW
    daily_energy_kwh = overview.get("lastDayData", {}).get("energy", 0) / 1000.0  # Wh 轉 kWh
    
    # 取得台灣時間 (UTC+8)
    now_taiwan = datetime.utcnow() + timedelta(hours=8)
    time_str = now_taiwan.strftime("%Y-%m-%d %H:%M:%S")
    
    print(f"成功取得數據！台灣時間: {time_str}, 當前功率: {current_power_kw:.2f} kW, 當日發電: {daily_energy_kwh:.2f} kWh")

except Exception as e:
    print(f"擷取 SolarEdge 數據失敗: {e}")
    exit(1)

# ==========================================
# 3. 組裝高雄綠能平台要求之 JSON 封包
# ==========================================
payload = {
    "token": KAOHSIUNG_API_TOKEN,
    "time": time_str,
    "power": round(current_power_kw, 2),
    "generation": round(daily_energy_kwh, 2)
}

json_data = json.dumps(payload).encode('utf-8')

# 高雄綠能平台 API Endpoint
kems_url = "https://kems.kcg.gov.tw/api/v1/upload" # 請確認您的綠能平台 API 網址

post_req = urllib.request.Request(
    kems_url,
    data=json_data,
    headers={
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0"
    },
    method="POST"
)

# ==========================================
# 4. 傳送數據至高雄綠能平台（含 3 次自動重試）
# ==========================================
print("正在傳送數據至高雄綠能平台...")

MAX_RETRIES = 3      # 最多重試次數
RETRY_DELAY = 5      # 每次失敗後等待秒數
upload_success = False

for attempt in range(1, MAX_RETRIES + 1):
    try:
        with urllib.request.urlopen(post_req, timeout=30) as post_response:
            status_code = post_response.getcode()
            print(f"綠能平台回應狀態碼: {status_code}")
            print("=== 傳送完成！ ===")
            upload_success = True
            break  # 傳送成功，立刻結束重試迴圈
            
    except (urllib.error.URLError, TimeoutError, Exception) as e:
        print(f"⚠️ 第 {attempt} 次傳送失敗 (原因: {e})")
        if attempt < MAX_RETRIES:
            print(f"等待 {RETRY_DELAY} 秒後進行第 {attempt + 1} 次重試...")
            time.sleep(RETRY_DELAY)
        else:
            print("❌ 已達到最大重試次數 (3次)。本次高雄綠能平台傳送暫時跳過，等待下一期(15分鐘後)自動觸發。")

# 備註：即便 3 次都失敗也不強制 exit(1)，防止 GitHub 發送騷擾 Email
