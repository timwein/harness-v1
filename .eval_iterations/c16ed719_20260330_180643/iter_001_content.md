```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "$id": "https://api.example.com/schemas/billing-system/v1.0.0",
  "title": "Multi-Tenant SaaS Billing System Schema",
  "version": "1.0.0",
  "definitions": {
    "money": {
      "type": "object",
      "properties": {
        "amount": {
          "type": "number",
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
    "uuid": {
      "type": "string",
      "pattern": "^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
    },
    "timestamp": {
      "type": "string",
      "format": "date-time"
    },
    "billing_interval": {
      "type": "string",
      "enum": ["monthly", "quarterly", "annually"]
    },
    "metered_dimension": {
      "type": "object",
      "properties": {
        "id": {
          "type": "string",
          "pattern": "^[a-z][a-z0-9_]*$"
        },
        "name": {
          "type": "string"
        },
        "unit": {
          "type": "string"
        },
        "aggregation_type": {
          "type": "string",
          "enum": ["sum", "max", "unique_count"]
        },
        "tiers": {
          "type": "array",
          "items": {
            "$ref": "#/definitions/pricing_tier"
          },
          "minItems": 1
        }
      },
      "required": ["id", "name", "unit", "aggregation_type", "tiers"],
      "additionalProperties": false
    },
    "pricing_tier": {
      "type": "object",
      "properties": {
        "start_at": {
          "type": "number",
          "minimum": 0
        },
        "end_at": {
          "type": ["number", "null"],
          "minimum": 0
        },
        "unit_price": {
          "$ref": "#/definitions/money"
        },
        "flat_fee": {
          "$ref": "#/definitions/money"
        }
      },
      "required": ["start_at", "unit_price"],
      "additionalProperties": false
    },
    "line_item": {
      "type": "object",
      "properties": {
        "id": {
          "$ref": "#/definitions/uuid"
        },
        "description": {
          "type": "string"
        },
        "type": {
          "type": "string",
          "enum": ["seat", "usage", "one_time", "proration", "discount"]
        },
        "quantity": {
          "type": "number",
          "minimum": 0
        },
        "unit_amount": {
          "$ref": "#/definitions/money"
        },
        "total_amount": {
          "$ref": "#/definitions/money"
        },
        "period_start": {
          "$ref": "#/definitions/timestamp"
        },
        "period_end": {
          "$ref": "#/definitions/timestamp"
        },
        "metered_dimension_id": {
          "type": ["string", "null"]
        },
        "metadata": {
          "type": "object",
          "additionalProperties": true
        }
      },
      "required": ["id", "description", "type", "quantity", "unit_amount", "total_amount"],
      "additionalProperties": false
    }
  },
  "type": "object",
  "properties": {
    "tenants": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "id": {
            "$ref": "#/definitions/uuid"
          },
          "name": {
            "type": "string",
            "minLength": 1
          },
          "status": {
            "type": "string",
            "enum": ["active", "suspended", "cancelled"]
          },
          "created_at": {
            "$ref": "#/definitions/timestamp"
          },
          "metadata": {
            "type": "object",
            "additionalProperties": true
          }
        },
        "required": ["id", "name", "status", "created_at"],
        "additionalProperties": false
      }
    },
    "plans": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "id": {
            "$ref": "#/definitions/uuid"
          },
          "name": {
            "type": "string",
            "minLength": 1
          },
          "description": {
            "type": "string"
          },
          "status": {
            "type": "string",
            "enum": ["active", "deprecated", "archived"]
          },
          "pricing_model": {
            "type": "object",
            "properties": {
              "type": {
                "type": "string",
                "enum": ["seat_based", "usage_based", "hybrid"]
              },
              "seat_price": {
                "$ref": "#/definitions/money"
              },
              "billing_interval": {
                "$ref": "#/definitions/billing_interval"
              },
              "trial_days": {
                "type": "integer",
                "minimum": 0
              },
              "metered_dimensions": {
                "type": "array",
                "items": {
                  "$ref": "#/definitions/metered_dimension"
                }
              },
              "included_seats": {
                "type": "integer",
                "minimum": 0
              },
              "additional_seat_price": {
                "$ref": "#/definitions/money"
              }
            },
            "required": ["type", "billing_interval"],
            "additionalProperties": false,
            "if": {
              "properties": {
                "type": {
                  "const": "seat_based"
                }
              }
            },
            "then": {
              "required": ["seat_price"]
            },
            "else": {
              "if": {
                "properties": {
                  "type": {
                    "const": "usage_based"
                  }
                }
              },
              "then": {
                "required": ["metered_dimensions"]
              },
              "else": {
                "required": ["seat_price", "metered_dimensions"]
              }
            }
          },
          "created_at": {
            "$ref": "#/definitions/timestamp"
          },
          "metadata": {
            "type": "object",
            "additionalProperties": true
          }
        },
        "required": ["id", "name", "status", "pricing_model", "created_at"],
        "additionalProperties": false
      }
    },
    "subscriptions": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "id": {
            "$ref": "#/definitions/uuid"
          },
          "tenant_id": {
            "$ref": "#/definitions/uuid"
          },
          "plan_id": {
            "$ref": "#/definitions/uuid"
          },
          "status": {
            "type": "string",
            "enum": ["trialing", "active", "past_due", "cancelled", "unpaid", "paused"]
          },
          "current_period_start": {
            "$ref": "#/definitions/timestamp"
          },
          "current_period_end": {
            "$ref": "#/definitions/timestamp"
          },
          "trial_start": {
            "type": ["string", "null"],
            "format": "date-time"
          },
          "trial_end": {
            "type": ["string", "null"],
            "format": "date-time"
          },
          "seats": {
            "type": "integer",
            "minimum": 1
          },
          "proration_behavior": {
            "type": "string",
            "enum": ["none", "create_prorations", "always_invoice"]
          },
          "created_at": {
            "$ref": "#/definitions/timestamp"
          },
          "cancelled_at": {
            "type": ["string", "null"],
            "format": "date-time"
          },
          "ended_at": {
            "type": ["string", "null"],
            "format": "date-time"
          },
          "metadata": {
            "type": "object",
            "additionalProperties": true
          }
        },
        "required": ["id", "tenant_id", "plan_id", "status", "current_period_start", "current_period_end", "seats", "proration_behavior", "created_at"],
        "additionalProperties": false
      }
    },
    "usage_records": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "id": {
            "$ref": "#/definitions/uuid"
          },
          "subscription_id": {
            "$ref": "#/definitions/uuid"
          },
          "metered_dimension_id": {
            "type": "string"
          },
          "quantity": {
            "type": "number",
            "minimum": 0
          },
          "timestamp": {
            "$ref": "#/definitions/timestamp"
          },
          "action": {
            "type": "string",
            "enum": ["increment", "set"]
          },
          "metadata": {
            "type": "object",
            "additionalProperties": true
          }
        },
        "required": ["id", "subscription_id", "metered_dimension_id", "quantity", "timestamp", "action"],
        "additionalProperties": false
      }
    },
    "invoices": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "id": {
            "$ref": "#/definitions/uuid"
          },
          "tenant_id": {
            "$ref": "#/definitions/uuid"
          },
          "subscription_id": {
            "$ref": "#/definitions/uuid"
          },
          "number": {
            "type": "string",
            "pattern": "^INV-[0-9]+$"
          },
          "status": {
            "type": "string",
            "enum": ["draft", "open", "paid", "void", "uncollectible"]
          },
          "currency": {
            "type": "string",
            "pattern": "^[A-Z]{3}$"
          },
          "subtotal": {
            "type": "number",
            "minimum": 0
          },
          "tax": {
            "type": "number",
            "minimum": 0
          },
          "total": {
            "type": "number",
            "minimum": 0
          },
          "amount_paid": {
            "type": "number",
            "minimum": 0
          },
          "amount_due": {
            "type": "number",
            "minimum": 0
          },
          "line_items": {
            "type": "array",
            "items": {
              "$ref": "#/definitions/line_item"
            },
            "minItems": 1
          },
          "period_start": {
            "$ref": "#/definitions/timestamp"
          },
          "period_end": {
            "$ref": "#/definitions/timestamp"
          },
          "due_date": {
            "$ref": "#/definitions/timestamp"
          },
          "created_at": {
            "$ref": "#/definitions/timestamp"
          },
          "paid_at": {
            "type": ["string", "null"],
            "format": "date-time"
          },
          "voided_at": {
            "type": ["string", "null"],
            "format": "date-time"
          },
          "payment_method": {
            "type": "object",
            "properties": {
              "type": {
                "type": "string",
                "enum": ["card", "bank_account", "ach", "wire_transfer"]
              },
              "last_four": {
                "type": "string",
                "pattern": "^[0-9]{4}$"
              }
            },
            "required": ["type"],
            "additionalProperties": false
          },
          "metadata": {
            "type": "object",
            "additionalProperties": true
          }
        },
        "required": ["id", "tenant_id", "subscription_id", "number", "status", "currency", "subtotal", "tax", "total", "amount_paid", "amount_due", "line_items", "period_start", "period_end", "due_date", "created_at"],
        "additionalProperties": false
      }
    },
    "subscription_changes": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "id": {
            "$ref": "#/definitions/uuid"
          },
          "subscription_id": {
            "$ref": "#/definitions/uuid"
          },
          "change_type": {
            "type": "string",
            "enum": ["upgrade", "downgrade", "seat_change", "plan_change", "cancellation", "reactivation"]
          },
          "effective_date": {
            "$ref": "#/definitions/timestamp"
          },
          "old_plan_id": {
            "type": ["string", "null"]
          },
          "new_plan_id": {
            "type": ["string", "null"]
          },
          "old_seats": {
            "type": ["integer", "null"],
            "minimum": 0
          },
          "new_seats": {
            "type": ["integer", "null"],
            "minimum": 0
          },
          "proration_invoice_id": {
            "type": ["string", "null"]
          },
          "created_at": {
            "$ref": "#/definitions/timestamp"
          },
          "metadata": {
            "type": "object",
            "additionalProperties": true
          }
        },
        "required": ["id", "subscription_id", "change_type", "effective_date", "created_at"],
        "additionalProperties": false
      }
    }
  },
  "required": ["tenants", "plans", "subscriptions", "usage_records", "invoices", "subscription_changes"],
  "additionalProperties": false
}
```