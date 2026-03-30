# Billing Schema — Final Harness Output

**Task:** Design a JSON schema for a multi-tenant SaaS billing system supporting usage-based and seat-based pricing
**Harness Score:** 30.5 / 38 (80.3%)
**Baseline Score:** 26.4 / 38 (69.5%)
**Lift:** +10.7pp
**Iterations:** 5

---

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://example.com/schemas/billing-system.json",
  "title": "Multi-Tenant SaaS Billing System Schema",
  "version": "1.0.0",
  "api_version": "2024-01-15",
  "schema_compatibility": "backward_compatible",
  "deprecated_fields": [],
  "breaking_changes": [],
  "sunset_date": null,
  "migration_guide_url": "https://example.com/docs/schema-migrations/v1.0.0",
  "type": "object",
  "$defs": {
    "money": {
      "type": "object",
      "properties": {
        "amount": {
          "type": "integer",
          "minimum": 0,
          "description": "Amount in smallest currency unit (e.g., cents)"
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
    "address": {
      "type": "object",
      "properties": {
        "line1": {"type": "string", "minLength": 1, "maxLength": 200},
        "line2": {"type": "string", "minLength": 0, "maxLength": 200},
        "city": {"type": "string", "minLength": 1, "maxLength": 100},
        "state": {"type": "string", "minLength": 0, "maxLength": 100},
        "postal_code": {"type": "string", "minLength": 1, "maxLength": 20},
        "country": {"type": "string", "pattern": "^[A-Z]{2}$"}
      },
      "required": ["line1", "city", "country"],
      "additionalProperties": false
    },
    "contact_info": {
      "type": "object",
      "properties": {
        "name": {"type": "string", "minLength": 1, "maxLength": 200},
        "email": {"type": "string", "format": "email", "maxLength": 254},
        "phone": {"type": "string", "minLength": 0, "maxLength": 20, "pattern": "^[+]?[0-9\\s\\-\\(\\)\\.]*$"}
      },
      "required": ["name", "email"],
      "additionalProperties": false
    },
    "audit_fields": {
      "type": "object",
      "properties": {
        "created_at": {
          "type": "string",
          "format": "date-time"
        },
        "updated_at": {
          "type": "string",
          "format": "date-time"
        },
        "created_by": {
          "type": "string",
          "minLength": 1,
          "maxLength": 100
        },
        "api_version": {
          "type": "string",
          "minLength": 1,
          "maxLength": 20
        }
      },
      "required": ["created_at", "api_version"],
      "additionalProperties": false
    },
    "pagination_metadata": {
      "type": "object",
      "properties": {
        "total_count": {"type": "integer", "minimum": 0},
        "page_size": {"type": "integer", "minimum": 1, "maximum": 1000},
        "current_page": {"type": "integer", "minimum": 1},
        "has_more": {"type": "boolean"}
      },
      "required": ["total_count", "page_size", "current_page", "has_more"],
      "additionalProperties": false
    },
    "custom_fields": {
      "type": "object",
      "properties": {
        "field_definitions": {
          "type": "object",
          "additionalProperties": {
            "type": "object",
            "properties": {
              "type": {"type": "string", "enum": ["string", "number", "boolean", "date", "enum"]},
              "validation_rules": {"type": "object", "additionalProperties": true},
              "display_name": {"type": "string", "minLength": 1, "maxLength": 100},
              "required": {"type": "boolean", "default": false}
            },
            "required": ["type", "display_name"],
            "additionalProperties": false
          }
        },
        "field_values": {
          "type": "object",
          "additionalProperties": true
        }
      },
      "additionalProperties": false
    },
    "entity_id": {
      "type": "string",
      "pattern": "^[a-zA-Z0-9_-]+$",
      "minLength": 1,
      "maxLength": 50
    },
    "entity_reference": {
      "type": "object",
      "properties": {
        "id": {"$ref": "#/$defs/entity_id"},
        "name": {"type": "string", "minLength": 1, "maxLength": 200}
      },
      "required": ["id", "name"],
      "additionalProperties": false
    },
    "status_with_reason": {
      "type": "object",
      "properties": {
        "status": {"type": "string"},
        "status_reason": {"type": "string", "minLength": 0, "maxLength": 500},
        "status_changed_at": {"type": "string", "format": "date-time"}
      },
      "required": ["status"],
      "additionalProperties": false
    },
    "billing_interval": {
      "type": "string",
      "enum": ["monthly", "quarterly", "yearly"]
    },
    "pricing_model_type": {
      "type": "string",
      "enum": ["seat_based", "usage_based", "hybrid"]
    },
    "subscription_status": {
      "type": "string",
      "enum": ["trial", "active", "past_due", "canceled", "paused"]
    },
    "invoice_status": {
      "type": "string",
      "enum": ["draft", "open", "paid", "void", "uncollectible"]
    },
    "webhook_endpoint": {
      "type": "object",
      "properties": {
        "url": {"type": "string", "format": "uri", "maxLength": 500},
        "events": {"type": "array", "items": {"type": "string", "minLength": 1, "maxLength": 100}, "minItems": 1},
        "secret": {"type": "string", "minLength": 1, "maxLength": 256}
      },
      "required": ["url", "events"],
      "additionalProperties": false
    },
    "tier": {
      "type": "object",
      "properties": {
        "min_quantity": {
          "type": "integer",
          "minimum": 0
        },
        "max_quantity": {
          "type": ["integer", "null"],
          "minimum": 0
        },
        "unit_price": {
          "$ref": "#/$defs/money"
        },
        "flat_fee": {
          "$ref": "#/$defs/money"
        }
      },
      "required": ["min_quantity", "unit_price"],
      "additionalProperties": false
    },
    "metered_dimension": {
      "type": "object",
      "properties": {
        "id": {
          "type": "string",
          "pattern": "^[a-z_][a-z0-9_]*$",
          "minLength": 1,
          "maxLength": 50
        },
        "name": {
          "type": "string",
          "minLength": 1,
          "maxLength": 200
        },
        "unit": {
          "type": "string",
          "minLength": 1,
          "maxLength": 50
        },
        "tiers": {
          "type": "array",
          "items": {
            "$ref": "#/$defs/tier"
          },
          "minItems": 1
        },
        "included_quantity": {
          "type": "integer",
          "minimum": 0,
          "default": 0
        },
        "aggregation_method": {
          "type": "string",
          "pattern": "^[a-z_]+$",
          "default": "sum"
        },
        "reset_frequency": {
          "type": "string",
          "pattern": "^[a-z_]+$",
          "default": "billing_cycle"
        },
        "dimension_config": {
          "type": "object",
          "additionalProperties": true
        },
        "metadata": {
          "type": "object",
          "additionalProperties": true
        }
      },
      "required": ["id", "name", "unit", "tiers"],
      "additionalProperties": false
    }
  },
  "properties": {
    "tenants": {
      "type": "object",
      "patternProperties": {
        "^[a-zA-Z0-9_-]+$": {
          "type": "object",
          "allOf": [
            {"$ref": "#/$defs/audit_fields"}
          ],
          "properties": {
            "id": {"$ref": "#/$defs/entity_id"},
            "name": {
              "type": "string",
              "minLength": 1,
              "maxLength": 200
            },
            "billing_address": {
              "$ref": "#/$defs/address"
            },
            "contact_info": {
              "$ref": "#/$defs/contact_info"
            },
            "tax_id": {
              "type": "string",
              "minLength": 0,
              "maxLength": 50
            },
            "metadata": {
              "type": "object",
              "additionalProperties": true
            },
            "custom_fields": {
              "$ref": "#/$defs/custom_fields"
            },
            "webhook_endpoints": {
              "type": "array",
              "items": {
                "$ref": "#/$defs/webhook_endpoint"
              }
            }
          },
          "required": ["id", "name", "contact_info"],
          "additionalProperties": false
        }
      }
    },
    "customers": {
      "type": "object",
      "patternProperties": {
        "^[a-zA-Z0-9_-]+$": {
          "type": "object",
          "allOf": [
            {"$ref": "#/$defs/audit_fields"}
          ],
          "properties": {
            "id": {"$ref": "#/$defs/entity_id"},
            "tenant_id": {"$ref": "#/$defs/entity_id"},
            "name": {
              "type": "string",
              "minLength": 1,
              "maxLength": 200
            },
            "email": {
              "type": "string",
              "format": "email",
              "maxLength": 254
            },
            "billing_address": {
              "$ref": "#/$defs/address"
            },
            "payment_method_id": {
              "type": "string",
              "minLength": 1,
              "maxLength": 100
            },
            "tax_exempt": {
              "type": "boolean",
              "default": false
            },
            "metadata": {
              "type": "object",
              "additionalProperties": true
            },
            "custom_fields": {
              "$ref": "#/$defs/custom_fields"
            },
            "webhook_endpoints": {
              "type": "array",
              "items": {
                "$ref": "#/$defs/webhook_endpoint"
              }
            }
          },
          "required": ["id", "tenant_id", "name", "email"],
          "additionalProperties": false
        }
      }
    },
    "plans": {
      "type": "object",
      "patternProperties": {
        "^[a-zA-Z0-9_-]+$": {
          "type": "object",
          "allOf": [
            {"$ref": "#/$defs/audit_fields"}
          ],
          "properties": {
            "id": {"$ref": "#/$defs/entity_id"},
            "tenant_id": {"$ref": "#/$defs/entity_id"},
            "name": {
              "type": "string",
              "minLength": 1,
              "maxLength": 200
            },
            "description": {
              "type": "string",
              "minLength": 0,
              "maxLength": 1000
            },
            "pricing_model": {
              "type": "object",
              "properties": {
                "type": {
                  "$ref": "#/$defs/pricing_model_type"
                },
                "seat_price": {
                  "$ref": "#/$defs/money"
                },
                "minimum_seats": {
                  "type": "integer",
                  "minimum": 1,
                  "default": 1
                },
                "maximum_seats": {
                  "type": ["integer", "null"],
                  "minimum": 1
                },
                "metered_dimensions": {
                  "type": "array",
                  "items": {
                    "$ref": "#/$defs/metered_dimension"
                  }
                }
              },
              "required": ["type"],
              "allOf": [
                {
                  "if": {
                    "properties": {"type": {"const": "seat_based"}}
                  },
                  "then": {
                    "required": ["seat_price"],
                    "not": {
                      "required": ["metered_dimensions"]
                    }
                  }
                },
                {
                  "if": {
                    "properties": {"type": {"const": "usage_based"}}
                  },
                  "then": {
                    "required": ["metered_dimensions"],
                    "not": {
                      "anyOf": [
                        {"required": ["seat_price"]},
                        {"required": ["minimum_seats"]},
                        {"required": ["maximum_seats"]}
                      ]
                    },
                    "properties": {
                      "metered_dimensions": {
                        "minItems": 1
                      }
                    }
                  }
                },
                {
                  "if": {
                    "properties": {"type": {"const": "hybrid"}}
                  },
                  "then": {
                    "required": ["seat_price", "metered_dimensions"],
                    "properties": {
                      "metered_dimensions": {
                        "minItems": 1
                      }
                    }
                  }
                }
              ],
              "additionalProperties": false
            },
            "billing_interval": {
              "$ref": "#/$defs/billing_interval"
            },
            "trial_period_days": {
              "type": "integer",
              "minimum": 0,
              "maximum": 365,
              "default": 0
            },
            "setup_fee": {
              "$ref": "#/$defs/money"
            },
            "active": {
              "type": "boolean",
              "default": true
            },
            "metadata": {
              "type": "object",
              "additionalProperties": true
            },
            "custom_fields": {
              "$ref": "#/$defs/custom_fields"
            }
          },
          "required": ["id", "tenant_id", "name", "pricing_model", "billing_interval"],
          "additionalProperties": false
        }
      }
    },
    "subscriptions": {
      "type": "object",
      "patternProperties": {
        "^[a-zA-Z0-9_-]+$": {
          "type": "object",
          "allOf": [
            {"$ref": "#/$defs/audit_fields"}
          ],
          "properties": {
            "id": {"$ref": "#/$defs/entity_id"},
            "customer_id": {"$ref": "#/$defs/entity_id"},
            "plan_id": {"$ref": "#/$defs/entity_id"},
            "status": {
              "$ref": "#/$defs/subscription_status"
            },
            "seat_count": {
              "type": "integer",
              "minimum": 1
            },
            "current_period_start": {
              "type": "string",
              "format": "date-time"
            },
            "current_period_end": {
              "type": "string",
              "format": "date-time"
            },
            "trial_end": {
              "type": ["string", "null"],
              "format": "date-time"
            },
            "billing_cycle_anchor": {
              "type": "string",
              "format": "date-time"
            },
            "proration_behavior": {
              "type": "string",
              "enum": ["create_prorations", "none", "always_invoice"],
              "default": "create_prorations"
            },
            "pending_changes": {
              "type": "object",
              "properties": {
                "plan_id": {"$ref": "#/$defs/entity_id"},
                "seat_count": {"type": "integer", "minimum": 1},
                "effective_date": {"type": "string", "format": "date-time"},
                "change_type": {
                  "type": "string",
                  "enum": ["upgrade", "downgrade", "plan_change", "seat_change"]
                },
                "change_reason": {
                  "type": "string",
                  "minLength": 0,
                  "maxLength": 500
                }
              },
              "required": ["effective_date", "change_type"],
              "additionalProperties": false
            },
            "canceled_at": {
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
            },
            "custom_fields": {
              "$ref": "#/$defs/custom_fields"
            },
            "webhook_endpoints": {
              "type": "array",
              "items": {
                "$ref": "#/$defs/webhook_endpoint"
              }
            }
          },
          "required": ["id", "customer_id", "plan_id", "status", "current_period_start", "current_period_end", "billing_cycle_anchor"],
          "additionalProperties": false
        }
      }
    },
    "usage_records": {
      "type": "object",
      "patternProperties": {
        "^[a-zA-Z0-9_-]+$": {
          "type": "object",
          "allOf": [
            {"$ref": "#/$defs/audit_fields"}
          ],
          "properties": {
            "id": {"$ref": "#/$defs/entity_id"},
            "subscription_id": {"$ref": "#/$defs/entity_id"},
            "dimension_name": {
              "type": "string",
              "minLength": 1,
              "maxLength": 100
            },
            "quantity": {
              "type": "number",
              "minimum": 0
            },
            "timestamp": {
              "type": "string",
              "format": "date-time"
            },
            "period_start": {
              "type": "string",
              "format": "date-time"
            },
            "period_end": {
              "type": "string",
              "format": "date-time"
            },
            "idempotency_key": {
              "type": "string",
              "pattern": "^[a-zA-Z0-9_-]+$",
              "minLength": 1,
              "maxLength": 255
            },
            "action": {
              "type": "string",
              "enum": ["increment", "decrement", "set"],
              "default": "increment"
            },
            "metadata": {
              "type": "object",
              "additionalProperties": true
            }
          },
          "required": ["id", "subscription_id", "dimension_name", "quantity", "timestamp", "period_start", "period_end"],
          "additionalProperties": false
        }
      }
    },
    "invoices": {
      "type": "object",
      "patternProperties": {
        "^[a-zA-Z0-9_-]+$": {
          "type": "object",
          "allOf": [
            {"$ref": "#/$defs/audit_fields"}
          ],
          "properties": {
            "id": {"$ref": "#/$defs/entity_id"},
            "customer_id": {"$ref": "#/$defs/entity_id"},
            "subscription_id": {"$ref": "#/$defs/entity_id"},
            "invoice_number": {
              "type": "string",
              "minLength": 1,
              "maxLength": 100
            },
            "status": {
              "$ref": "#/$defs/invoice_status"
            },
            "issue_date": {
              "type": "string",
              "format": "date-time"
            },
            "due_date": {
              "type": "string",
              "format": "date-time"
            },
            "subtotal": {
              "$ref": "#/$defs/money",
              "description": "Calculated as sum of all line_items amounts before tax"
            },
            "tax_amount": {
              "$ref": "#/$defs/money"
            },
            "total_amount": {
              "$ref": "#/$defs/money",
              "description": "Calculated as subtotal plus tax_amount"
            },
            "line_items": {
              "type": "array",
              "items": {
                "type": "object",
                "properties": {
                  "id": {"$ref": "#/$defs/entity_id"},
                  "description": {"type": "string", "minLength": 1, "maxLength": 500},
                  "quantity": {"type": "number", "minimum": 0},
                  "unit_price": {"$ref": "#/$defs/money"},
                  "amount": {"$ref": "#/$defs/money"},
                  "subscription_id": {"$ref": "#/$defs/entity_id"},
                  "metadata": {
                    "type": "object",
                    "additionalProperties": true
                  }
                },
                "required": ["id", "description", "quantity", "unit_price", "amount"],
                "additionalProperties": false
              },
              "minItems": 1
            },
            "period_start": {
              "type": "string",
              "format": "date-time"
            },
            "period_end": {
              "type": "string",
              "format": "date-time"
            },
            "paid_at": {
              "type": ["string", "null"],
              "format": "date-time"
            },
            "finalized_at": {
              "type": ["string", "null"],
              "format": "date-time"
            },
            "idempotency_key": {
              "type": "string",
              "pattern": "^[a-zA-Z0-9_-]+$",
              "minLength": 1,
              "maxLength": 255
            },
            "metadata": {
              "type": "object",
              "additionalProperties": true
            }
          },
          "required": ["id", "customer_id", "invoice_number", "status", "issue_date", "due_date", "subtotal", "tax_amount", "total_amount", "line_items"],
          "additionalProperties": false
        }
      }
    },
    "line_items": {
      "type": "object",
      "patternProperties": {
        "^[a-zA-Z0-9_-]+$": {
          "type": "object",
          "allOf": [
            {"$ref": "#/$defs/audit_fields"}
          ],
          "properties": {
            "id": {"$ref": "#/$defs/entity_id"},
            "invoice_id": {"$ref": "#/$defs/entity_id"},
            "description": {
              "type": "string",
              "minLength": 1,
              "maxLength": 500
            },
            "quantity": {
              "type": "number",
              "minimum": 0
            },
            "unit_price": {
              "$ref": "#/$defs/money"
            },
            "amount": {
              "$ref": "#/$defs/money"
            },
            "subscription_id": {"$ref": "#/$defs/entity_id"},
            "item_type": {
              "type": "string",
              "enum": ["subscription", "usage", "setup", "adjustment", "tax"],
              "default": "subscription"
            },
            "metadata": {
              "type": "object",
              "additionalProperties": true
            }
          },
          "required": ["id", "invoice_id", "description", "quantity", "unit_price", "amount"],
          "additionalProperties": false
        }
      }
    },
    "billing_adjustments": {
      "type": "object",
      "patternProperties": {
        "^[a-zA-Z0-9_-]+$": {
          "type": "object",
          "allOf": [
            {"$ref": "#/$defs/audit_fields"}
          ],
          "properties": {
            "id": {"$ref": "#/$defs/entity_id"},
            "customer_id": {"$ref": "#/$defs/entity_id"},
            "type": {
              "type": "string",
              "enum": ["credit", "debit", "refund", "chargeback", "dispute"]
            },
            "amount": {
              "$ref": "#/$defs/money"
            },
            "reason": {
              "type": "string",
              "minLength": 1,
              "maxLength": 500
            },
            "reference_invoice_id": {
              "type": ["string", "null"],
              "pattern": "^[a-zA-Z0-9_-]+$",
              "maxLength": 50
            },
            "status": {
              "type": "string",
              "enum": ["pending", "applied", "reversed"]
            },
            "applied_at": {
              "type": ["string", "null"],
              "format": "date-time"
            },
            "idempotency_key": {
              "type": "string",
              "pattern": "^[a-zA-Z0-9_-]+$",
              "minLength": 1,
              "maxLength": 255
            },
            "metadata": {
              "type": "object",
              "additionalProperties": true
            }
          },
          "required": ["id", "customer_id", "type", "amount", "reason", "status"],
          "additionalProperties": false
        }
      }
    },
    "dunning_campaigns": {
      "type": "object",
      "patternProperties": {
        "^[a-zA-Z0-9_-]+$": {
          "type": "object",
          "allOf": [
            {"$ref": "#/$defs/audit_fields"}
          ],
          "properties": {
            "id": {"$ref": "#/$defs/entity_id"},
            "customer_id": {"$ref": "#/$defs/entity_id"},
            "invoice_id": {"$ref": "#/$defs/entity_id"},
            "status": {
              "type": "string",
              "enum": ["active", "paused", "completed", "failed"]
            },
            "steps": {
              "type": "array",
              "items": {
                "type": "object",
                "properties": {
                  "days_after_due": {"type": "integer", "minimum": 0, "maximum": 365},
                  "action": {"type": "string", "enum": ["email", "suspend_service", "cancel_subscription"]},
                  "template_id": {"type": "string", "minLength": 1, "maxLength": 50},
                  "completed": {"type": "boolean", "default": false},
                  "completed_at": {"type": ["string", "null"], "format": "date-time"}
                },
                "required": ["days_after_due", "action"],
                "additionalProperties": false
              },
              "minItems": 1
            },
            "current_step": {
              "type": "integer",
              "minimum": 0
            },
            "metadata": {
              "type": "object",
              "additionalProperties": true
            }
          },
          "required": ["id", "customer_id", "invoice_id", "status", "steps", "current_step"],
          "additionalProperties": false
        }
      }
    },
    "revenue_recognition": {
      "type": "object",
      "patternProperties": {
        "^[a-zA-Z0-9_-]+$": {
          "type": "object",
          "allOf": [
            {"$ref": "#/$defs/audit_fields"}
          ],
          "properties": {
            "id": {"$ref": "#/$defs/entity_id"},
            "contract_id": {"$ref": "#/$defs/entity_id"},
            "performance_obligations": {
              "type": "array",
              "items": {
                "type": "object",
                "properties": {
                  "id": {"$ref": "#/$defs/entity_id"},
                  "description": {"type": "string", "minLength": 1, "maxLength": 500},
                  "standalone_selling_price": {"$ref": "#/$defs/money"},
                  "allocated_amount": {"$ref": "#/$defs/money"},
                  "satisfaction_method": {"type": "string", "enum": ["over_time", "point_in_time"]},
                  "recognition_start": {"type": "string", "format": "date-time"},
                  "recognition_end": {"type": ["string", "null"], "format": "date-time"}
                },
                "required": ["id", "description", "standalone_selling_price", "allocated_amount", "satisfaction_method"],
                "additionalProperties": false
              },
              "minItems": 1
            },
            "contract_modifications": {
              "type": "array",
              "items": {
                "type": "object",
                "properties": {
                  "modification_date": {"type": "string", "format": "date-time"},
                  "type": {"type": "string", "enum": ["separate_contract", "contract_modification", "termination"]},
                  "price_change": {"$ref": "#/$defs/money"},
                  "new_performance_obligations": {"type": "array", "items": {"type": "string", "minLength": 1, "maxLength": 50}},
                  "cumulative_catch_up_adjustment": {"$ref": "#/$defs/money"}
                },
                "required": ["modification_date", "type"],
                "additionalProperties": false
              }
            },
            "variable_consideration": {
              "type": "object",
              "properties": {
                "estimate_method": {"type": "string", "enum": ["expected_value", "most_likely_amount"]},
                "constraint_applied": {"type": "boolean"},
                "estimated_amount": {"$ref": "#/$defs/money"},
                "actual_amount": {"$ref": "#/$defs/money"}
              },
              "additionalProperties": false
            },
            "total_contract_value": {
              "$ref": "#/$defs/money"
            },
            "recognized_revenue": {
              "$ref": "#/$defs/money"
            },
            "deferred_revenue": {
              "$ref": "#/$defs/money"
            },
            "metadata": {
              "type": "object",
              "additionalProperties": true
            }
          },
          "required": ["id", "contract_id", "performance_obligations", "total_contract_value", "recognized_revenue", "deferred_revenue"],
          "additionalProperties": false
        }
      }
    },
    "payments": {
      "type": "object",
      "patternProperties": {
        "^[a-zA-Z0-9_-]+$": {
          "type": "object",
          "allOf": [
            {"$ref": "#/$defs/audit_fields"}
          ],
          "properties": {
            "id": {"$ref": "#/$defs/entity_id"},
            "invoice_id": {"$ref": "#/$defs/entity_id"},
            "amount": {
              "$ref": "#/$defs/money"
            },
            "status": {
              "type": "string",
              "enum": ["pending", "succeeded", "failed", "canceled", "refunded"]
            },
            "payment_method": {
              "type": "string",
              "enum": ["card", "ach", "wire_transfer", "check"]
            },
            "processed_at": {
              "type": ["string", "null"],
              "format": "date-time"
            },
            "failure_reason": {
              "type": "string",
              "minLength": 0,
              "maxLength": 500
            },
            "idempotency_key": {
              "type": "string",
              "pattern": "^[a-zA-Z0-9_-]+$",
              "minLength": 1,
              "maxLength": 255
            },
            "metadata": {
              "type": "object",
              "additionalProperties": true
            }
          },
          "required": ["id", "invoice_id", "amount", "status", "payment_method"],
          "additionalProperties": false
        }
      }
    },
    "extensions": {
      "type": "object",
      "additionalProperties": true
    }
  },
  "required": ["tenants", "customers", "plans", "subscriptions", "usage_records", "invoices", "line_items"],
  "additionalProperties": false
}
```

---

*Criterion scores: schema_completeness 9.0/12 (75%) | schema_correctness 7.5/10 (75%) | schema_extensibility 6.0/8 (75%) | schema_realworld 8.0/8 (100%)*
