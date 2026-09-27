"""
Integration tests for QuickBooks Online, Generic REST, and Shopify Connectors.

Verifies:
1. Real OAuth 2.0 token refresh handling upon 401 Unauthorized.
2. Real rate-limit (429) & server error (5xx) exponential backoff retries.
3. Full end-to-end CRUD, schema discovery, health check, and batch sync flows.
"""

import json
from datetime import datetime, timezone
import pytest
import httpx

from packages.connectors import (
    QuickBooksConnector,
    QuickBooksAPIError,
    QuickBooksAuthError,
    GenericRestConnector,
    GenericRestAPIError,
    ShopifyConnector,
    ShopifyAPIError,
)


# ============================================================================
# 1. QuickBooks Online Connector Integration Tests
# ============================================================================

@pytest.mark.asyncio
async def test_quickbooks_oauth_token_refresh_on_401():
    """Verify QuickBooks connector automatically refreshes expired OAuth token and retries."""
    refresh_called = False
    query_attempts = 0

    def mock_handler(request: httpx.Request) -> httpx.Response:
        nonlocal refresh_called, query_attempts
        
        # 1. Token Refresh Request
        if request.url.path == "/oauth2/v1/tokens/bearer":
            refresh_called = True
            assert request.headers.get("authorization", "").startswith("Basic ")
            return httpx.Response(
                200,
                json={
                    "access_token": "new_refreshed_access_token_xyz",
                    "refresh_token": "new_refresh_token_abc",
                    "expires_in": 3600
                }
            )

        # 2. Company Info or Query Endpoint
        if "/v3/company/test_realm_123/query" in request.url.path:
            query_attempts += 1
            auth_header = request.headers.get("authorization", "")
            
            # First attempt with stale token -> Return 401
            if auth_header == "Bearer stale_token_123":
                return httpx.Response(401, text="Unauthorized: Token Expired")
            
            # Second attempt with refreshed token -> Return 200
            elif auth_header == "Bearer new_refreshed_access_token_xyz":
                return httpx.Response(
                    200,
                    json={
                        "QueryResponse": {
                            "Invoice": [
                                {"Id": "INV-101", "DocNumber": "1001", "TotalAmt": 1500.0}
                            ]
                        }
                    }
                )

        return httpx.Response(404, text="Not Found")

    transport = httpx.MockTransport(mock_handler)
    async with httpx.AsyncClient(transport=transport) as client:
        connector = QuickBooksConnector(
            tenant_id="tenant-01",
            organization_id="org-01",
            credentials={
                "realm_id": "test_realm_123",
                "client_id": "mock_client_id",
                "client_secret": "mock_client_secret",
                "access_token": "stale_token_123",
                "refresh_token": "valid_refresh_token",
                "environment": "sandbox"
            },
            client=client,
            backoff_factor=0.01
        )

        invoices = await connector.read("invoices")
        assert len(invoices) == 1
        assert invoices[0]["Id"] == "INV-101"
        assert refresh_called is True
        assert query_attempts == 2
        assert connector.access_token == "new_refreshed_access_token_xyz"


@pytest.mark.asyncio
async def test_quickbooks_exponential_backoff_retry_on_429():
    """Verify QuickBooks connector retries on 429 Too Many Requests."""
    attempts = 0

    def mock_handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            return httpx.Response(429, headers={"Retry-After": "0.01"}, text="Too Many Requests")
        return httpx.Response(
            200,
            json={
                "CompanyInfo": {
                    "CompanyName": "Sandbox Enterprise Solutions"
                }
            }
        )

    transport = httpx.MockTransport(mock_handler)
    async with httpx.AsyncClient(transport=transport) as client:
        connector = QuickBooksConnector(
            tenant_id="tenant-01",
            organization_id="org-01",
            credentials={
                "realm_id": "test_realm_123",
                "access_token": "valid_token",
                "environment": "sandbox"
            },
            client=client,
            max_retries=3,
            backoff_factor=0.01
        )

        conn_status = await connector.test_connection()
        assert conn_status["status"] == "Healthy"
        assert conn_status["company_name"] == "Sandbox Enterprise Solutions"
        assert attempts == 3


