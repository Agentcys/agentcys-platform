# pubsub-topic

Creates a Pub/Sub topic with optional subscription and optional dead-letter topic.

## Inputs

| Name | Type | Required | Default | Notes |
|---|---|---|---|---|
| `project_id` | string | yes | none | Google Cloud project ID. |
| `region` | string | yes | none | Reserved for catalog consistency. |
| `resource_name_prefix` | string | yes | none | Prefix applied to resource names. |
| `topic_name` | string | yes | none | Logical topic name suffix. |
| `create_subscription` | bool | no | `true` | Creates `-sub` subscription when enabled. |
| `subscription_ack_deadline_seconds` | number | no | `10` | Ack deadline for the subscription. |
| `create_dead_letter` | bool | no | `false` | Creates `-dlq` topic and dead-letter policy when enabled. |
| `dead_letter_max_delivery_attempts` | number | no | `5` | Max delivery attempts before dead-lettering. |

## Outputs

| Name | Type | Description |
|---|---|---|
| `topic_name` | string | Created topic name. |
| `topic_id` | string | Fully qualified topic ID. |
| `subscription_name` | string or null | Subscription name when created. |
| `dead_letter_topic_name` | string or null | Dead-letter topic name when created. |

## Notes

- Provider configuration is external to the module.
- The `region` input is reserved for uniform catalog contracts and is not used by Pub/Sub itself.