"""
快速驗證容器建立修復
"""
import requests
import time
import os

def test_container_creation():
    """測試容器建立是否正常"""
    
    print("=== 容器建立修復驗證測試 ===\n")
    
    # 模擬 API 請求
    api_url = "http://localhost:your-port/api/session/ensure"  # 替換成你的實際端口
    
    payload = {
        "user_id": "test_user",
        "llm_api_key": "AINX-F78D2FCD53915EE37BD0871392FFBFFAF648C53C388950FC6A1F2ED8C534B249",
        "model": "Qwen/Qwen3.6-35B-A3B-FP8",
        "phison_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
        "system_prompt": "測試助理"
    }
    
    print(f"發送請求到: {api_url}")
    print(f"用户ID: {payload['user_id']}")
    print(f"模型: {payload['model']}")
    
    start_time = time.time()
    
    try:
        response = requests.post(
            api_url, 
            json=payload,
            timeout=300  # 5分鐘超時
        )
        
        elapsed_time = time.time() - start_time
        
        print(f"\n📊 響應時間: {elapsed_time:.2f} 秒")
        print(f"📊 狀態碼: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"\n✅ 成功回應: {result.get('status')}")
            print(f"📊 容器ID: {result.get('worker_id', 'N/A')}")
            print(f"📊 基礎URL: {result.get('base_url', 'N/A')}")
            
            # 時間比較
            if elapsed_time < 30:
                print(f"🎉 優秀！容器在 {elapsed_time:.1f} 秒內建立成功")
            elif elapsed_time < 60:
                print(f"✅ 良好！容器在 {elapsed_time:.1f} 秒內建立成功")
            else:
                print(f"⚠️  警告：容器建立花費 {elapsed_time:.1f} 秒，請檢查網絡環境")
                
            return True
        else:
            print(f"\n❌ 錯誤回應: {response.status_code}")
            try:
                error_detail = response.json()
                print(f"錯誤詳情: {error_detail}")
            except:
                print(f"錯誤內容: {response.text[:200]}")
            return False
            
    except requests.exceptions.Timeout:
        elapsed_time = time.time() - start_time
        print(f"\n❌ 超時錯誤: 請求在 {elapsed_time:.1f} 秒後超時")
        print("可能原因:")
        print("1. 服務未啟動")
        print("2. 端口錯誤")
        print("3. 容器建立慢（網絡問題或配置錯誤）")
        return False
        
    except requests.exceptions.ConnectionError:
        print(f"\n❌ 連接錯誤: 無法連接到 {api_url}")
        print("請檢查:")
        print("1. 服務是否啟動")
        print("2. 端口是否正確")
        print("3. 防火牆設置")
        return False
        
    except Exception as e:
        elapsed_time = time.time() - start_time
        print(f"\n❌ 未預期的錯誤: {str(e)}")
        print(f"耗時: {elapsed_time:.1f} 秒")
        return False

def check_environment_variables():
    """檢查必要的環境變數是否設置"""
    print("\n=== 環境變數檢查 ===")
    
    required_vars = [
        "PHISON_API_KEY",
        "LLM_BASE_URL", 
        "LLM_MODEL"
    ]
    
    all_set = True
    for var in required_vars:
        value = os.getenv(var)
        status = "✅" if value else "❌"
        display_value = value[:20] + "..." if value and len(value) > 20 else value
        print(f"{status} {var}: {display_value if value else '未設置'}")
        if not value:
            all_set = False
    
    if all_set:
        print("\n✅ 所有必要環境變數都已設置")
    else:
        print("\n⚠️  請設置缺失的環境變數")
    
    return all_set

def check_file_upload():
    """檢查本地檔案是否準備就緒"""
    print("\n=== 檔案檢查 ===")
    
    test_user_dir = "D:\\mygpt\\AI_NEXUS_hermes\\hermes_core_data_test\\profiles\\user_2"
    required_files = ["config.yaml", "SOUL.md", "mcp.json", "phison_mcp_bridge.py"]
    
    all_exist = True
    for filename in required_files:
        file_path = os.path.join(test_user_dir, filename)
        if os.path.exists(file_path):
            size = os.path.getsize(file_path)
            print(f"✅ {filename}: {size} bytes")
        else:
            print(f"❌ {filename}: 檔案不存在")
            all_exist = False
    
    return all_exist

if __name__ == "__main__":
    print("🔍 开始診斷容器建立問題\n")
    
    # 檢查環境變數
    env_ok = check_environment_variables()
    
    # 檢查檔案
    files_ok = check_file_upload()
    
    # 如果前置檢查都通過，測試容器建立
    if env_ok and files_ok:
        print("\n" + "="*50)
        print("開始測試容器建立...")
        print("="*50 + "\n")
        
        test_container_creation()
    else:
        print("\n⚠️  請先解決環境變數或檔案問題，然後重新測試")