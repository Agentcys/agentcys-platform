# cloud-storage-bucket

Creates a Cloud Storage bucket with secure defaults and optional object lifecycle deletion.

## Inputs

| Name | Type | Required | Default | Notes |
|---|---|---|---|---|
| `project_id` | string | yes | none | Google Cloud project ID. |
| `region` | string | yes | none | Bucket location. |
| `resource_name_prefix` | string | yes | none | Prefix applied to the bucket name. |
| `bucket_name_suffix` | string | yes | none | Suffix appended to the bucket name. |
| `storage_class` | string | no | `"STANDARD"` | Bucket storage class. |
| `versioning` | bool | no | `false` | Enables object versioning. |
| `uniform_bucket_level_access` | bool | no | `true` | Enables UBLA. |
| `lifecycle_age_days` | number or null | no | `null` | Deletes objects after the configured age. |
| `force_destroy` | bool | no | `false` | Allows deletion of non-empty buckets. |

## Outputs

| Name | Type | Description |
|---|---|---|
| `bucket_name` | string | Created bucket name. |
| `bucket_url` | string | Canonical bucket URL. |
| `bucket_self_link` | string | Bucket self link. |

## Notes

- Provider configuration is external to the module.
- Public access prevention is always enforced.