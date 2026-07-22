import zlib
import json

# Test user_id conversion
user_id = "1"
hash_value = zlib.crc32(user_id.encode('utf-8'))
user_id_int = abs(hash_value) | 1
print(f'User ID conversion: "{user_id}" -> {user_id_int}')

# Test _extract_base_url function
def _extract_base_url(data):
    print(f'_extract_base_url input: {json.dumps(data, ensure_ascii=False)}')
    
    if not isinstance(data, dict):
        print('Data is not dict format')
        return None, None
    
    external_base_url = data.get("externalBaseUrl")
    base_url = data.get("baseUrl")
    print(f'Extracted - base_url: {base_url} (type: {type(base_url)}), external_base_url: {external_base_url} (type: {type(external_base_url)})')
    
    if isinstance(base_url, (list, tuple)) and len(base_url) > 0:
        print(f'base_url is array, taking first element: {base_url[0]}')
        base_url = base_url[0]
    
    if isinstance(external_base_url, (list, tuple)) and len(external_base_url) > 0:
        print(f'external_base_url is array, taking first element: {external_base_url[0]}')
        external_base_url = external_base_url[0]
    
    print(f'Returning: ({base_url}, {external_base_url})')
    return base_url, external_base_url

# Test normal case
test_data_1 = {
    "id": 123,
    "name": "test-worker",
    "baseUrl": "http://agent-worker-123:8080",
    "externalBaseUrl": "http://192.168.41.173:5080/workers/123",
    "status": "created"
}

# Test array format case
test_data_2 = {
    "id": 124,
    "name": "test-worker-2", 
    "baseUrl": ["http://agent-worker-124:8080"],
    "externalBaseUrl": None,
    "status": "created"
}

print('\n=== Test normal case ===')
result_1 = _extract_base_url(test_data_1)

print('\n=== Test array case ===')
result_2 = _extract_base_url(test_data_2)

print('\n=== Test unpacking ===')
try:
    base_url, external_base_url = result_1
    print(f'Normal unpack SUCCESS: base_url={base_url}, external_base_url={external_base_url}')
except Exception as e:
    print(f'Normal unpack FAIL: {e}')

try:
    base_url, external_base_url = result_2
    print(f'Array unpack SUCCESS: base_url={base_url}, external_base_url={external_base_url}')
except Exception as e:
    print(f'Array unpack FAIL: {e}')