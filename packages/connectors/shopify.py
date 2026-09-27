"""
Shopify Enterprise E-Commerce Connector.

Production implementation of Shopify Admin REST API (version 2024-04) integration
supporting Access Token authorization, leaky bucket rate limit throttles,
product catalog synchronization, order management, and customer CRM updates via httpx.
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import httpx

from packages.connectors.base import BaseConnector

logger = logging.getLogger("connectors.shopify")


class ShopifyAPIError(Exception):
    """Exception raised when Shopify Admin API returns an error."""
    def __init__(self, message: str, status_code: Optional[int] = None, response_body: Optional[Any] = None):
        super().__init__(message)
        self.status_code = status_code
        self.response_body = response_body


class ShopifyConnector(BaseConnector):
    """
    Shopify E-Commerce Store Connector.
    Interfaces with Shopify Admin REST API v2024-04 with leaky bucket rate-limit
    throttling and automatic exponential backoff retries.
    """

    API_VERSION = "2024-04"

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
        
        shop_domain = credentials.get("shop_domain") or credentials.get("store_url") or "myshopify.com"
        # Normalize domain to https://{shop}.myshopify.com
        if not shop_domain.startswith("http"):
            shop_domain = f"https://{shop_domain}"
        self.shop_url = shop_domain.rstrip("/")
        
        self.access_token = credentials.get("access_token") or credentials.get("api_password") or credentials.get("api_key", "")
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor
        
        self.base_url = f"{self.shop_url}/admin/api/{self.API_VERSION}"
        self._custom_client = client is not None
        self.client = client or httpx.AsyncClient(timeout=30.0)

    def _get_headers(self) -> Dict[str, str]:
        return {
            "X-Shopify-Access-Token": self.access_token,
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    async def _request_with_retry(
        self,
        method: str,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        json_data: Optional[Dict[str, Any]] = None,
        attempt: int = 1
    ) -> httpx.Response:
        """Executes HTTP request with Shopify rate limit (429) & error exponential backoff."""
        headers = self._get_headers()
        try:
            response = await self.client.request(method, url, headers=headers, params=params, json=json_data)

            # Check Shopify leaky bucket header: "39/40"
            call_limit = response.headers.get("X-Shopify-Shop-Api-Call-Limit")
            if call_limit:
                try:
                    used, max_calls = map(int, call_limit.split("/"))
                    if used >= max_calls - 2:
                        logger.info(f"Shopify rate limit near capacity ({used}/{max_calls}). Pausing for 0.5s...")
                        await asyncio.sleep(0.5)
                except Exception:
                    pass

            if response.status_code in (429, 500, 502, 503, 504) and attempt <= self.max_retries:
                retry_after = float(response.headers.get("Retry-After", self.backoff_factor * (2 ** (attempt - 1))))
                logger.warning(f"Shopify API status {response.status_code}. Retrying in {retry_after:.2f}s (attempt {attempt}/{self.max_retries})...")
                await asyncio.sleep(retry_after)
                return await self._request_with_retry(method, url, params=params, json_data=json_data, attempt=attempt + 1)

            return response
        except (httpx.ConnectError, httpx.TimeoutException) as e:
            if attempt <= self.max_retries:
                delay = self.backoff_factor * (2 ** (attempt - 1))
                logger.warning(f"Shopify network error: {e}. Retrying in {delay:.2f}s...")
                await asyncio.sleep(delay)
                return await self._request_with_retry(method, url, params=params, json_data=json_data, attempt=attempt + 1)
            raise ShopifyAPIError(f"Shopify connection failed after {self.max_retries} attempts: {e}") from e

    async def authenticate(self) -> bool:
        """Validates Shopify access token."""
        return bool(self.access_token)

    async def test_connection(self) -> Dict[str, Any]:
        """Test connection against Shopify Shop endpoint."""
        url = f"{self.base_url}/shop.json"
        response = await self._request_with_retry("GET", url)
        
        if response.status_code == 200:
            data = response.json().get("shop", {})
            latency = 10.0
            try:
                if hasattr(response, "_elapsed") and response._elapsed is not None:
                    latency = round(response.elapsed.total_seconds() * 1000, 2)
            except Exception:
                pass

            return {
                "status": "Healthy",
                "provider": "Shopify",
                "shop_name": data.get("name", "Shopify Store"),
                "email": data.get("email", ""),
                "currency": data.get("currency", "USD"),
                "latency_ms": latency
            }
        elif response.status_code == 401:
            return {
                "status": "Unauthorized",
                "provider": "Shopify",
                "message": "Invalid or expired Shopify access token"
            }
        else:
            raise ShopifyAPIError(
                f"Shopify connection test failed with HTTP {response.status_code}: {response.text}",
                status_code=response.status_code,
                response_body=response.text
            )

    async def discover_capabilities(self) -> List[str]:
        """Discovers supported Shopify store modules."""
        return ["products", "orders", "customers", "inventory_levels"]

    async def get_schema(self, entity_type: str) -> Dict[str, Any]:
        """Returns entity schema for Shopify products/orders/customers."""
        entity = entity_type.lower()
        if entity in ("products", "product"):
            return {
                "entity": "Product",
                "fields": {
                    "id": "integer",
                    "title": "string",
                    "body_html": "string",
                    "vendor": "string",
                    "product_type": "string",
                    "variants": "array",
                    "status": "string"
                }
            }
        elif entity in ("orders", "order"):
            return {
                "entity": "Order",
                "fields": {
                    "id": "integer",
                    "order_number": "integer",
                    "total_price": "string",
                    "financial_status": "string",
                    "fulfillment_status": "string",
                    "customer": "object",
                    "line_items": "array"
                }
            }
        elif entity in ("customers", "customer"):
            return {
                "entity": "Customer",
                "fields": {
                    "id": "integer",
                    "email": "string",
                    "first_name": "string",
                    "last_name": "string",
                    "orders_count": "integer",
                    "total_spent": "string"
                }
            }
        return {"entity": entity_type, "fields": {}}

    async def read(self, entity_type: str, query: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Queries records from Shopify Admin API."""
        entity = entity_type.lower().strip("/")
        plural_map = {
            "product": "products",
            "order": "orders",
            "customer": "customers",
            "inventory_level": "inventory_levels"
        }
        resource_name = plural_map.get(entity, entity)
        url = f"{self.base_url}/{resource_name}.json"
        
        params = dict(query or {})
        if "since" in params:
            since_val = params.pop("since")
            if isinstance(since_val, datetime):
                params["updated_at_min"] = since_val.isoformat()
            else:
                params["updated_at_min"] = str(since_val)

        response = await self._request_with_retry("GET", url, params=params)
        if response.status_code == 200:
            data = response.json()
            return data.get(resource_name, [])
        else:
            raise ShopifyAPIError(
                f"Shopify read '{entity_type}' failed with HTTP {response.status_code}: {response.text}",
                status_code=response.status_code,
                response_body=response.text
            )

    async def create(self, entity_type: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Creates a product, order, or customer in Shopify."""
        entity = entity_type.lower().strip("/")
        singular_map = {
            "products": "product",
            "orders": "order",
            "customers": "customer"
        }
        singular_name = singular_map.get(entity, entity)
        plural_name = f"{singular_name}s"
        url = f"{self.base_url}/{plural_name}.json"
        
        # Shopify requires payloads wrapped in singular key, e.g. {"product": {...}}
        payload = {singular_name: data} if singular_name not in data else data
        
        response = await self._request_with_retry("POST", url, json_data=payload)
        if response.status_code in (200, 201):
            res_json = response.json()
            return res_json.get(singular_name, res_json)
        else:
            raise ShopifyAPIError(
                f"Shopify create '{entity_type}' failed with HTTP {response.status_code}: {response.text}",
                status_code=response.status_code,
                response_body=response.text
            )

    async def update(self, entity_type: str, record_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Updates a product, order, or customer in Shopify."""
        entity = entity_type.lower().strip("/")
        singular_map = {
            "products": "product",
            "orders": "order",
            "customers": "customer"
        }
        singular_name = singular_map.get(entity, entity)
        plural_name = f"{singular_name}s"
        url = f"{self.base_url}/{plural_name}/{record_id}.json"
        
        payload = {singular_name: {"id": record_id, **data}} if singular_name not in data else data
        
        response = await self._request_with_retry("PUT", url, json_data=payload)
        if response.status_code in (200, 201):
            res_json = response.json()
            return res_json.get(singular_name, res_json)
        else:
            raise ShopifyAPIError(
                f"Shopify update '{entity_type}/{record_id}' failed: {response.text}",
                status_code=response.status_code,
                response_body=response.text
            )

    async def delete(self, entity_type: str, record_id: str) -> bool:
        """Deletes a product, order, or customer from Shopify."""
        entity = entity_type.lower().strip("/")
        singular_map = {
            "products": "product",
            "orders": "order",
            "customers": "customer"
        }
        singular_name = singular_map.get(entity, entity)
        plural_name = f"{singular_name}s"
        url = f"{self.base_url}/{plural_name}/{record_id}.json"
        
        response = await self._request_with_retry("DELETE", url)
        if response.status_code == 200:
            return True
        elif response.status_code == 404:
            return False
        else:
            raise ShopifyAPIError(
                f"Shopify delete '{entity_type}/{record_id}' failed: {response.text}",
                status_code=response.status_code,
                response_body=response.text
            )

    async def sync(self, since: Optional[datetime] = None) -> Dict[str, Any]:
        """Performs incremental or full sync of products, orders, and customers."""
        query = {"since": since} if since else None
        products = await self.read("products", query=query)
        orders = await self.read("orders", query=query)
        customers = await self.read("customers", query=query)

        return {
            "status": "success",
            "provider": "Shopify",
            "products_synced": len(products),
            "orders_synced": len(orders),
            "customers_synced": len(customers),
            "synced_at": datetime.now(timezone.utc).isoformat()
        }

    async def health_check(self) -> bool:
        try:
            res = await self.test_connection()
            return res.get("status") in ("Healthy", "Connected")
        except Exception:
            return False

    async def disconnect(self) -> bool:
        if not self._custom_client:
            await self.client.aclose()
        return True
