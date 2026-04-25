# firestore-database

Creates a Firestore Native database and maps a deployment region to a supported Firestore multi-region location when applicable.

## Inputs

| Name | Type | Required | Default | Notes |
|---|---|---|---|---|
| `project_id` | string | yes | none | Google Cloud project ID. |
| `region` | string | yes | none | Region mapped to a Firestore location via local lookup. |
| `resource_name_prefix` | string | yes | none | Reserved for catalog consistency. |
| `database_id` | string | no | `"(default)"` | Firestore database ID. |
| `deletion_protection` | bool | no | `true` | Uses `ABANDON` deletion policy by default. |
| `point_in_time_recovery` | bool | no | `false` | Enables PITR when supported. |

## Outputs

| Name | Type | Description |
|---|---|---|
| `database_name` | string | Fully qualified Firestore database name. |
| `database_id` | string | Firestore database ID. |

## Notes

- Provider configuration is external to the module.
- Unknown regions fall back to the raw `region` value.