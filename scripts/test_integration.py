import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient
from apps.api.main import app

client = TestClient(app)

print('1. Testing GET /health...')
r = client.get('/health')
print('Health:', r.status_code, r.json())
assert r.status_code == 200

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
r = client.get('/api/v1/connectors')
print('Connectors:', r.status_code, 'Count:', len(r.json()))
assert r.status_code == 200

print('6. Testing GET /api/v1/billing/usage...')
r = client.get('/api/v1/billing/usage')
print('Billing usage:', r.status_code, r.json().get('metrics', {}).get('plan'))
assert r.status_code == 200

print('7. Testing GET /api/v1/knowledge/search?q=invoice...')
r = client.get('/api/v1/knowledge/search?q=invoice')
print('Knowledge search:', r.status_code, 'Matches:', len(r.json().get('results', [])))
assert r.status_code == 200

print('8. Testing GET /api/v1/agents...')
r = client.get('/api/v1/agents')
print('Agents:', r.status_code, 'Total items:', r.json().get('total'))
assert r.status_code == 200

print('9. Testing GET /api/v1/workflows...')
r = client.get('/api/v1/workflows')
print('Workflows:', r.status_code, "Count:", len(r.json()))
assert r.status_code == 200

print('10. Testing GET /api/v1/dashboard/finance...')
r = client.get('/api/v1/dashboard/finance')
print('Finance dashboard:', r.status_code, list(r.json().keys()))
assert r.status_code == 200

print('11. Testing GET /api/v1/dashboard/inventory...')
r = client.get('/api/v1/dashboard/inventory')
print('Inventory dashboard:', r.status_code, list(r.json().keys()))
assert r.status_code == 200

print('12. Testing GET /api/v1/dashboard/procurement...')
r = client.get('/api/v1/dashboard/procurement')
print('Procurement dashboard:', r.status_code, list(r.json().keys()))
assert r.status_code == 200

print('13. Testing GET /api/v1/dashboard/sales...')
r = client.get('/api/v1/dashboard/sales')
print('Sales dashboard:', r.status_code, list(r.json().keys()))
assert r.status_code == 200

print('14. Testing GET /api/v1/dashboard/security...')
r = client.get('/api/v1/dashboard/security')
print('Security dashboard:', r.status_code, list(r.json().keys()))
assert r.status_code == 200

print('\n==========================================')
print('>>> ALL 14 BACKEND INTEGRATION TESTS PASSED PERFECTLY! <<<')
print('==========================================')