@pytest.mark.asyncio
async def test_quickbooks_end_to_end_sandbox_crud_and_sync():
    """Verify full end-to-end CRUD, schema discovery, and sync flow for QuickBooks."""
    invoices_db = {
        "101": {"Id": "101", "DocNumber": "INV-101", "TotalAmt": 2500.0, "CustomerRef": {"value": "CUST-1"}}
    }

    def mock_handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path

        if "/companyinfo/" in path:
            return httpx.Response(200, json={"CompanyInfo": {"CompanyName": "Acme Sandbox"}})

        if "/query" in path:
            return httpx.Response(200, json={"QueryResponse": {"Invoice": list(invoices_db.values()), "Customer": [{"Id": "CUST-1", "DisplayName": "Acme Corp"}]}})

        if path.endswith("/invoice") and request.method == "POST":
            data = json.loads(request.content)
            inv_id = str(data.get("Id", "102"))
            invoices_db[inv_id] = {"Id": inv_id, **data}
            return httpx.Response(201, json={"Invoice": invoices_db[inv_id]})

        if "operation=delete" in str(request.url):
            data = json.loads(request.content)
            inv_id = str(data.get("Id"))
            invoices_db.pop(inv_id, None)
            return httpx.Response(200, json={"Invoice": {"Id": inv_id, "status": "Deleted"}})

        return httpx.Response(404, text="Not Found")

    transport = httpx.MockTransport(mock_handler)
    async with httpx.AsyncClient(transport=transport) as client:
        connector = QuickBooksConnector(
            tenant_id="tenant-01",
            organization_id="org-01",
            credentials={
                "realm_id": "test_realm_123",
                "access_token": "valid_token_123",
                "environment": "sandbox"
            },
            client=client
        )

        # 1. Health check & test connection
        health = await connector.health_check()
        assert health is True

        # 2. Capabilities & Schema
        caps = await connector.discover_capabilities()
        assert "invoices" in caps
        schema = await connector.get_schema("invoices")
        assert "TotalAmt" in schema["fields"]

        # 3. Read
        items = await connector.read("invoices")
        assert len(items) >= 1

        # 4. Create
        created = await connector.create("invoices", {"DocNumber": "INV-102", "TotalAmt": 4200.0})
        assert created["DocNumber"] == "INV-102"

        # 5. Update
        updated = await connector.update("invoices", "102", {"TotalAmt": 4500.0})
        assert updated["TotalAmt"] == 4500.0

        # 6. Delete
        deleted = await connector.delete("invoices", "102")
        assert deleted is True

        # 7. Batch Sync
        sync_result = await connector.sync()
        assert sync_result["status"] == "success"
        assert sync_result["invoices_synced"] >= 1

        # 8. Disconnect
        assert await connector.disconnect() is True


# ============================================================================
# 2. Generic REST Connector Integration Tests
# ============================================================================

