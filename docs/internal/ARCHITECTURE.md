# Internal Architecture

## API Surface (v1)

| Method | Path | Auth | Service | Audit |
|---|---|---|---|---|
| POST | /v1/tenants | Public (bootstrap) | `TenantService.create_tenant` | N/A |
| POST | /v1/tenants/{tenant_id}/api-keys | Public (bootstrap) | `TenantService.create_api_key` | N/A |
| POST | /v1/credentials | API key | `CredentialService.create_credential` | `credential.uploaded` |
| POST | /v1/projects | API key | `ProjectService.link_project` | `project.linked` |
| GET | /v1/blueprints | API key | `BlueprintService.list_blueprints` | N/A |
| GET | /v1/blueprints/{blueprint_id} | API key | `BlueprintService.get_blueprint_with_latest` | N/A |

## Middleware Stack

1. `RequestBodySizeLimitMiddleware`
2. `CORSMiddleware`
3. `SecurityHeadersMiddleware`
4. `FetchMetadataCsrfMiddleware`
5. `APIKeyAuthMiddleware`

`APIKeyAuthMiddleware` enforces API-key auth for tenant-scoped `/v1/*` routes, excluding bootstrap tenant routes.

## Credential + Project Flow

```mermaid
sequenceDiagram
    Client->>+API: POST /v1/projects
    API->>+Firestore: load credential by credential_id
    Firestore-->>-API: credential (tenant scoped)
    API->>+CloudStorage: create/verify tf-state bucket
    CloudStorage-->>-API: bucket versioning enabled
    API->>+Firestore: insert customer_projects
    Firestore-->>-API: project persisted
    API-->>-Client: 201 Created
```

## Blueprint Read Flow

```mermaid
sequenceDiagram
    Client->>+API: GET /v1/blueprints/{blueprint_id}
    API->>+Firestore: query blueprints by blueprint_id
    Firestore-->>-API: blueprint metadata
    API->>+Firestore: query blueprint_versions by latest_version
    Firestore-->>-API: version payload
    API-->>-Client: 200 OK { blueprint + latest }
```

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
