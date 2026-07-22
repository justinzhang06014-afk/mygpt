import zlib
import json

# 模擬 payload 中的 user_id
user_id = "1"
hash_value = zlib.crc32(user_id.encode('utf-8'))
user_id_int = abs(hash_value) | 1

print(f'Test 1: User ID 轉換')
print(f'  輸入: "{user_id}"')
print(f'  結果: {user_id_int}')
print()

# 模擬 _extract_base_url 的處理
test_data_1 = {
    "id": 123,
    "name": "test-worker",
    "baseUrl": "http://agent-worker-123:8080",
    "externalBaseUrl": "http://192.168.41.173:5080/workers/123",
    "status": "created"
}

test_data_2 = {
    "id": 124,
    "name": "test-worker-2", 
    "baseUrl": ["http://agent-worker-124:8080"],  # 陣列格式
    "externalBaseUrl": None,
    "status": "created"
}

def _extract_base_url(data):
    print(f'Test 2: _extract_base_url 處理')
    print(f'  輸入資料: {json.dumps(data, ensure_ascii=False)}')
    
    if not isinstance(data, dict):
        print(f'  ❌ 資料不是字典格式')
        return None, None
    
    external_base_url = data.get("externalBaseUrl")
    base_url = data.get("baseUrl")
    print(f'  提取結果 - base_url: {base_url} (類型: {type(base_url)}), external_base_url: {external_base_url} (類型: {type(external_base_url)})')
    
    if isinstance(base_url, (list, tuple)) and len(base_url) > 0:
        print(f'  [Warning] base_url is array, take first element: {base_url[0]}')
        base_url = base_url[0]
    
    if isinstance(external_base_url, (list, tuple)) and len(external_base_url) > 0:
        print(f'  [Warning] external_base_url is array, take first element: {external_base_url[0]}')
        external_base_url = external_base_url[0]
    
    print(f'  返回結果: ({base_url}, {external_base_url})')
    return base_url, external_base_url

# 測試正常情況
print('=' * 50)
result_1 = _extract_base_url(test_data_1)
print()

# 測試陣列情況
print('=' * 50)
result_2 = _extract_base_url(test_data_2)
print()

# 測試解包
print('=' * 50)
print('Test 3: 解包測試')
try:
    base_url, external_base_url = result_1
    print(f'✅ 正常解包成功: base_url={base_url}, external_base_url={external_base_url}')
except Exception as e:
    print(f'❌ 解包失敗: {e}')

try:
    base_url, external_base_url = result_2
    print(f'✅ 陣列處理解包成功: base_url={base_url}, external_base_url={external_base_url}')
except Exception as e:
    print(f'❌ 陣列解包失敗: {e}')