@pytest.mark.asyncio
async def test_generic_rest_oauth_refresh_and_retries():
    """Verify Generic REST connector refreshes OAuth 2.0 tokens and handles 503 retries."""
    refresh_invoked = False
    requests_count = 0

    def mock_handler(request: httpx.Request) -> httpx.Response:
        nonlocal refresh_invoked, requests_count
        requests_count += 1

        if request.url.path == "/oauth/token":
            refresh_invoked = True
            return httpx.Response(200, json={"access_token": "fresh_bearer_token"})

        if request.url.path == "/api/v1/customers":
            auth = request.headers.get("authorization", "")
            if auth == "Bearer expired_bearer_token":
                return httpx.Response(401, text="Unauthorized Token")
            elif auth == "Bearer fresh_bearer_token":
                if requests_count == 3:  # First call failed 401, second call refreshed token, third call triggers transient 503
                    return httpx.Response(503, headers={"Retry-After": "0.01"}, text="Service Unavailable")
                return httpx.Response(200, json=[{"id": "cust-99", "name": "Global ERP Partner"}])

        return httpx.Response(404, text="Not Found")

    transport = httpx.MockTransport(mock_handler)
    async with httpx.AsyncClient(transport=transport) as client:
        connector = GenericRestConnector(
            tenant_id="tenant-01",
            organization_id="org-01",
            credentials={
                "base_url": "https://api.partner.example.com",
                "auth_type": "oauth2",
                "access_token": "expired_bearer_token",
                "refresh_token": "rf_token_123",
                "token_url": "https://api.partner.example.com/oauth/token",
                "client_id": "client_abc",
                "client_secret": "secret_xyz"
            },
            client=client,
            backoff_factor=0.01
        )

        records = await connector.read("api/v1/customers")
        assert len(records) == 1
        assert records[0]["name"] == "Global ERP Partner"
        assert refresh_invoked is True
        assert connector.access_token == "fresh_bearer_token"


@pytest.mark.asyncio
async def test_generic_rest_end_to_end_crud():
    """Verify Generic REST connector end-to-end CRUD operations."""
    store = {}

    def mock_handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/health":
            return httpx.Response(200, json={"status": "ok"})
        
        if path == "/inventory":
            if request.method == "GET":
                return httpx.Response(200, json={"data": list(store.values())})
            elif request.method == "POST":
                data = json.loads(request.content)
                store[data["sku"]] = data
                return httpx.Response(201, json=data)

        if path.startswith("/inventory/"):
            sku = path.split("/")[-1]
            if request.method == "PUT":
                data = json.loads(request.content)
                store[sku] = {**store.get(sku, {}), **data}
                return httpx.Response(200, json=store[sku])
            elif request.method == "DELETE":
                store.pop(sku, None)
                return httpx.Response(204)

        return httpx.Response(404, text="Not Found")

    transport = httpx.MockTransport(mock_handler)
    async with httpx.AsyncClient(transport=transport) as client:
        connector = GenericRestConnector(
            tenant_id="tenant-01",
            organization_id="org-01",
            credentials={
                "base_url": "https://api.inventory.example.com",
                "auth_type": "api_key",
                "api_key": "secret_key_123",
                "capabilities": ["inventory"]
            },
            client=client
        )

        # 1. Connection check
        conn = await connector.test_connection()
        assert conn["status"] == "Healthy"

        # 2. Create
        created = await connector.create("inventory", {"sku": "SKU-99", "qty": 100})
        assert created["sku"] == "SKU-99"

        # 3. Read
        read_items = await connector.read("inventory")
        assert len(read_items) == 1

        # 4. Update
        updated = await connector.update("inventory", "SKU-99", {"qty": 150})
        assert updated["qty"] == 150

        # 5. Sync
        sync_res = await connector.sync()
        assert sync_res["records_processed"] == 1

        # 6. Delete
        assert await connector.delete("inventory", "SKU-99") is True


# ============================================================================
# 3. Shopify Connector Integration Tests
# ============================================================================

@pytest.mark.asyncio
async def test_shopify_rate_limiting_and_error_retries():
    """Verify Shopify connector respects leaky-bucket limits and retries on 429."""
    attempts = 0

    def mock_handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        assert request.headers.get("x-shopify-access-token") == "shpat_test_token_123"

        if attempts < 2:
            return httpx.Response(
                429,
                headers={"Retry-After": "0.01", "X-Shopify-Shop-Api-Call-Limit": "40/40"},
                text="Rate Exceeded"
            )

        return httpx.Response(
            200,
            headers={"X-Shopify-Shop-Api-Call-Limit": "35/40"},
            json={
                "shop": {
                    "id": 1001,
                    "name": "Acme Flagship Store",
                    "email": "store@acme.com",
                    "currency": "USD"
                }
            }
        )

    transport = httpx.MockTransport(mock_handler)
    async with httpx.AsyncClient(transport=transport) as client:
        connector = ShopifyConnector(
            tenant_id="tenant-01",
            organization_id="org-01",
            credentials={
                "shop_domain": "acme-flagship.myshopify.com",
                "access_token": "shpat_test_token_123"
            },
            client=client,
            backoff_factor=0.01
        )

        test_res = await connector.test_connection()
        assert test_res["status"] == "Healthy"
        assert test_res["shop_name"] == "Acme Flagship Store"
        assert attempts == 2


