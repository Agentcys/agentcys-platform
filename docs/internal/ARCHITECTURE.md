# Internal Architecture

## API Surface (v1)

| Method | Path | Auth | Service | Audit |
|---|---|---|---|---|
| POST | /v1/tenants | Public (bootstrap) | `TenantService.create_tenant` | N/A |
| POST | /v1/tenants/{tenant_id}/api-keys | Public (bootstrap) | `TenantService.create_api_key` | N/A |

## Middleware Stack

1. `RequestBodySizeLimitMiddleware`
2. `CORSMiddleware`
3. `SecurityHeadersMiddleware`
4. `FetchMetadataCsrfMiddleware`
5. `APIKeyAuthMiddleware`

`APIKeyAuthMiddleware` enforces API-key auth for tenant-scoped `/v1/*` routes, excluding bootstrap tenant routes.

## Auth Data Flow

```mermaid
sequenceDiagram
    Client->>+API: Request /v1/* with X-API-Key
    API->>API: sha256(key)
    API->>+Firestore: lookup tenant_api_keys.key_hash
    Firestore-->>-API: key record / no match
    alt Match found
        API->>API: request.state.tenant_id = key.tenant_id
        API-->>Client: Route handler executes
    else No match
        API-->>Client: 401 Unauthorized
    end
```
