```json
{
  "$schema": "https://json-schema.org/draft/2019-09/schema",
  "$id": "https://saas-billing.example.com/schema/v1",
  "title": "Multi-Tenant SaaS Billing System Schema",
  "description": "JSON Schema for usage-based and seat-based billing in multi-tenant SaaS",
  "version": "1.0.0",
  "type": "object",
  "definitions": {
    "money": {
      "type": "object",
      "properties": {
        "amount": {
          "type": "integer",
          "description": "Amount in smallest currency unit (e.g., cents for USD)",
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
    "timestamp": {
      "type": "string",
      "format": "date-time",
      "description": "ISO 8601 timestamp with timezone"
    },
    "uuid": {
      "type": "string",
      "format": "uuid",
      "description": "UUID identifier"
    },
    "metadata": {
      "type": "object",
      "patternProperties": {
        "^[a-zA-Z_][a-zA-Z0-9_]*$": {
          "oneOf": [
            { "type": "string" },
            { "type": "number" },
            { "type": "boolean" },
            { "type": "null" }
          ]
        }
      },
      "additionalProperties": false,
      "description": "Custom metadata fields for extensibility"
    },
    "tenant": {
      "type": "object",
      "properties": {
        "id": { "$ref": "#/definitions/uuid" },
        "name": { 
          "type": "string",
          "minLength": 1,
          "maxLength": 255
        },
        "created_at": { "$ref": "#/definitions/timestamp" },
        "updated_at": { "$ref": "#/definitions/timestamp" },
        "status": {
          "type": "string",
          "enum": ["active", "suspended", "canceled"]
        },
        "settings": {
          "type": "object",
          "properties": {
            "timezone": {
              "type": "string",
              "pattern": "^[A-Za-z_]+/[A-Za-z_]+$"
            },
            "billing_contact": {
              "type": "object",
              "properties": {
                "email": { "type": "string", "format": "email" },
                "name": { "type": "string" }
              },
              "required": ["email"]
            }
          }
        },
        "metadata": { "$ref": "#/definitions/metadata" }
      },
      "required": ["id", "name", "created_at", "status"],
      "additionalProperties": false
    },
    "customer": {
      "type": "object",
      "properties": {
        "id": { "$ref": "#/definitions/uuid" },
        "tenant_id": { "$ref": "#/definitions/uuid" },
        "external_id": {
          "type": "string",
          "description": "Customer ID from external system (e.g., Stripe customer ID)"
        },
        "email": { "type": "string", "format": "email" },
        "name": { "type": "string" },
        "company": { "type": "string" },
        "created_at": { "$ref": "#/definitions/timestamp" },
        "updated_at": { "$ref": "#/definitions/timestamp" },
        "status": {
          "type": "string",
          "enum": ["active", "delinquent", "suspended", "canceled"]
        },
        "billing_address": {
          "type": "object",
          "properties": {
            "line1": { "type": "string" },
            "line2": { "type": "string" },
            "city": { "type": "string" },
            "state": { "type": "string" },
            "postal_code": { "type": "string" },
            "country": {
              "type": "string",
              "pattern": "^[A-Z]{2}$",
              "description": "ISO 3166-1 alpha-2 country code"
            }
          },
          "required": ["country"]
        },
        "metadata": { "$ref": "#/definitions/metadata" }
      },
      "required": ["id", "tenant_id", "email", "created_at", "status"],
      "additionalProperties": false
    },
    "pricing_tier": {
      "type": "object",
      "properties": {
        "up_to": {
          "oneOf": [
            { "type": "number", "minimum": 0 },
            { "type": "null" }
          ],
          "description": "Upper limit for this tier, null means unlimited"
        },
        "unit_price": { "$ref": "#/definitions/money" },
        "flat_fee": { "$ref": "#/definitions/money" }
      },
      "required": ["unit_price"],
      "additionalProperties": false
    },
    "metered_dimension": {
      "type": "object",
      "properties": {
        "id": {
          "type": "string",
          "pattern": "^[a-z][a-z0-9_]*$",
          "description": "Unique identifier for the metered dimension"
        },
        "display_name": { "type": "string" },
        "description": { "type": "string" },
        "unit": {
          "type": "string",
          "description": "Unit of measurement (e.g., 'requests', 'GB', 'minutes')"
        },
        "aggregation": {
          "type": "string",
          "enum": ["sum", "max", "unique_count", "average"],
          "default": "sum"
        },
        "pricing_model": {
          "type": "string",
          "enum": ["per_unit", "tiered", "graduated"]
        },
        "tiers": {
          "type": "array",
          "items": { "$ref": "#/definitions/pricing_tier" },
          "minItems": 1
        },
        "included_units": {
          "type": "number",
          "minimum": 0,
          "description": "Free units included in base plan"
        }
      },
      "required": ["id", "display_name", "unit", "pricing_model"],
      "additionalProperties": false
    },
    "plan": {
      "type": "object",
      "properties": {
        "id": { "$ref": "#/definitions/uuid" },
        "tenant_id": { "$ref": "#/definitions/uuid" },
        "name": { "type": "string" },
        "description": { "type": "string" },
        "pricing_model": {
          "type": "object",
          "properties": {
            "type": {
              "type": "string",
              "enum": ["seat_based", "usage_based", "hybrid"]
            },
            "seat_price": {
              "$ref": "#/definitions/money",
              "description": "Price per seat for seat-based or hybrid models"
            },
            "minimum_seats": {
              "type": "integer",
              "minimum": 1,
              "description": "Minimum number of seats required"
            },
            "base_fee": {
              "$ref": "#/definitions/money",
              "description": "Fixed monthly/yearly base fee"
            },
            "metered_dimensions": {
              "type": "array",
              "items": { "$ref": "#/definitions/metered_dimension" },
              "description": "Usage-based pricing dimensions"
            }
          },
          "required": ["type"],
          "allOf": [
            {
              "if": {
                "properties": { "type": { "const": "seat_based" } }
              },
              "then": {
                "required": ["seat_price"]
              }
            },
            {
              "if": {
                "properties": { "type": { "const": "usage_based" } }
              },
              "then": {
                "required": ["metered_dimensions"]
              }
            },
            {
              "if": {
                "properties": { "type": { "const": "hybrid" } }
              },
              "then": {
                "anyOf": [
                  { "required": ["seat_price"] },
                  { "required": ["base_fee"] },
                  { "required": ["metered_dimensions"] }
                ]
              }
            }
          ]
        },
        "billing_interval": {
          "type": "string",
          "enum": ["monthly", "yearly", "quarterly"]
        },
        "trial_period_days": {
          "type": "integer",
          "minimum": 0
        },
        "status": {
          "type": "string",
          "enum": ["active", "archived"]
        },
        "created_at": { "$ref": "#/definitions/timestamp" },
        "updated_at": { "$ref": "#/definitions/timestamp" },
        "metadata": { "$ref": "#/definitions/metadata" }
      },
      "required": ["id", "tenant_id", "name", "pricing_model", "billing_interval", "status", "created_at"],
      "additionalProperties": false
    },
    "subscription": {
      "type": "object",
      "properties": {
        "id": { "$ref": "#/definitions/uuid" },
        "customer_id": { "$ref": "#/definitions/uuid" },
        "plan_id": { "$ref": "#/definitions/uuid" },
        "external_id": {
          "type": "string",
          "description": "Subscription ID from external system (e.g., Stripe subscription ID)"
        },
        "status": {
          "type": "string",
          "enum": ["trialing", "active", "past_due", "canceled", "unpaid", "incomplete", "incomplete_expired"]
        },
        "current_period_start": { "$ref": "#/definitions/timestamp" },
        "current_period_end": { "$ref": "#/definitions/timestamp" },
        "trial_start": { "$ref": "#/definitions/timestamp" },
        "trial_end": { "$ref": "#/definitions/timestamp" },
        "canceled_at": { "$ref": "#/definitions/timestamp" },
        "quantity": {
          "type": "integer",
          "minimum": 1,
          "description": "Number of seats for seat-based plans"
        },
        "proration_behavior": {
          "type": "string",
          "enum": ["create_prorations", "none", "always_invoice"],
          "default": "create_prorations"
        },
        "collection_method": {
          "type": "string",
          "enum": ["charge_automatically", "send_invoice"],
          "default": "charge_automatically"
        },
        "created_at": { "$ref": "#/definitions/timestamp" },
        "updated_at": { "$ref": "#/definitions/timestamp" },
        "metadata": { "$ref": "#/definitions/metadata" }
      },
      "required": ["id", "customer_id", "plan_id", "status", "current_period_start", "current_period_end", "created_at"],
      "additionalProperties": false
    },
    "usage_event": {
      "type": "object",
      "properties": {
        "id": { "$ref": "#/definitions/uuid" },
        "customer_id": { "$ref": "#/definitions/uuid" },
        "subscription_id": { "$ref": "#/definitions/uuid" },
        "dimension_id": {
          "type": "string",
          "pattern": "^[a-z][a-z0-9_]*$"
        },
        "event_time": { "$ref": "#/definitions/timestamp" },
        "quantity": {
          "type": "number",
          "minimum": 0
        },
        "unit": { "type": "string" },
        "idempotency_key": {
          "type": "string",
          "description": "Client-provided key to prevent duplicate events"
        },
        "properties": {
          "type": "object",
          "description": "Additional event properties for context"
        },
        "created_at": { "$ref": "#/definitions/timestamp" }
      },
      "required": ["id", "customer_id", "dimension_id", "event_time", "quantity", "unit", "idempotency_key", "created_at"],
      "additionalProperties": false
    },
    "usage_summary": {
      "type": "object",
      "properties": {
        "id": { "$ref": "#/definitions/uuid" },
        "customer_id": { "$ref": "#/definitions/uuid" },
        "subscription_id": { "$ref": "#/definitions/uuid" },
        "dimension_id": {
          "type": "string",
          "pattern": "^[a-z][a-z0-9_]*$"
        },
        "period_start": { "$ref": "#/definitions/timestamp" },
        "period_end": { "$ref": "#/definitions/timestamp" },
        "total_usage": {
          "type": "number",
          "minimum": 0
        },
        "billable_usage": {
          "type": "number",
          "minimum": 0,
          "description": "Usage above included units"
        },
        "included_usage": {
          "type": "number",
          "minimum": 0,
          "description": "Usage covered by included units"
        },
        "unit": { "type": "string" },
        "calculated_cost": { "$ref": "#/definitions/money" },
        "created_at": { "$ref": "#/definitions/timestamp" },
        "updated_at": { "$ref": "#/definitions/timestamp" }
      },
      "required": ["id", "customer_id", "dimension_id", "period_start", "period_end", "total_usage", "billable_usage", "unit", "calculated_cost", "created_at"],
      "additionalProperties": false
    },
    "invoice_line_item": {
      "type": "object",
      "properties": {
        "id": { "$ref": "#/definitions/uuid" },
        "type": {
          "type": "string",
          "enum": ["subscription", "usage", "one_time", "proration", "discount", "tax"]
        },
        "description": { "type": "string" },
        "quantity": {
          "type": "number",
          "minimum": 0
        },
        "unit_amount": { "$ref": "#/definitions/money" },
        "amount": { "$ref": "#/definitions/money" },
        "period_start": { "$ref": "#/definitions/timestamp" },
        "period_end": { "$ref": "#/definitions/timestamp" },
        "subscription_id": { "$ref": "#/definitions/uuid" },
        "dimension_id": {
          "type": "string",
          "pattern": "^[a-z][a-z0-9_]*$"
        },
        "proration": { "type": "boolean", "default": false },
        "metadata": { "$ref": "#/definitions/metadata" }
      },
      "required": ["id", "type", "description", "amount"],
      "additionalProperties": false
    },
    "invoice": {
      "type": "object",
      "properties": {
        "id": { "$ref": "#/definitions/uuid" },
        "customer_id": { "$ref": "#/definitions/uuid" },
        "external_id": {
          "type": "string",
          "description": "Invoice ID from external system (e.g., Stripe invoice ID)"
        },
        "number": {
          "type": "string",
          "description": "Human-readable invoice number"
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
          "type": "integer",
          "minimum": 0,
          "description": "Amount before discounts and tax in smallest currency unit"
        },
        "tax_amount": {
          "type": "integer",
          "minimum": 0,
          "description": "Total tax amount in smallest currency unit"
        },
        "discount_amount": {
          "type": "integer",
          "minimum": 0,
          "description": "Total discount amount in smallest currency unit"
        },
        "total": {
          "type": "integer",
          "minimum": 0,
          "description": "Final amount due in smallest currency unit"
        },
        "amount_paid": {
          "type": "integer",
          "minimum": 0,
          "description": "Amount paid in smallest currency unit"
        },
        "amount_due": {
          "type": "integer",
          "minimum": 0,
          "description": "Amount still due in smallest currency unit"
        },
        "line_items": {
          "type": "array",
          "items": { "$ref": "#/definitions/invoice_line_item" }
        },
        "period_start": { "$ref": "#/definitions/timestamp" },
        "period_end": { "$ref": "#/definitions/timestamp" },
        "issue_date": { "$ref": "#/definitions/timestamp" },
        "due_date": { "$ref": "#/definitions/timestamp" },
        "paid_at": { "$ref": "#/definitions/timestamp" },
        "voided_at": { "$ref": "#/definitions/timestamp" },
        "collection_method": {
          "type": "string",
          "enum": ["charge_automatically", "send_invoice"]
        },
        "created_at": { "$ref": "#/definitions/timestamp" },
        "updated_at": { "$ref": "#/definitions/timestamp" },
        "metadata": { "$ref": "#/definitions/metadata" }
      },
      "required": ["id", "customer_id", "status", "currency", "subtotal", "total", "amount_due", "line_items", "issue_date", "created_at"],
      "additionalProperties": false
    },
    "payment": {
      "type": "object",
      "properties": {
        "id": { "$ref": "#/definitions/uuid" },
        "invoice_id": { "$ref": "#/definitions/uuid" },
        "external_id": {
          "type": "string",
          "description": "Payment ID from external system (e.g., Stripe payment intent ID)"
        },
        "amount": { "$ref": "#/definitions/money" },
        "status": {
          "type": "string",
          "enum": ["pending", "succeeded", "failed", "canceled", "refunded"]
        },
        "payment_method": {
          "type": "object",
          "properties": {
            "type": {
              "type": "string",
              "enum": ["card", "bank_transfer", "ach", "wire", "check"]
            },
            "last_four": { "type": "string" },
            "brand": { "type": "string" }
          },
          "required": ["type"]
        },
        "failure_reason": { "type": "string" },
        "processed_at": { "$ref": "#/definitions/timestamp" },
        "created_at": { "$ref": "#/definitions/timestamp" },
        "metadata": { "$ref": "#/definitions/metadata" }
      },
      "required": ["id", "invoice_id", "amount", "status", "created_at"],
      "additionalProperties": false
    },
    "credit": {
      "type": "object",
      "properties": {
        "id": { "$ref": "#/definitions/uuid" },
        "customer_id": { "$ref": "#/definitions/uuid" },
        "amount": { "$ref": "#/definitions/money" },
        "remaining_amount": { "$ref": "#/definitions/money" },
        "reason": {
          "type": "string",
          "enum": ["refund", "goodwill", "promotional", "adjustment"]
        },
        "description": { "type": "string" },
        "expires_at": { "$ref": "#/definitions/timestamp" },
        "created_at": { "$ref": "#/definitions/timestamp" },
        "metadata": { "$ref": "#/definitions/metadata" }
      },
      "required": ["id", "customer_id", "amount", "remaining_amount", "reason", "created_at"],
      "additionalProperties": false
    }
  },
  "properties": {
    "tenants": {
      "type": "array",
      "items": { "$ref": "#/definitions/tenant" }
    },
    "customers": {
      "type": "array", 
      "items": { "$ref": "#/definitions/customer" }
    },
    "plans": {
      "type": "array",
      "items": { "$ref": "#/definitions/plan" }
    },
    "subscriptions": {
      "type": "array",
      "items": { "$ref": "#/definitions/subscription" }
    },
    "usage_events": {
      "type": "array",
      "items": { "$ref": "#/definitions/usage_event" }
    },
    "usage_summaries": {
      "type": "array",
      "items": { "$ref": "#/definitions/usage_summary" }
    },
    "invoices": {
      "type": "array",
      "items": { "$ref": "#/definitions/invoice" }
    },
    "payments": {
      "type": "array",
      "items": { "$ref": "#/definitions/payment" }
    },
    "credits": {
      "type": "array",
      "items": { "$ref": "#/definitions/credits" }
    }
  },
  "additionalProperties": false
}
```

This comprehensive JSON schema for a multi-tenant SaaS billing system incorporates real-world patterns from 
Stripe's billing infrastructure, with primary tables being subscriptions and invoices, and support for billing meter objects that specify how to aggregate meter events over billing periods
. 

The schema supports both usage-based and seat-based pricing models through a flexible hybrid approach. 
Invoice objects contain line items that show subscriptions and invoice items applied to the invoice, with each line having an amount attribute that represents the actual contribution to the invoice total
. 

The design follows 
invoice payment status patterns with states like "open", "paid", or "canceled"
 and incorporates 
usage event ingestion patterns with idempotency keys to prevent double-charging even if the same event is sent multiple times
.

Key extensibility features include dynamic metered dimensions that can be added without schema changes, comprehensive metadata support throughout all entities, and a versioned schema approach. The schema reflects real billing system patterns with proper money handling (amounts in cents with currency codes), 
subscription status enums matching Stripe's model (incomplete, active, past_due, canceled, unpaid)
, and detailed invoice line items for transparency.