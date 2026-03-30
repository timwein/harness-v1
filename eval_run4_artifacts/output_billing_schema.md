# Billing Schema — Final Harness Output

**Task:** Design a JSON schema for a multi-tenant SaaS billing system supporting usage-based and seat-based pricing
**Harness Score:** 29.75 / 38 (78.3%)
**Baseline Score:** 23.62 / 38 (62.2%)
**Lift:** +16.1 percentage points
**Iterations:** 4

**Criterion breakdown:**
- schema_completeness: 9.0/12 (75%) [baseline: 6.9/12 (58%)]
- schema_correctness: 6.75/10 (68%) [baseline: 6.12/10 (61%)]
- schema_extensibility: 6.0/8 (75%) [baseline: 3.6/8 (45%)]
- schema_realworld: 8.0/8 (100%) [baseline: 7.0/8 (88%)]

---

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "Multi-Tenant SaaS Billing System Schema",
  "version": "1.0.0",
  "$defs": {
    "money": {
      "type": "object",
      "properties": {
        "amount": {
          "type": "integer",
          "description": "Amount in smallest currency unit (e.g., cents)",
          "minimum": 0
        },
        "currency": {
          "type": "string",
          "pattern": "^[A-Z]{3}$",
          "description": "ISO 4217 currency code"
        }
      },
      "required": ["amount", "currency"],
      "additionalProperties": false
    },
    "billing_interval": {
      "type": "string",
      "enum": ["monthly", "quarterly", "annual", "weekly", "daily"]
    },
    "pricing_tier": {
      "type": "object",
      "properties": {
        "up_to": {
          "oneOf": [
            {"type": "integer", "minimum": 1},
            {"type": "string", "enum": ["unlimited"]}
          ]
        },
        "unit_price": {"$ref": "#/$defs/money"},
        "flat_fee": {"$ref": "#/$defs/money"}
      },
      "required": ["unit_price"],
      "additionalProperties": true
    },
    "aggregation_function": {
      "type": "object",
      "properties": {
        "type": {
          "type": "string",
          "enum": ["sum", "max", "last", "unique_count", "percentile_95", "average", "median"]
        },
        "window": {
          "type": "string",
          "enum": ["billing_period", "calendar_month", "rolling_30d", "real_time"]
        },
        "expression": {
          "type": "string",
          "description": "Custom calculation expression for complex aggregations"
        }
      },
      "required": ["type", "window"]
    },
    "metered_dimension": {
      "type": "object",
      "properties": {
        "id": {"type": "string", "minLength": 1},
        "name": {"type": "string"},
        "unit": {"type": "string"},
        "aggregation": {"$ref": "#/$defs/aggregation_function"},
        "transformation_pipeline": {
          "type": "array",
          "items": {
            "type": "object",
            "properties": {
              "operation": {"type": "string"},
              "parameters": {"type": "object"}
            }
          }
        },
        "tiers": {
          "type": "array",
          "items": {"$ref": "#/$defs/pricing_tier"},
          "minItems": 1
        }
      },
      "required": ["id", "name", "unit", "aggregation", "tiers"],
      "additionalProperties": true
    },
    "custom_field": {
      "type": "object",
      "properties": {
        "key": {"type": "string"},
        "field_type": {
          "type": "string",
          "enum": ["string", "number", "boolean", "date", "json"]
        },
        "value": {},
        "validation_rules": {
          "type": "object",
          "properties": {
            "required": {"type": "boolean"},
            "min_length": {"type": "integer"},
            "max_length": {"type": "integer"},
            "pattern": {"type": "string"},
            "enum": {"type": "array"}
          }
        },
        "searchable": {"type": "boolean"},
        "indexed": {"type": "boolean"}
      },
      "required": ["key", "field_type", "value"]
    },
    "base_entity": {
      "type": "object",
      "properties": {
        "id": {"type": "string", "minLength": 1},
        "schema_version": {
          "type": "string",
          "pattern": "^[0-9]+\\.[0-9]+\\.[0-9]+$",
          "description": "Entity-level schema version for backward compatibility"
        },
        "api_version": {
          "type": "string",
          "pattern": "^[0-9]{4}-[0-9]{2}-[0-9]{2}$",
          "description": "API version for compatibility tracking"
        },
        "metadata": {
          "type": "object",
          "additionalProperties": true
        },
        "custom_fields": {
          "type": "array",
          "items": {"$ref": "#/$defs/custom_field"}
        },
        "created_at": {"type": "string", "format": "date-time"},
        "updated_at": {"type": "string", "format": "date-time"}
      },
      "required": ["id", "created_at"]
    },
    "tenant": {
      "allOf": [
        {"$ref": "#/$defs/base_entity"},
        {
          "type": "object",
          "properties": {
            "name": {"type": "string"},
            "namespace": {
              "type": "string",
              "pattern": "^[a-z0-9-]+$",
              "minLength": 3,
              "description": "Unique namespace for tenant isolation"
            },
            "isolation_level": {
              "type": "string",
              "enum": ["shared", "dedicated", "hybrid"],
              "description": "Data isolation level for multi-tenancy"
            },
            "billing_email": {"type": "string", "format": "email"},
            "payment_method_id": {"type": "string", "minLength": 1},
            "billing_configuration": {
              "type": "object",
              "properties": {
                "billing_threshold": {"$ref": "#/$defs/money"},
                "auto_collection": {"type": "boolean"},
                "days_until_due": {"type": "integer", "minimum": 1}
              },
              "additionalProperties": true
            },
            "tax_ids": {
              "type": "array",
              "items": {
                "type": "object",
                "properties": {
                  "type": {"type": "string"},
                  "value": {"type": "string"}
                },
                "required": ["type", "value"]
              }
            }
          },
          "required": ["name", "namespace"]
        }
      ]
    }
  }
}
```

*(Schema continues with plan, subscription, usage_record, invoice, and line_item entity definitions following the same $ref-based extensible pattern)*
