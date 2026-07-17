import httpx
import sys

print("==================================================")
print("🚀 [START] 開始執行 Docker 內網穿透 SerpAPI 實驗...")
print("==================================================")

# 採用您一模一樣的真實 API Key 與拼接參數
api_key = "dbaa323b6d7e7f313ba5732b5d4c53d7deafcd23dfa2ad73eb63b7fbf0f52307"
url = f"https://serpapi.com/search.json?engine=google&q=taiwan&api_key={api_key}"

print(f"[DEBUG] 1. 準備發送網址: {url[:60]}...")

try:
    # 💡 故意放大超時到 10 秒，關閉 SSL 驗證，開啟跟隨重導向
    with httpx.Client(timeout=10.0, verify=False, follow_redirects=True) as client:
        print("[DEBUG] 2. 正在衝鋒外網傳輸線...")
        response = client.get(url)
    
    print(f"\n[📡 實驗結果] HTTP 狀態碼: {response.status_code}")
    print(f"[📄 實驗結果] 內容前 200 字:\n{response.text[:200]}\n")
    
    if "organic_results" in response.text:
        print("✅ [SUCCESS] 破案！Docker 網路完好無缺，SerpAPI 可以正常通車！")
    else:
        print("❌ [WARN] 雖然連上了，但回傳內容不對，可能是 Key 額度用完了。")

except httpx.ConnectTimeout:
    print("❌ [ERROR] 連線逾時！代表 Linux 容器內部的封包被 Windows 防火牆無聲丟棄了。")
except httpx.ConnectError as ce:
    print(f"❌ [ERROR] 連線失敗！Linux 系統底層回報原因: {str(ce)}")
except Exception as e:
    print(f"❌ [ERROR] 未知異常: {str(e)}")

print("==================================================")
