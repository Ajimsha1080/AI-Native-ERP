import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient
from apps.api.main import app
from packages.security.auth import create_access_token

client = TestClient(app)

# Generate valid access token for test client
auth_token = create_access_token(data={"sub": "admin@acme.com", "type": "access"})
auth_headers = {"Authorization": f"Bearer {auth_token}"}

print('1. Testing GET /health...')
r = client.get('/health')
print('Health:', r.status_code, r.json())
assert r.status_code == 200

print('1b. Testing unauthenticated rejection on protected endpoint /api/v1/billing/usage...')
r_unauth = client.get('/api/v1/billing/usage')
print('Unauthenticated rejection:', r_unauth.status_code)
assert r_unauth.status_code == 401, "Expected 401 Unauthorized for unauthenticated request"

print('2. Testing GET /api/v1/dashboard/home...')
r = client.get('/api/v1/dashboard/home')
print('Dashboard home:', r.status_code, list(r.json().keys()))
assert r.status_code == 200

print('3. Testing GET /api/v1/actions/approvals-queue...')
r = client.get('/api/v1/actions/approvals-queue')
print('Approvals queue:', r.status_code, 'Count:', len(r.json()))
assert r.status_code == 200

print('4. Testing POST /api/v1/dashboard/command with > $1000 action...')
r = client.post('/api/v1/dashboard/command', json={'query': 'Approve purchase order for $4500 for Dell laptops'})
res = r.json()
print('Command Agent:', res.get('agent_name'))
print('Command Summary:', res.get('summary'))
print('Command Findings:', res.get('findings'))
assert r.status_code == 200
assert res.get('agent_name') == 'Procurement Agent'
assert 'approvals' in res.get('recommendation', '').lower() or any('/approvals' in a.get('url', '') for a in res.get('actions', []))

print('5. Testing GET /api/v1/connectors...')
r = client.get('/api/v1/connectors', headers=auth_headers)
print('Connectors:', r.status_code, 'Count:', len(r.json()))
assert r.status_code == 200

print('6. Testing GET /api/v1/billing/usage with Bearer token...')
r = client.get('/api/v1/billing/usage', headers=auth_headers)
print('Billing usage:', r.status_code, r.json().get('metrics', {}).get('plan'))
assert r.status_code == 200

print('7. Testing GET /api/v1/knowledge/search?q=invoice...')
r = client.get('/api/v1/knowledge/search?q=invoice', headers=auth_headers)
print('Knowledge search:', r.status_code, 'Matches:', len(r.json().get('results', [])))
assert r.status_code == 200

print('8. Testing GET /api/v1/agents...')
r = client.get('/api/v1/agents', headers=auth_headers)
print('Agents:', r.status_code, 'Total items:', r.json().get('total'))
assert r.status_code == 200

print('9. Testing GET /api/v1/workflows...')
r = client.get('/api/v1/workflows', headers=auth_headers)
print('Workflows:', r.status_code, "Count:", len(r.json()))
assert r.status_code == 200

print('10. Testing GET /api/v1/dashboard/finance...')
r = client.get('/api/v1/dashboard/finance', headers=auth_headers)
print('Finance dashboard:', r.status_code, list(r.json().keys()))
assert r.status_code == 200

print('11. Testing GET /api/v1/dashboard/inventory...')
r = client.get('/api/v1/dashboard/inventory', headers=auth_headers)
print('Inventory dashboard:', r.status_code, list(r.json().keys()))
assert r.status_code == 200

print('12. Testing GET /api/v1/dashboard/procurement...')
r = client.get('/api/v1/dashboard/procurement', headers=auth_headers)
print('Procurement dashboard:', r.status_code, list(r.json().keys()))
assert r.status_code == 200

print('13. Testing GET /api/v1/dashboard/sales...')
r = client.get('/api/v1/dashboard/sales', headers=auth_headers)
print('Sales dashboard:', r.status_code, list(r.json().keys()))
assert r.status_code == 200

print('14. Testing GET /api/v1/dashboard/security...')
r = client.get('/api/v1/dashboard/security', headers=auth_headers)
print('Security dashboard:', r.status_code, list(r.json().keys()))
assert r.status_code == 200

print('\n==========================================')
print('>>> ALL 14 BACKEND INTEGRATION TESTS PASSED PERFECTLY! <<<')
print('==========================================')
