"""
測試檔案上傳功能是否正常修復
"""
import requests
import os

# 設定
ORCHESTRATOR_URL = "http://192.168.41.173:5080"
USER_ID = "2"
AGENT_DIR = "D:\\mygpt\\AI_NEXUS_hermes\\hermes_core_data_test\\profiles\\user_2"

def test_upload_endpoint():
    """測試正確的檔案上傳端點"""
    print("=== 測試 1：檢查檔案是否存在 ===")
    
    required_files = ["config.yaml", "SOUL.md", "mcp.json", "phison_mcp_bridge.py"]
    missing_files = []
    
    for filename in required_files:
        file_path = os.path.join(AGENT_DIR, filename)
        if os.path.exists(file_path):
            print(f"✅ {filename} 存在 ({os.path.getsize(file_path)} bytes)")
        else:
            print(f"❌ {filename} 不存在")
            missing_files.append(filename)
    
    if missing_files:
        print(f"缺少檔案: {missing_files}")
        return False
    
    print("\n=== 測試 2：上傳檔案到 Orchestrator ===")
    
    # 測試正確的端點 (沒有 /files)
    upload_url = f"{ORCHESTRATOR_URL}/api/v1/users/{USER_ID}"
    print(f"上傳端點: {upload_url}")
    
    files_to_upload = []
    for filename in required_files:
        file_path = os.path.join(AGENT_DIR, filename)
        files_to_upload.append((filename, (filename, open(file_path, "rb"), "application/octet-stream")))
    
    try:
        print("開始上傳...")
        upload_resp = requests.post(
            upload_url,
            files=files_to_upload,
            timeout=120,
        )
        
        print(f"回應狀態碼: {upload_resp.status_code}")
        print(f"回應內容: {upload_resp.text[:500]}...")
        
        if upload_resp.status_code == 200:
            upload_data = upload_resp.json()
            print(f"✅ 上傳成功!")
            
            # 檢查檔案狀態
            files_result = upload_data.get("files", [])
            print(f"\n檔案上傳結果:")
            for file_result in files_result:
                path = file_result.get("path", "unknown")
                status = file_result.get("status", "unknown")
                print(f"  - {path}: {status}")
                
                if status not in ("written", "success"):
                    error = file_result.get("error", "no error details")
                    print(f"    ❌ 錯誤: {error}")
            
            failed_files = [f for f in files_result if f.get("status") not in ("written", "success")]
            if not failed_files:
                print("\n🎉 所有檔案上傳成功!")
                return True
            else:
                print(f"\n⚠️ 有 {len(failed_files)} 個檔案上傳失敗")
                return False
        else:
            print(f"❌ 上傳失敗，狀態碼: {upload_resp.status_code}")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"❌ 上傳發生錯誤: {str(e)}")
        return False
    finally:
        # 關閉所有開啟的檔案
        for _, file_tuple in files_to_upload:
            file_tuple[1].close()

def test_incorrect_endpoint():
    """測試錯誤的端點 (有 /files) - 應該會失敗"""
    print("\n=== 測試 3：測試錯誤的端點 ===")
    
    upload_url = f"{ORCHESTRATOR_URL}/api/v1/users/{USER_ID}/files"
    print(f"錯誤端點: {upload_url}")
    
    test_file = os.path.join(AGENT_DIR, "config.yaml")
    
    try:
        with open(test_file, "rb") as f:
            resp = requests.post(
                upload_url,
                files=[("config.yaml", ("config.yaml", f, "application/octet-stream"))],
                timeout=10,
            )
        
        print(f"錯誤端點回應狀態碼: {resp.status_code}")
        if resp.status_code == 404:
            print("✅ 預期的結果：404 Not Found (端點不存在)")
            return True
        else:
            print(f"⚠️ 未預期的回應: {resp.status_code}")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"✅ 預期的錯誤: {str(e)[:100]}...")
        return True

if __name__ == "__main__":
    print("🔍 執行檔案上傳修復驗證測試\n")
    
    result1 = test_upload_endpoint()
    result2 = test_incorrect_endpoint()
    
    print("\n" + "="*50)
    if result1:
        print("✅ 檔案上傳功能修復成功!")
    else:
        print("❌ 檔案上傳還有問題")
    
    if result2:
        print("✅ 端點格式確認正確")
    else:
        print("⚠️ 需要進一步檢查端點格式")