@pytest.mark.asyncio
async def test_shopify_end_to_end_crud_and_sync():
    """Verify full CRUD and synchronization lifecycle against a Shopify sandbox store."""
    products_db = {
        101: {"id": 101, "title": "Industrial Titanium Valve", "vendor": "Acme Metals", "status": "active"}
    }
    orders_db = [
        {"id": 5001, "order_number": 1001, "total_price": "249.99", "financial_status": "paid"}
    ]

    def mock_handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path

        if path.endswith("/shop.json"):
            return httpx.Response(200, json={"shop": {"id": 1, "name": "Sandbox Store", "currency": "USD"}})

        if path.endswith("/products.json"):
            if request.method == "GET":
                return httpx.Response(200, json={"products": list(products_db.values())})
            elif request.method == "POST":
                body = json.loads(request.content)
                prod = body.get("product", body)
                prod_id = 102
                products_db[prod_id] = {"id": prod_id, **prod}
                return httpx.Response(201, json={"product": products_db[prod_id]})

        if "/products/" in path:
            prod_id = int(path.split("/")[-1].replace(".json", ""))
            if request.method == "PUT":
                body = json.loads(request.content)
                prod = body.get("product", body)
                products_db[prod_id] = {**products_db.get(prod_id, {}), **prod}
                return httpx.Response(200, json={"product": products_db[prod_id]})
            elif request.method == "DELETE":
                products_db.pop(prod_id, None)
                return httpx.Response(200, json={})

        if path.endswith("/orders.json"):
            return httpx.Response(200, json={"orders": orders_db})

        if path.endswith("/customers.json"):
            return httpx.Response(200, json={"customers": [{"id": 1, "email": "customer@example.com"}]})

        return httpx.Response(404, text="Not Found")

    transport = httpx.MockTransport(mock_handler)
    async with httpx.AsyncClient(transport=transport) as client:
        connector = ShopifyConnector(
            tenant_id="tenant-01",
            organization_id="org-01",
            credentials={
                "shop_domain": "sandbox-demo.myshopify.com",
                "access_token": "shpat_sandbox_token_123"
            },
            client=client
        )

        # 1. Health check & Capabilities
        assert await connector.health_check() is True
        caps = await connector.discover_capabilities()
        assert "products" in caps
        assert "orders" in caps

        # 2. Schema
        schema = await connector.get_schema("products")
        assert "title" in schema["fields"]

        # 3. Read
        prods = await connector.read("products")
        assert len(prods) == 1
        assert prods[0]["title"] == "Industrial Titanium Valve"

        # 4. Create Product
        created_prod = await connector.create("products", {"title": "Precision Ceramic Bearing", "vendor": "Acme"})
        assert created_prod["id"] == 102
        assert created_prod["title"] == "Precision Ceramic Bearing"

        # 5. Update Product
        updated_prod = await connector.update("products", "102", {"title": "Precision Ceramic Bearing v2"})
        assert updated_prod["title"] == "Precision Ceramic Bearing v2"

        # 6. Delete Product
        assert await connector.delete("products", "102") is True
        assert 102 not in products_db

        # 7. Incremental Sync
        sync_result = await connector.sync(since=datetime(2026, 1, 1, tzinfo=timezone.utc))
        assert sync_result["status"] == "success"
        assert sync_result["products_synced"] == 1
        assert sync_result["orders_synced"] == 1
        assert sync_result["customers_synced"] == 1

        # 8. Disconnect
        assert await connector.disconnect() is True
