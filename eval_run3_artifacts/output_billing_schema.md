# Harness Output: billing_schema

**Score:** 76.6% (29.12/38)
**Iterations:** 4
**Best Iteration:** 2 (75.9%)

---

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "Multi-Tenant SaaS Billing System Schema",
  "version": "1.0.0",
  "type": "object",
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
          "examples": ["USD", "EUR", "GBP"]
        }
      },
      "required": ["amount", "currency"],
      "additionalProperties": false
    },
    "timestamp": {
      "type": "string",
      "format": "date-time"
    },
    "uuid": {
      "type": "string",
      "pattern": "^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
    },
    "billing_interval": {
      "type": "string",
      "enum": ["monthly", "quarterly", "yearly"]
    },
    "base_entity": {
      "allOf": [
        {
          "type": "object",
          "properties": {
            "created_at": {
              "$ref": "#/definitions/timestamp"
            },
            "updated_at": {
              "$ref": "#/definitions/timestamp"
            },
            "metadata": {
              "$ref": "#/definitions/extensible_metadata"
            }
          },
          "required": ["created_at"]
        }
      ]
    },
    "extensible_metadata": {
      "type": "object",
      "properties": {
        "custom_fields": {
          "type": "array",
          "items": {
            "type": "object",
            "properties": {
              "field_name": {
                "type": "string",
                "pattern": "^[a-zA-Z][a-zA-Z0-9_]*$"
              },
              "field_type": {
                "type": "string",
                "enum": ["string", "number", "boolean", "date", "array", "object"]
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
              }
            },
            "required": ["field_name", "field_type", "value"]
          }
        },
        "webhook_configuration": {
          "type": "object",
          "properties": {
            "endpoints": {
              "type": "array",
              "items": {
                "type": "object",
                "properties": {
                  "url": {"type": "string", "format": "uri"},
                  "events": {
                    "type": "array",
                    "items": {"type": "string"}
                  },
                  "authentication": {
                    "type": "object",
                    "properties": {
                      "type": {"type": "string", "enum": ["bearer", "api_key", "hmac"]},
                      "secret_key": {"type": "string"}
                    }
                  }
                }
              }
            }
          }
        },
        "integration_mappings": {
          "type": "object",
          "patternProperties": {
            "^[a-z][a-z0-9_]*$": {
              "type": "object",
              "properties": {
                "external_system": {"type": "string"},
                "field_mappings": {
                  "type": "object",
                  "patternProperties": {
                    "^[a-zA-Z][a-zA-Z0-9_]*$": {"type": "string"}
                  }
                }
              }
            }
          }
        }
      },
      "additionalProperties": true
    },
    "pricing_tier": {
      "type": "object",
      "properties": {
        "from": {
          "type": "number",
          "minimum": 0
        },
        "to": {
          "type": ["number", "null"],
          "minimum": 0
        },
        "price_per_unit": {
          "$ref": "#/definitions/money"
        }
      },
      "required": ["from", "price_per_unit"],
      "additionalProperties": false
    },
    "metered_dimension": {
      "type": "object",
      "properties": {
        "id": {
          "type": "string",
          "pattern": "^[a-z][a-z0-9_]*$"
        },
        "name": {
          "type": "string",
          "minLength": 1
        },
        "unit": {
          "type": "string",
          "minLength": 1,
          "examples": ["requests", "GB", "minutes", "users"]
        },
        "pricing_type": {
          "type": "string",
          "enum": ["flat", "tiered", "volume"]
        },
        "tiers": {
          "type": "array",
          "items": {
            "$ref": "#/definitions/pricing_tier"
          },
          "minItems": 1
        },
        "aggregation": {
          "type": "string",
          "enum": ["sum", "max", "average"],
          "default": "sum"
        },
        "reset_period": {
          "$ref": "#/definitions/billing_interval"
        },
        "custom_properties": {
          "type": "object",
          "patternProperties": {
            "^[a-zA-Z][a-zA-Z0-9_]*$": {
              "oneOf": [
                {"type": "string"},
                {"type": "number"},
                {"type": "boolean"},
                {"type": "object"},
                {"type": "array"}
              ]
            }
          },
          "additionalProperties": false
        },
        "validation_rules": {
          "type": "array",
          "items": {
            "type": "object",
            "properties": {
              "rule_type": {
                "type": "string",
                "enum": ["min_value", "max_value", "allowed_values", "custom_expression"]
              },
              "value": {},
              "error_message": {"type": "string"}
            }
          }
        },
        "transformation_functions": {
          "type": "array",
          "items": {
            "type": "object",
            "properties": {
              "function_name": {"type": "string"},
              "parameters": {"type": "object"},
              "execution_order": {"type": "integer", "minimum": 1}
            }
          }
        },
        "metadata": {
          "type": "object",
          "additionalProperties": true
        }
      },
      "required": ["id", "name", "unit", "pricing_type", "tiers"],
      "additionalProperties": false
    },
    "versioning": {
      "type": "object",
      "properties": {
        "schema_version": {
          "type": "string",
          "const": "1.0.0"
        },
        "migration_path": {
          "type": "object",
          "properties": {
            "supported_versions": {
              "type": "array",
              "items": {"type": "string"}
            },
            "transformation_rules": {
              "type": "array",
              "items": {
                "type": "object",
                "properties": {
                  "from_version": {"type": "string"},
                  "to_version": {"type": "string"},
                  "field_mappings": {
                    "type": "object",
                    "patternProperties": {
                      ".*": {"type": "string"}
                    }
                  },
                  "data_transformations": {
                    "type": "array",
                    "items": {"type": "string"}
                  }
                }
              }
            }
          }
        },
        "backward_compatibility": {
          "type": "object",
          "properties": {
            "minimum_supported_version": {"type": "string"},
            "deprecated_fields": {
              "type": "array",
              "items": {
                "type": "object",
                "properties": {
                  "field_path": {"type": "string"},
                  "deprecated_in": {"type": "string"},
                  "removal_in": {"type": "string"},
                  "replacement": {"type": "string"}
                }
              }
            }
          }
        },
        "deprecation_warnings": {
          "type": "array",
          "items": {
            "type": "object",
            "properties": {
              "field_path": {"type": "string"},
              "message": {"type": "string"},
              "severity": {"type": "string", "enum": ["warning", "error"]},
              "removal_date": {"$ref": "#/definitions/timestamp"}
            }
          }
        }
      }
    }
  },
  "properties": {
    "schema_version": {
      "type": "string",
      "const": "1.0.0"
    },
    "versioning_metadata": {
      "$ref": "#/definitions/versioning"
    },
    "tenants": {
      "type": "array",
      "items": {
        "allOf": [
          {"$ref": "#/definitions/base_entity"},
          {
            "type": "object",
            "properties": {
              "tenant_id": {
                "$ref": "#/definitions/uuid"
              },
              "name": {
                "type": "string",
                "minLength": 1
              },
              "billing_email": {
                "type": "string",
                "format": "email"
              },
              "billing_address": {
                "type": "object",
                "properties": {
                  "line1": {"type": "string"},
                  "line2": {"type": "string"},
                  "city": {"type": "string"},
                  "state": {"type": "string"},
                  "postal_code": {"type": "string"},
                  "country": {"type": "string", "pattern": "^[A-Z]{2}$"}
                },
                "required": ["line1", "city", "country"],
                "additionalProperties": false
              },
              "tax_id": {
                "type": "string"
              },
              "preferred_currency": {
                "type": "string",
                "pattern": "^[A-Z]{3}$"
              }
            },
            "required": ["tenant_id", "name", "billing_email", "preferred_currency"],
            "additionalProperties": false
          }
        ]
      }
    },
    "plans": {
      "type": "array",
      "items": {
        "allOf": [
          {"$ref": "#/definitions/base_entity"},
          {
            "type": "object",
            "properties": {
              "plan_id": {
                "$ref": "#/definitions/uuid"
              },
              "name": {
                "type": "string",
                "minLength": 1
              },
              "description": {
                "type": "string"
              },
              "pricing_model": {
                "oneOf": [
                  {
                    "type": "object",
                    "properties": {
                      "type": {"const": "seat_based"},
                      "seat_price": {"$ref": "#/definitions/money"},
                      "minimum_seats": {"type": "integer", "minimum": 1, "default": 1},
                      "maximum_seats": {"type": ["integer", "null"], "minimum": 1}
                    },
                    "required": ["type", "seat_price"],
                    "additionalProperties": false
                  },
                  {
                    "type": "object",
                    "properties": {
                      "type": {"const": "usage_based"},
                      "metered_dimensions": {
                        "type": "array",
                        "items": {"$ref": "#/definitions/metered_dimension"},
                        "minItems": 1
                      }
                    },
                    "required": ["type", "metered_dimensions"],
                    "additionalProperties": false
                  },
                  {
                    "type": "object",
                    "properties": {
                      "type": {"const": "hybrid"},
                      "seat_price": {"$ref": "#/definitions/money"},
                      "minimum_seats": {"type": "integer", "minimum": 1, "default": 1},
                      "maximum_seats": {"type": ["integer", "null"], "minimum": 1},
                      "metered_dimensions": {
                        "type": "array",
                        "items": {"$ref": "#/definitions/metered_dimension"},
                        "minItems": 1
                      },
                      "included_quotas": {
                        "type": "object",
                        "patternProperties": {
                          "^[a-z][a-z0-9_]*$": {
                            "type": "number",
                            "minimum": 0
                          }
                        },
                        "additionalProperties": false
                      }
                    },
                    "required": ["type", "seat_price", "metered_dimensions"],
                    "additionalProperties": false
                  }
                ]
              },
              "billing_interval": {
                "$ref": "#/definitions/billing_interval"
              },
              "trial_period_days": {
                "type": "integer",
                "minimum": 0,
                "default": 0
              },
              "active": {
                "type": "boolean",
                "default": true
              }
            },
            "required": ["plan_id", "name", "pricing_model", "billing_interval"],
            "additionalProperties": false
          }
        ]
      }
    },
    "subscriptions": {
      "type": "array",
      "items": {
        "allOf": [
          {"$ref": "#/definitions/base_entity"},
          {
            "type": "object",
            "properties": {
              "subscription_id": {
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
                "enum": ["trial", "active", "past_due", "canceled", "paused"]
              },
              "current_period_start": {
                "$ref": "#/definitions/timestamp"
              },
              "current_period_end": {
                "$ref": "#/definitions/timestamp"
              },
              "trial_end": {
                "type": ["string", "null"],
                "format": "date-time"
              },
              "seat_count": {
                "type": "integer",
                "minimum": 1
              },
              "proration_behavior": {
                "type": "string",
                "enum": ["immediate", "next_cycle", "none"],
                "default": "immediate"
              },
              "discount": {
                "type": "object",
                "properties": {
                  "type": {
                    "type": "string",
                    "enum": ["percentage", "fixed_amount"]
                  },
                  "value": {
                    "type": "number",
                    "minimum": 0
                  },
                  "currency": {
                    "type": "string",
                    "pattern": "^[A-Z]{3}$"
                  },
                  "valid_until": {
                    "$ref": "#/definitions/timestamp"
                  }
                },
                "required": ["type", "value"],
                "additionalProperties": false,
                "if": {
                  "properties": {
                    "type": {"const": "fixed_amount"}
                  }
                },
                "then": {
                  "required": ["currency"]
                }
              },
              "canceled_at": {
                "type": ["string", "null"],
                "format": "date-time"
              }
            },
            "required": ["subscription_id", "tenant_id", "plan_id", "status", "current_period_start", "current_period_end"],
            "additionalProperties": false
          }
        ]
      }
    },
    "usage_records": {
      "type": "array",
      "items": {
        "allOf": [
          {"$ref": "#/definitions/base_entity"},
          {
            "type": "object",
            "properties": {
              "record_id": {
                "$ref": "#/definitions/uuid"
              },
              "subscription_id": {
                "$ref": "#/definitions/uuid"
              },
              "dimension_id": {
                "type": "string",
                "pattern": "^[a-z][a-z0-9_]*$"
              },
              "quantity": {
                "type": "number",
                "minimum": 0
              },
              "timestamp": {
                "$ref": "#/definitions/timestamp"
              },
              "idempotency_key": {
                "type": "string",
                "minLength": 1
              }
            },
            "required": ["record_id", "subscription_id", "dimension_id", "quantity", "timestamp"],
            "additionalProperties": false
          }
        ]
      }
    },
    "invoices": {
      "type": "array",
      "items": {
        "allOf": [
          {"$ref": "#/definitions/base_entity"},
          {
            "type": "object",
            "properties": {
              "invoice_id": {
                "$ref": "#/definitions/uuid"
              },
              "tenant_id": {
                "$ref": "#/definitions/uuid"
              },
              "subscription_id": {
                "$ref": "#/definitions/uuid"
              },
              "invoice_number": {
                "type": "string",
                "pattern": "^INV-[0-9]{4}-[0-9]+$"
              },
              "status": {
                "type": "string",
                "enum": ["draft", "open", "paid", "void", "uncollectible"]
              },
              "currency": {
                "type": "string",
                "pattern": "^[A-Z]{3}$"
              },
              "period_start": {
                "$ref": "#/definitions/timestamp"
              },
              "period_end": {
                "$ref": "#/definitions/timestamp"
              },
              "line_items": {
                "type": "array",
                "items": {
                  "type": "object",
                  "properties": {
                    "line_item_id": {
                      "$ref": "#/definitions/uuid"
                    },
                    "type": {
                      "type": "string",
                      "enum": ["subscription", "usage", "one_time", "proration", "discount"]
                    },
                    "description": {
                      "type": "string",
                      "minLength": 1
                    },
                    "quantity": {
                      "type": "number",
                      "minimum": 0
                    },
                    "unit_amount": {
                      "$ref": "#/definitions/money"
                    },
                    "amount": {
                      "$ref": "#/definitions/money"
                    },
                    "dimension_id": {
                      "type": "string",
                      "pattern": "^[a-z][a-z0-9_]*$"
                    },
                    "proration_details": {
                      "type": "object",
                      "properties": {
                        "previous_quantity": {"type": "number"},
                        "new_quantity": {"type": "number"},
                        "proration_date": {"$ref": "#/definitions/timestamp"},
                        "days_in_period": {"type": "integer", "minimum": 1},
                        "days_used": {"type": "integer", "minimum": 0}
                      },
                      "additionalProperties": false
                    },
                    "metadata": {
                      "type": "object",
                      "additionalProperties": true
                    }
                  },
                  "required": ["line_item_id", "type", "description", "quantity", "unit_amount", "amount"],
                  "additionalProperties": false
                },
                "minItems": 1
              },
              "subtotal": {
                "$ref": "#/definitions/money"
              },
              "tax_amount": {
                "$ref": "#/definitions/money"
              },
              "discount_amount": {
                "$ref": "#/definitions/money"
              },
              "total": {
                "$ref": "#/definitions/money"
              },
              "amount_paid": {
                "$ref": "#/definitions/money"
              },
              "amount_due": {
                "$ref": "#/definitions/money"
              },
              "due_date": {
                "$ref": "#/definitions/timestamp"
              },
              "paid_at": {
                "type": ["string", "null"],
                "format": "date-time"
              },
              "voided_at": {
                "type": ["string", "null"],
                "format": "date-time"
              }
            },
            "required": ["invoice_id", "tenant_id", "subscription_id", "invoice_number", "status", "currency", "period_start", "period_end", "line_items", "subtotal", "total", "amount_due", "due_date"],
            "additionalProperties": false
          }
        ]
      }
    },
    "payments": {
      "type": "array",
      "items": {
        "allOf": [
          {"$ref": "#/definitions/base_entity"},
          {
            "type": "object",
            "properties": {
              "payment_id": {
                "$ref": "#/definitions/uuid"
              },
              "invoice_id": {
                "$ref": "#/definitions/uuid"
              },
              "tenant_id": {
                "$ref": "#/definitions/uuid"
              },
              "amount": {
                "$ref": "#/definitions/money"
              },
              "status": {
                "type": "string",
                "enum": ["pending", "succeeded", "failed", "canceled", "refunded"]
              },
              "payment_method": {
                "type": "string",
                "enum": ["credit_card", "bank_transfer", "check", "other"]
              },
              "gateway": {
                "type": "string",
                "examples": ["stripe", "square", "braintree"]
              },
              "gateway_transaction_id": {
                "type": "string"
              },
              "processed_at": {
                "type": ["string", "null"],
                "format": "date-time"
              },
              "failure_reason": {
                "type": "string"
              }
            },
            "required": ["payment_id", "invoice_id", "tenant_id", "amount", "status", "payment_method"],
            "additionalProperties": false
          }
        ]
      }
    },
    "billing_adjustments": {
      "type": "array",
      "items": {
        "allOf": [
          {"$ref": "#/definitions/base_entity"},
          {
            "type": "object",
            "properties": {
              "adjustment_id": {
                "$ref": "#/definitions/uuid"
              },
              "tenant_id": {
                "$ref": "#/definitions/uuid"
              },
              "invoice_id": {
                "$ref": "#/definitions/uuid"
              },
              "type": {
                "type": "string",
                "enum": ["credit", "debit", "refund", "write_off", "dispute_reversal"]
              },
              "reason": {
                "type": "string",
                "enum": ["billing_error", "customer_service", "dispute", "goodwill", "promotional", "technical_issue"]
              },
              "amount": {
                "$ref": "#/definitions/money"
              },
              "description": {
                "type": "string",
                "minLength": 1
              },
              "applied_at": {
                "$ref": "#/definitions/timestamp"
              },
              "approved_by": {
                "type": "string"
              },
              "reference_transaction_id": {
                "type": "string"
              }
            },
            "required": ["adjustment_id", "tenant_id", "type", "reason", "amount", "description", "applied_at"],
            "additionalProperties": false
          }
        ]
      }
    },
    "dunning_management": {
      "type": "array",
      "items": {
        "allOf": [
          {"$ref": "#/definitions/base_entity"},
          {
            "type": "object",
            "properties": {
              "dunning_id": {
                "$ref": "#/definitions/uuid"
              },
              "tenant_id": {
                "$ref": "#/definitions/uuid"
              },
              "subscription_id": {
                "$ref": "#/definitions/uuid"
              },
              "invoice_id": {
                "$ref": "#/definitions/uuid"
              },
              "status": {
                "type": "string",
                "enum": ["initiated", "in_progress", "paused", "resolved", "failed", "expired"]
              },
              "current_step": {
                "type": "integer",
                "minimum": 1
              },
              "total_steps": {
                "type": "integer",
                "minimum": 1
              },
              "dunning_steps": {
                "type": "array",
                "items": {
                  "type": "object",
                  "properties": {
                    "step_number": {"type": "integer", "minimum": 1},
                    "action": {
                      "type": "string",
                      "enum": ["email_reminder", "suspend_service", "retry_payment", "escalate_to_collection"]
                    },
                    "delay_days": {"type": "integer", "minimum": 0},
                    "executed_at": {"$ref": "#/definitions/timestamp"},
                    "status": {
                      "type": "string",
                      "enum": ["pending", "executed", "skipped", "failed"]
                    }
                  }
                }
              },
              "retry_attempts": {
                "type": "integer",
                "minimum": 0,
                "default": 0
              },
              "max_retry_attempts": {
                "type": "integer",
                "minimum": 1,
                "default": 3
              },
              "next_retry_at": {
                "$ref": "#/definitions/timestamp"
              }
            },
            "required": ["dunning_id", "tenant_id", "subscription_id", "invoice_id", "status", "current_step", "total_steps", "dunning_steps"],
            "additionalProperties": false
          }
        ]
      }
    },
    "revenue_recognition": {
      "type": "array",
      "items": {
        "allOf": [
          {"$ref": "#/definitions/base_entity"},
          {
            "type": "object",
            "properties": {
              "recognition_id": {
                "$ref": "#/definitions/uuid"
              },
              "tenant_id": {
                "$ref": "#/definitions/uuid"
              },
              "subscription_id": {
                "$ref": "#/definitions/uuid"
              },
              "invoice_id": {
                "$ref": "#/definitions/uuid"
              },
              "recognition_method": {
                "type": "string",
                "enum": ["straight_line", "usage_based", "milestone_based", "percentage_completion"]
              },
              "total_contract_value": {
                "$ref": "#/definitions/money"
              },
              "recognized_to_date": {
                "$ref": "#/definitions/money"
              },
              "remaining_to_recognize": {
                "$ref": "#/definitions/money"
              },
              "recognition_schedule": {
                "type": "array",
                "items": {
                  "type": "object",
                  "properties": {
                    "period_start": {"$ref": "#/definitions/timestamp"},
                    "period_end": {"$ref": "#/definitions/timestamp"},
                    "amount": {"$ref": "#/definitions/money"},
                    "recognized": {"type": "boolean", "default": false},
                    "recognition_date": {"$ref": "#/definitions/timestamp"}
                  }
                }
              },
              "accounting_standards": {
                "type": "string",
                "enum": ["ASC_606", "IFRS_15", "GAAP", "OTHER"]
              },
              "contract_start_date": {
                "$ref": "#/definitions/timestamp"
              },
              "contract_end_date": {
                "$ref": "#/definitions/timestamp"
              },
              "performance_obligations": {
                "type": "array",
                "items": {
                  "type": "object",
                  "properties": {
                    "obligation_id": {"$ref": "#/definitions/uuid"},
                    "description": {"type": "string"},
                    "allocated_amount": {"$ref": "#/definitions/money"},
                    "satisfaction_method": {
                      "type": "string",
                      "enum": ["over_time", "point_in_time"]
                    },
                    "completion_percentage": {"type": "number", "minimum": 0, "maximum": 100}
                  }
                }
              }
            },
            "required": ["recognition_id", "tenant_id", "subscription_id", "invoice_id", "recognition_method", "total_contract_value", "accounting_standards", "contract_start_date", "contract_end_date"],
            "additionalProperties": false
          }
        ]
      }
    }
  },
  "required": ["schema_version", "tenants", "plans", "subscriptions", "invoices"],
  "additionalProperties": false
}
```