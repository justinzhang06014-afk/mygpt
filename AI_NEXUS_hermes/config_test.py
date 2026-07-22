import os
import orchestrator_client
import json

print('=== Orchestrator Configuration ===')
print(f'URL: {orchestrator_client.ORCHESTRATOR_URL}')
print(f'Enabled: {orchestrator_client.is_enabled()}')
print(f'HERMES_DATA_ROOT: {orchestrator_client.HERMES_DATA_ROOT}')
print(f'HERMES_IMAGE: {orchestrator_client.HERMES_IMAGE}')
print()

print('=== Test Payload Processing ===')
test_payload = {
    'llm_api_key': 'AINX-F78D2FCD53915EE37BD0871392FFBFFAF648C53C388950FC6A1F2ED8C534B249',
    'model': 'Qwen/Qwen3.6-35B-A3B-FP8',
    'phison_token': 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJqdXN0aW5femhhbmciLCJqdGkiOiIyNjlmZTY2MS05Mzk1LTQ1ZDYtOGMxMC01YzRiZTkxNzc1MjgiLCJpZCI6IjEyMDkwIiwiZXhwIjoxNzg0Nzk4OTgzLCJpc3MiOiJ5b3VyX2lzc3VlciIsImF1ZCI6InlvdXJfaXNzdWVyIn0.auPGqWzdJzSS0EXMNL9CV4ZlGzgdgxvGaaS5fDpH0uk',
    'system_prompt': 'You are a helpful office assistant',
    'user_id': '1'
}

print(f'user_id: {test_payload["user_id"]}')
print(f'Type: {type(test_payload["user_id"])}')
print(f'Converted to int: {orchestrator_client._convert_user_id(test_payload["user_id"])}')