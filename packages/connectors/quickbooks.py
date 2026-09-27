"""
QuickBooks Online Enterprise Connector.

Production implementation of Intuit QuickBooks Online v3 REST API integration
supporting OAuth 2.0 token authorization, automatic token refresh, exponential backoff retries,
Invoice querying, Customer sync, and Purchase Order management via httpx.
"""

import asyncio
import base64
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import httpx

from packages.connectors.base import BaseConnector

logger = logging.getLogger("connectors.quickbooks")


class QuickBooksAPIError(Exception):
    """Exception raised when QuickBooks API returns an error."""
    def __init__(self, message: str, status_code: Optional[int] = None, response_body: Optional[Any] = None):
        super().__init__(message)
        self.status_code = status_code
        self.response_body = response_body


class QuickBooksAuthError(QuickBooksAPIError):
    """Exception raised for OAuth authentication and token refresh failures."""
    pass


class QuickBooksConnector(BaseConnector):
    """
    Intuit QuickBooks Online Accounting Connector.
    Interfaces with QuickBooks Online v3 REST API with automatic OAuth 2.0 token refresh
    and resilient exponential backoff retries.
    """

    SANDBOX_BASE_URL = "https://sandbox-quickbooks.api.intuit.com"
    PRODUCTION_BASE_URL = "https://quickbooks.api.intuit.com"
    TOKEN_ENDPOINT = "https://oauth.platform.intuit.com/oauth2/v1/tokens/bearer"

    def __init__(
        self,
        tenant_id: str,
        organization_id: str,
        credentials: Dict[str, Any],
        client: Optional[httpx.AsyncClient] = None,
        max_retries: int = 3,
        backoff_factor: float = 0.5
    ):
        super().__init__(tenant_id, organization_id, credentials)
        
        self.realm_id = str(credentials.get("realm_id") or credentials.get("company_id") or "sandbox_company_01")
        self.client_id = credentials.get("client_id", "")
        self.client_secret = credentials.get("client_secret", "")
        self.access_token = credentials.get("access_token", "")
        self.refresh_token = credentials.get("refresh_token", "")
        self.is_sandbox = credentials.get("environment", "sandbox").lower() == "sandbox"
        
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor
        
        self.base_url = self.SANDBOX_BASE_URL if self.is_sandbox else self.PRODUCTION_BASE_URL
        self._custom_client = client is not None
        self.client = client or httpx.AsyncClient(timeout=30.0)
        self._lock = asyncio.Lock()

    def _get_headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    async def refresh_access_token(self) -> Dict[str, Any]:
        """
        Refreshes OAuth 2.0 access token using Intuit's OAuth endpoint.
        Uses Basic Auth with client_id:client_secret and grant_type=refresh_token.
        """
        async with self._lock:
            if not self.refresh_token:
                raise QuickBooksAuthError("No refresh_token provided in credentials for OAuth refresh.")

            auth_str = f"{self.client_id}:{self.client_secret}"
            encoded_auth = base64.b64encode(auth_str.encode("utf-8")).decode("utf-8")
            
            headers = {
                "Authorization": f"Basic {encoded_auth}",
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json",
            }
            data = {
                "grant_type": "refresh_token",
                "refresh_token": self.refresh_token,
            }

            try:
                response = await self.client.post(self.TOKEN_ENDPOINT, headers=headers, data=data)
                if response.status_code == 200:
                    token_data = response.json()
                    self.access_token = token_data.get("access_token", self.access_token)
                    self.refresh_token = token_data.get("refresh_token", self.refresh_token)
                    self.credentials["access_token"] = self.access_token
                    self.credentials["refresh_token"] = self.refresh_token
                    logger.info("Successfully refreshed QuickBooks OAuth 2.0 access token.")
                    return token_data
                else:
                    error_msg = f"Failed to refresh QuickBooks token: HTTP {response.status_code} - {response.text}"
                    logger.error(error_msg)
                    raise QuickBooksAuthError(error_msg, status_code=response.status_code, response_body=response.text)
            except httpx.RequestError as e:
                error_msg = f"Network error during QuickBooks token refresh: {str(e)}"
                logger.error(error_msg)
                raise QuickBooksAuthError(error_msg) from e

    async def _request_with_retry(
        self,
        method: str,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        json_data: Optional[Dict[str, Any]] = None,
        attempt: int = 1
    ) -> httpx.Response:
        """
        Executes HTTP request with automatic 401 token refresh and exponential backoff retry.
        """
        headers = self._get_headers()
        try:
            response = await self.client.request(method, url, headers=headers, params=params, json=json_data)
            
            # Handle token expiration (401 Unauthorized)
            if response.status_code == 401 and attempt <= self.max_retries and self.refresh_token and self.client_id:
                logger.warning(f"QuickBooks 401 Unauthorized. Attempting OAuth token refresh (attempt {attempt}/{self.max_retries})...")
                await self.refresh_access_token()
                return await self._request_with_retry(method, url, params=params, json_data=json_data, attempt=attempt + 1)

            # Handle rate limiting (429) or transient 5xx server errors
            if response.status_code in (429, 500, 502, 503, 504) and attempt <= self.max_retries:
                retry_after = float(response.headers.get("Retry-After", self.backoff_factor * (2 ** (attempt - 1))))
                logger.warning(f"QuickBooks API returned {response.status_code}. Retrying in {retry_after:.2f}s...")
                await asyncio.sleep(retry_after)
                return await self._request_with_retry(method, url, params=params, json_data=json_data, attempt=attempt + 1)

            return response
        except (httpx.ConnectError, httpx.TimeoutException) as e:
            if attempt <= self.max_retries:
                delay = self.backoff_factor * (2 ** (attempt - 1))
                logger.warning(f"QuickBooks network error: {e}. Retrying in {delay:.2f}s (attempt {attempt}/{self.max_retries})...")
                await asyncio.sleep(delay)
                return await self._request_with_retry(method, url, params=params, json_data=json_data, attempt=attempt + 1)
            raise QuickBooksAPIError(f"QuickBooks network connection failed after {self.max_retries} attempts: {e}") from e

    async def authenticate(self) -> bool:
        """Validates OAuth token readiness."""
        if not self.access_token and self.refresh_token:
            try:
                await self.refresh_access_token()
            except Exception as e:
                logger.error(f"Authentication failed on initial token refresh: {e}")
                return False
        return bool(self.access_token)

    async def test_connection(self) -> Dict[str, Any]:
        """Test connection against QuickBooks CompanyInfo endpoint."""
        url = f"{self.base_url}/v3/company/{self.realm_id}/companyinfo/{self.realm_id}"
        response = await self._request_with_retry("GET", url)
        
        if response.status_code == 200:
            data = response.json()
            company_name = data.get("CompanyInfo", {}).get("CompanyName", "QuickBooks Sandbox Company")
            latency = 12.0
            try:
                if hasattr(response, "_elapsed") and response._elapsed is not None:
                    latency = round(response.elapsed.total_seconds() * 1000, 2)
            except Exception:
                pass

            return {
                "status": "Healthy",
                "provider": "QuickBooks Online",
                "company_name": company_name,
                "latency_ms": latency
            }
        elif response.status_code == 401:
            return {
                "status": "Unauthorized",
                "provider": "QuickBooks Online",
                "message": "OAuth access token expired or invalid"
            }
        else:
            raise QuickBooksAPIError(
                f"QuickBooks test_connection failed with status {response.status_code}: {response.text}",
                status_code=response.status_code,
                response_body=response.text
            )

    async def discover_capabilities(self) -> List[str]:
        """Returns supported QuickBooks Online entity types."""
        return ["invoices", "customers", "items", "purchase_orders", "payments"]

    async def get_schema(self, entity_type: str) -> Dict[str, Any]:
        """Return schema representation for QuickBooks entities."""
        entity = entity_type.lower()
        if entity in ["invoices", "invoice"]:
            return {
                "entity": "Invoice",
                "fields": {
                    "Id": "string",
                    "DocNumber": "string",
                    "TxnDate": "string",
                    "CustomerRef": {"value": "string", "name": "string"},
                    "TotalAmt": "number",
                    "Line": "array",
                    "Balance": "number",
                    "DueDate": "string"
                }
            }
        elif entity in ["customers", "customer"]:
            return {
                "entity": "Customer",
                "fields": {
                    "Id": "string",
                    "DisplayName": "string",
                    "PrimaryEmailAddr": "string",
                    "PrimaryPhone": "string",
                    "Balance": "number",
                    "Active": "boolean"
                }
            }
        elif entity in ["items", "item", "inventory"]:
            return {
                "entity": "Item",
                "fields": {
                    "Id": "string",
                    "Name": "string",
                    "Type": "string",
                    "QtyOnHand": "number",
                    "UnitPrice": "number"
                }
            }
        return {"entity": entity_type, "fields": {}}

    async def read(self, entity_type: str, query: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Query records from QuickBooks Online v3 API using SQL-like syntax."""
        entity = entity_type.lower()
        table_map = {
            "invoices": "Invoice",
            "invoice": "Invoice",
            "customers": "Customer",
            "customer": "Customer",
            "items": "Item",
            "item": "Item",
            "purchase_orders": "PurchaseOrder",
            "payments": "Payment"
        }
        table_name = table_map.get(entity, entity.capitalize())
        
        limit = query.get("limit", 20) if query else 20
        where_clause = ""
        if query and "since" in query:
            since_val = query["since"]
            if isinstance(since_val, datetime):
                since_str = since_val.strftime("%Y-%m-%dT%H:%M:%S%z")
            else:
                since_str = str(since_val)
            where_clause = f" WHERE MetaData.LastUpdatedTime > '{since_str}'"

        sql = f"select * from {table_name}{where_clause} maxresults {limit}"
        url = f"{self.base_url}/v3/company/{self.realm_id}/query"
        
        response = await self._request_with_retry("GET", url, params={"query": sql})
        if response.status_code == 200:
            data = response.json()
            query_resp = data.get("QueryResponse", {})
            return query_resp.get(table_name, [])
        else:
            raise QuickBooksAPIError(
                f"QuickBooks read '{entity_type}' failed with status {response.status_code}: {response.text}",
                status_code=response.status_code,
                response_body=response.text
            )

    async def create(self, entity_type: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create an invoice, customer, or purchase order in QuickBooks Online."""
        entity = entity_type.lower()
        endpoint_map = {
            "invoices": "invoice",
            "invoice": "invoice",
            "customers": "customer",
            "customer": "customer",
            "items": "item",
            "item": "item"
        }
        endpoint = endpoint_map.get(entity, entity)
        url = f"{self.base_url}/v3/company/{self.realm_id}/{endpoint}"
        
        response = await self._request_with_retry("POST", url, json_data=data)
        if response.status_code in (200, 201):
            res_json = response.json()
            key_name = endpoint.capitalize()
            return res_json.get(key_name, res_json)
        else:
            raise QuickBooksAPIError(
                f"QuickBooks create '{entity_type}' failed with status {response.status_code}: {response.text}",
                status_code=response.status_code,
                response_body=response.text
            )

    async def update(self, entity_type: str, record_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Update a record in QuickBooks Online."""
        entity = entity_type.lower()
        endpoint_map = {
            "invoices": "invoice",
            "invoice": "invoice",
            "customers": "customer",
            "customer": "customer"
        }
        endpoint = endpoint_map.get(entity, entity)
        url = f"{self.base_url}/v3/company/{self.realm_id}/{endpoint}"
        
        payload = {"Id": record_id, **data}
        response = await self._request_with_retry("POST", url, json_data=payload)
        if response.status_code in (200, 201):
            res_json = response.json()
            return res_json.get(endpoint.capitalize(), res_json)
        else:
            raise QuickBooksAPIError(
                f"QuickBooks update '{entity_type}' record '{record_id}' failed: {response.text}",
                status_code=response.status_code,
                response_body=response.text
            )

    async def delete(self, entity_type: str, record_id: str) -> bool:
        """Soft delete/void a record in QuickBooks Online."""
        entity = entity_type.lower()
        url = f"{self.base_url}/v3/company/{self.realm_id}/{entity}?operation=delete"
        payload = {"Id": record_id, "SyncToken": "0"}
        response = await self._request_with_retry("POST", url, json_data=payload)
        if response.status_code == 200:
            return True
        elif response.status_code == 404:
            return False
        else:
            raise QuickBooksAPIError(
                f"QuickBooks delete '{entity_type}' failed: {response.text}",
                status_code=response.status_code,
                response_body=response.text
            )

    async def sync(self, since: Optional[datetime] = None) -> Dict[str, Any]:
        """Synchronizes invoices and customers from QuickBooks Online."""
        query = {"since": since} if since else None
        invoices = await self.read("invoices", query=query)
        customers = await self.read("customers", query=query)
        
        return {
            "status": "success",
            "provider": "QuickBooks Online",
            "invoices_synced": len(invoices),
            "customers_synced": len(customers),
            "synced_at": datetime.now(timezone.utc).isoformat()
        }

    async def health_check(self) -> bool:
        try:
            res = await self.test_connection()
            return res.get("status") in ["Healthy", "Connected"]
        except Exception:
            return False

    async def disconnect(self) -> bool:
        if not self._custom_client:
            await self.client.aclose()
        return True
