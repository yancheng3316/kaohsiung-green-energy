import urllib.request
import json
import time
from datetime import datetime, timezone, timedelta

# --- 1. 設定參數 ---
SOLAREDGE_SITE_ID = "4391290"
SOLAREDGE_API_KEY = "BZACTRW5TQFVOUDOL6X45SFJX7Y4UAQ5"

KEMS_API_KEY = "0BC4B29B-858A-4FA2-9287-90CE11672F42"
UBID = "76010302"
FCID = "1"
TYPE_D = "FS1"

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

# --- 2. 從 SolarEdge 抓取最新資料 ---
print("正在從 SolarEdge 讀取發電數據...")
se_url = f"https://monitoringapi.solaredge.com/site/{SOLAREDGE_SITE_ID}/overview?api_key={SOLAREDGE_API_KEY}"

try:
    req = urllib.request.Request(se_url, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as response:
        se_data = json.loads(response.read().decode('utf-8'))
    
    overview = se_data.get('overview', {})
    current_power_w = overview.get('currentPower', {}).get('power', 0.0) # 瓦 (W)
    last_day_data = overview.get('lastDayData', {}).get('energy', 0.0)    # 瓦時 (Wh)
    
    # 單位轉換：W 轉 kW，Wh 轉 kWh
    gen_max_kw = round(current_power_w / 1000.0, 2)
    gen_kwh = round(last_day_data / 1000.0, 2)
    
    # 取得台灣時間 (UTC+8)
    tz_taiwan = timezone(timedelta(hours=8))
    now_str = datetime.now(tz_taiwan).strftime("%Y-%m-%d %H:%M:%S")
    print(f"成功取得數據！台灣時間: {now_str}, 當前功率: {gen_max_kw} kW, 當日發電: {gen_kwh} kWh")

    # --- 3. 打包資料準備傳送到高雄綠能平台 ---
    payload = {
        "UBID": UBID,
        "FCID": FCID,
        "DT": now_str,
        "Status": "N",
        "DataType": {
            "Name": "TypeD",
            "Value": TYPE_D
        },
        "GenkWh": str(gen_kwh),
        "GenMaxkW": str(gen_max_kw)
    }

    kems_url = f"http://125.227.111.239/KEMSAPI/?Key={KEMS_API_KEY}"
    json_data = json.dumps(payload).encode('utf-8')

    print("正在傳送數據至高雄綠能平台...")
    post_headers = headers.copy()
    post_headers['Content-Type'] = 'application/json'

    post_req = urllib.request.Request(
        kems_url, 
        data=json_data, 
        headers=post_headers
    )
    
    # --- 4. 傳送資料（含 3 次自動重試機制） ---
    MAX_RETRIES = 3      # 最多重試次數
    RETRY_DELAY = 5      # 每次失敗後等待 5 秒

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            with urllib.request.urlopen(post_req, timeout=30) as post_response:
                res_code = post_response.getcode()
                res_body = post_response.read().decode('utf-8')
                print(f"綠能平台回應狀態碼: {res_code}")
                print(f"綠能平台回應內容: {res_body}")
                print("\n=== 傳送完成！ ===")
                break  # 傳送成功，跳出迴圈
                
        except Exception as e:
            print(f"⚠️ 第 {attempt} 次傳送失敗 (原因: {e})")
            if attempt < MAX_RETRIES:
                print(f"等待 {RETRY_DELAY} 秒後進行第 {attempt + 1} 次重試...")
                time.sleep(RETRY_DELAY)
            else:
                print("❌ 已達到最大重試次數 (3次)。本次高雄綠能平台傳送暫時跳過，等待下一期(15分鐘後)自動觸發。")

except Exception as e:
    print(f"\n執行過程中發生錯誤: {e}")
    raise e
