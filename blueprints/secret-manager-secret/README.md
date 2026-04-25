# secret-manager-secret

Creates a Secret Manager secret and seeds the initial secret version from a sensitive input value.

## Inputs

| Name | Type | Required | Default | Notes |
|---|---|---|---|---|
| `project_id` | string | yes | none | Google Cloud project ID. |
| `region` | string | yes | none | Replica region for `user_managed` replication. |
| `resource_name_prefix` | string | yes | none | Prefix prepended to `secret_id`. |
| `secret_id` | string | yes | none | Logical secret identifier suffix. |
| `secret_value` | string | yes | none | Sensitive secret payload. |
| `replication` | string | no | `"automatic"` | One of `automatic` or `user_managed`. |

## Outputs

| Name | Type | Description |
|---|---|---|
| `secret_name` | string | Fully qualified secret name. |
| `secret_id` | string | Created secret identifier. |
| `version_id` | string | Created secret version resource name. |

## Notes

- Provider configuration is external to the module.
- `secret_value` is marked sensitive in Terraform and write-only in JSON schema.