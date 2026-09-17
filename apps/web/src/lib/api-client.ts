/**
 * Centralized API client for all frontend data queries.
 * Automatically resolves NEXT_PUBLIC_API_URL and attaches Authorization Bearer tokens.
 */

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

class ApiClient {
  private base: string;

  constructor(baseUrl: string) {
    this.base = baseUrl.replace(/\/$/, "");
  }

  private async getAuthToken(): Promise<string | null> {
    if (typeof window === "undefined") return null;
    try {
      const res = await fetch("/api/auth/me");
      if (res.ok) {
        const data = await res.json();
        return data.token || null;
      }
    } catch {}
    return null;
  }

  private async request(endpoint: string, options: RequestInit = {}): Promise<any> {
    const url = endpoint.startsWith("http") ? endpoint : `${this.base}${endpoint.startsWith("/") ? "" : "/"}${endpoint}`;
    
    const headers = new Headers(options.headers || {});
    if (!headers.has("Content-Type") && !(options.body instanceof FormData)) {
      headers.set("Content-Type", "application/json");
    }

    // Attach token if not present
    if (!headers.has("Authorization")) {
      const token = await this.getAuthToken();
      if (token) {
        headers.set("Authorization", `Bearer ${token}`);
      }
    }

    const config: RequestInit = {
      ...options,
      headers,
    };

    let response = await fetch(url, config);

    // If 401, attempt silent refresh
    if (response.status === 401 && typeof window !== "undefined") {
      try {
        const refreshRes = await fetch("/api/auth/refresh", { method: "POST" });
        if (refreshRes.ok) {
          const refreshData = await refreshRes.json();
          if (refreshData.access_token) {
            headers.set("Authorization", `Bearer ${refreshData.access_token}`);
            response = await fetch(url, { ...options, headers });
          }
        }
      } catch {}
    }

    if (!response.ok) {
      let errDetail = `HTTP ${response.status}`;
      try {
        const errData = await response.json();
        errDetail = errData.detail || errData.message || errDetail;
      } catch {}
      throw new Error(errDetail);
    }

    return response.json();
  }

  get(endpoint: string, options: RequestInit = {}) {
    return this.request(endpoint, { ...options, method: "GET" });
  }

  post(endpoint: string, body?: any, options: RequestInit = {}) {
    return this.request(endpoint, {
      ...options,
      method: "POST",
      body: body ? JSON.stringify(body) : undefined,
    });
  }

  put(endpoint: string, body?: any, options: RequestInit = {}) {
    return this.request(endpoint, {
      ...options,
      method: "PUT",
      body: body ? JSON.stringify(body) : undefined,
    });
  }

  delete(endpoint: string, options: RequestInit = {}) {
    return this.request(endpoint, { ...options, method: "DELETE" });
  }
}

export const apiClient = new ApiClient(API_BASE);
export default apiClient;
