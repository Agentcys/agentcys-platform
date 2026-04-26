# cloud-run-service

Deploys a Google Cloud Run v2 service with configurable container settings and optional public invocation.

## Inputs

| Name | Type | Required | Default | Notes |
|---|---|---|---|---|
| `project_id` | string | yes | none | Google Cloud project ID. |
| `region` | string | yes | none | Deployment region. |
| `resource_name_prefix` | string | yes | none | Cloud Run service name. |
| `container_image` | string | yes | none | OCI image to deploy. |
| `port` | number | no | `8080` | Container port. |
| `env_vars` | map(string) | no | `{}` | Plaintext environment variables. |
| `min_instances` | number | no | `0` | Minimum instance count. |
| `max_instances` | number | no | `10` | Maximum instance count. |
| `cpu` | string | no | `"1"` | CPU limit. |
| `memory` | string | no | `"512Mi"` | Memory limit. |
| `allow_unauthenticated` | bool | no | `false` | Grants `roles/run.invoker` to `allUsers` when enabled. |

## Outputs

| Name | Type | Description |
|---|---|---|
| `service_url` | string | HTTPS service URL. |
| `service_name` | string | Cloud Run service name. |
| `service_id` | string | Fully qualified service resource ID. |

## Notes

- Provider configuration is external to the module.
- Public access is disabled by default.