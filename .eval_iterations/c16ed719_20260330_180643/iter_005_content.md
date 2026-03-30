```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "$id": "https://api.example.com/schemas/billing-system/v1.0.0",
  "title": "Multi-Tenant SaaS Billing System Schema",
  "version": "1.0.0",
  "deprecated_fields": ["legacy_amount_field", "old_status_field"],
  "backward_compatibility": {
    "supported_versions": ["1.0.0"],
    "minimum_api_version": "2024-01",
    "deprecated_fields": ["legacy_amount_field", "old_status_field"],
    "migration_scripts": {
      "0.9.0_to_1.0.0": {
        "transformations": [
          {
            "field": "legacy_amount_field",
            "action": "rename_to",
            "target": "amount"
          },
          {
            "field": "old_status_field", 
            "action": "map_values",
            "mapping": {"old_active": "active", "old_inactive": "suspended"}
          }
        ]
      }
    }
  },
  "migration_notes": {
    "breaking_changes": [],
    "deprecation_timeline": {}
  },
  "api_version_requirements": {
    "1.0.0": "2024-01"
  },
  "definitions": {
    "schema_evolution": {
      "type": "object",
      "properties": {
        "breaking_change_policy": {
          "type": "string",
          "enum": ["major_version_increment", "deprecation_period", "backward_compatible_only"]
        },
        "non_breaking_change_policy": {
          "type": "string",
          "enum": ["minor_version_increment", "patch_version_increment", "additive_only"]
        },
        "field_addition_policy": {
          "type": "string",
          "enum": ["optional_fields_only", "required_with_defaults", "breaking_change"]
        }
      },
      "required": ["breaking_change_policy", "non_breaking_change_policy", "field_addition_policy"],
      "additionalProperties": true
    },
    "auditable_entity": {
      "type": "object",
      "properties": {
        "schema_version": {
          "type": "string",
          "pattern": "^[0-9]+\\.[0-9]+\\.[0-9]+$",
          "description": "Entity-level schema version for backward compatibility"
        },
        "entity_version": {
          "type": "string",
          "pattern": "^[0-9]+$",
          "description": "Entity version for individual record versioning"
        },
        "created_at": {
          "$ref": "#/definitions/timestamp"
        },
        "updated_at": {
          "$ref": "#/definitions/timestamp"
        },
        "created_by": {
          "$ref": "#/definitions/uuid"
        },
        "updated_by": {
          "$ref": "#/definitions/uuid"
        }
      },
      "required": ["schema_version", "entity_version", "created_at"],
      "additionalProperties": false
    },
    "audit_fields": {
      "type": "object",
      "properties": {
        "created_at": {
          "$ref": "#/definitions/timestamp"
        },
        "updated_at": {
          "$ref": "#/definitions/timestamp"
        },
        "created_by": {
          "$ref": "#/definitions/uuid"
        },
        "updated_by": {
          "$ref": "#/definitions/uuid"
        }
      },
      "required": ["created_at"],
      "additionalProperties": false
    },
    "address": {
      "type": "object",
      "properties": {
        "street_line_1": {
          "type": "string",
          "minLength": 1
        },
        "street_line_2": {
          "type": ["string", "null"]
        },
        "city": {
          "type": "string",
          "minLength": 1
        },
        "state_province": {
          "type": "string",
          "minLength": 1
        },
        "postal_code": {
          "type": "string",
          "pattern": "^[A-Za-z0-9\\s-]{3,12}$"
        },
        "country": {
          "type": "string",
          "pattern": "^[A-Z]{2}$"
        }
      },
      "required": ["street_line_1", "city", "state_province", "postal_code", "country"],
      "additionalProperties": false
    },
    "contact_info": {
      "type": "object",
      "properties": {
        "email": {
          "type": "string",
          "format": "email"
        },
        "phone": {
          "type": ["string", "null"],
          "pattern": "^\\+?[1-9]\\d{1,14}$"
        },
        "name": {
          "type": "string",
          "minLength": 1
        },
        "title": {
          "type": ["string", "null"]
        }
      },
      "required": ["email", "name"],
      "additionalProperties": false
    },
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
    "entity_status": {
      "type": "string",
      "enum": ["active", "inactive", "suspended", "cancelled", "archived", "deprecated"]
    },
    "metered_dimension": {
      "type": "object",
      "allOf": [
        {"$ref": "#/definitions/auditable_entity"}
      ],
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
          "type": "string"
        },
        "tiers": {
          "type": "array",
          "items": {
            "$ref": "#/definitions/pricing_tier"
          },
          "minItems": 1
        },
        "custom_properties": {
          "type": "object",
          "additionalProperties": true,
          "description": "Extensible properties for dimension-specific configurations"
        }
      },
      "required": ["id", "name", "unit", "aggregation_type", "tiers"],
      "additionalProperties": true
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
        "invoice_id": {
          "$ref": "#/definitions/uuid"
        },
        "description": {
          "type": "string"
        },
        "type": {
          "$ref": "#/definitions/line_item_type"
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
      "required": ["id", "invoice_id", "description", "type", "quantity", "unit_amount", "total_amount"],
      "additionalProperties": false
    },
    "line_item_type": {
      "type": "string",
      "enum": ["seat", "usage", "one_time", "proration", "discount"]
    },
    "subscription_status": {
      "type": "string",
      "enum": ["trialing", "active", "past_due", "cancelled", "unpaid", "paused"]
    },
    "invoice_status": {
      "type": "string",
      "enum": ["draft", "open", "paid", "void", "uncollectible"]
    },
    "custom_field_definition": {
      "type": "object",
      "properties": {
        "field_name": {
          "type": "string",
          "pattern": "^[a-z][a-z0-9_]*$"
        },
        "field_type": {
          "type": "string",
          "enum": ["string", "number", "boolean", "date", "array"]
        },
        "required": {
          "type": "boolean"
        },
        "validation_rules": {
          "type": "object",
          "additionalProperties": true
        }
      },
      "required": ["field_name", "field_type"],
      "additionalProperties": false
    },
    "advanced_metadata": {
      "type": "object",
      "properties": {
        "custom_fields": {
          "type": "object",
          "patternProperties": {
            ".*": {
              "oneOf": [
                {"type": "string"},
                {"type": "number"},
                {"type": "boolean"},
                {"type": "string", "format": "date-time"},
                {"type": "array"}
              ]
            }
          },
          "additionalProperties": true
        },
        "integration_data": {
          "type": "object",
          "patternProperties": {
            "^[a-z][a-z0-9_]*_integration$": {
              "type": "object",
              "properties": {
                "external_id": {"type": "string"},
                "sync_status": {"type": "string", "enum": ["synced", "pending", "error"]},
                "last_sync": {"$ref": "#/definitions/timestamp"}
              },
              "additionalProperties": true
            }
          },
          "additionalProperties": true
        },
        "workflow_state": {
          "type": "object",
          "properties": {
            "current_stage": {"type": "string"},
            "approval_status": {"type": "string", "enum": ["pending", "approved", "rejected"]},
            "assigned_to": {"$ref": "#/definitions/uuid"}
          },
          "additionalProperties": true
        },
        "audit_metadata": {
          "type": "object",
          "properties": {
            "change_history": {
              "type": "array",
              "items": {
                "type": "object",
                "properties": {
                  "field": {"type": "string"},
                  "old_value": {},
                  "new_value": {},
                  "changed_at": {"$ref": "#/definitions/timestamp"},
                  "changed_by": {"$ref": "#/definitions/uuid"}
                }
              }
            }
          },
          "additionalProperties": true
        }
      },
      "additionalProperties": true
    },
    "payment_method_base": {
      "type": "object",
      "properties": {
        "id": {
          "$ref": "#/definitions/uuid"
        },
        "tenant_id": {
          "$ref": "#/definitions/uuid"
        },
        "type": {
          "type": "string",
          "enum": ["card", "bank_account", "ach", "wire_transfer"]
        },
        "status": {
          "type": "string",
          "enum": ["active", "inactive", "expired", "failed_verification"]
        },
        "is_default": {
          "type": "boolean"
        }
      },
      "required": ["id", "tenant_id", "type", "status"],
      "additionalProperties": false
    },
    "discount_policy": {
      "type": "object",
      "allOf": [
        {"$ref": "#/definitions/auditable_entity"}
      ],
      "properties": {
        "id": {
          "$ref": "#/definitions/uuid"
        },
        "name": {
          "type": "string"
        },
        "discount_type": {
          "type": "string",
          "enum": ["percentage", "fixed_amount", "free_trial"]
        },
        "value": {
          "type": "number",
          "minimum": 0
        },
        "eligibility_criteria": {
          "$ref": "#/definitions/eligibility_criteria"
        }
      },
      "required": ["id", "name", "discount_type", "value"],
      "additionalProperties": false
    },
    "eligibility_criteria": {
      "type": "object",
      "properties": {
        "min_seats": {
          "type": ["integer", "null"],
          "minimum": 1
        },
        "max_seats": {
          "type": ["integer", "null"],
          "minimum": 1
        },
        "tenant_age_days": {
          "type": ["integer", "null"],
          "minimum": 0
        },
        "plan_ids": {
          "type": ["array", "null"],
          "items": {
            "$ref": "#/definitions/uuid"
          }
        }
      },
      "additionalProperties": false,
      "not": {
        "allOf": [
          {"properties": {"min_seats": {"type": "null"}}},
          {"properties": {"max_seats": {"type": "null"}}},
          {"properties": {"tenant_age_days": {"type": "null"}}},
          {"properties": {"plan_ids": {"type": "null"}}}
        ]
      }
    }
  },
  "type": "object",
  "properties": {
    "tenants": {
      "type": "array",
      "items": {
        "type": "object",
        "allOf": [
          {"$ref": "#/definitions/auditable_entity"}
        ],
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
          "billing_address": {
            "$ref": "#/definitions/address"
          },
          "billing_contact": {
            "$ref": "#/definitions/contact_info"
          },
          "metadata": {
            "$ref": "#/definitions/advanced_metadata"
          }
        },
        "required": ["id", "name", "status"],
        "additionalProperties": false
      }
    },
    "plans": {
      "type": "array",
      "items": {
        "type": "object",
        "allOf": [
          {"$ref": "#/definitions/auditable_entity"}
        ],
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
                "required": ["metered_dimensions"],
                "properties": {
                  "metered_dimensions": {
                    "minItems": 1
                  }
                }
              },
              "else": {
                "if": {
                  "properties": {
                    "type": {
                      "const": "hybrid"
                    }
                  }
                },
                "then": {
                  "required": ["seat_price", "metered_dimensions"],
                  "properties": {
                    "seat_price": {
                      "$ref": "#/definitions/money",
                      "properties": {
                        "amount": {
                          "type": "number",
                          "minimum": 0.01
                        }
                      }
                    },
                    "metered_dimensions": {
                      "minItems": 1
                    }
                  }
                }
              }
            }
          },
          "metadata": {
            "$ref": "#/definitions/advanced_metadata"
          }
        },
        "required": ["id", "name", "status", "pricing_model"],
        "additionalProperties": false
      }
    },
    "subscriptions": {
      "type": "array",
      "items": {
        "type": "object",
        "allOf": [
          {"$ref": "#/definitions/auditable_entity"}
        ],
        "properties": {
          "id": {
            "$ref": "#/definitions/uuid"
          },
          "idempotency_key": {
            "type": "string",
            "format": "uuid",
            "description": "Unique key to prevent duplicate subscription creation"
          },
          "tenant_id": {
            "$ref": "#/definitions/uuid"
          },
          "plan_id": {
            "$ref": "#/definitions/uuid"
          },
          "status": {
            "$ref": "#/definitions/subscription_status"
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
          "cancelled_at": {
            "type": ["string", "null"],
            "format": "date-time"
          },
          "ended_at": {
            "type": ["string", "null"],
            "format": "date-time"
          },
          "cancellation_date": {
            "type": ["string", "null"],
            "format": "date-time"
          },
          "cancellation_reason": {
            "type": ["string", "null"],
            "enum": ["voluntary", "payment_failure", "terms_violation", "business_closure", "other"]
          },
          "creation_source": {
            "type": "string",
            "enum": ["api", "dashboard", "webhook", "migration", "trial_conversion"]
          },
          "metadata": {
            "$ref": "#/definitions/advanced_metadata"
          }
        },
        "required": ["id", "idempotency_key", "tenant_id", "plan_id", "status", "current_period_start", "current_period_end", "seats", "proration_behavior", "creation_source"],
        "additionalProperties": false
      }
    },
    "usage_records": {
      "type": "array",
      "items": {
        "type": "object",
        "allOf": [
          {"$ref": "#/definitions/auditable_entity"}
        ],
        "properties": {
          "id": {
            "$ref": "#/definitions/uuid"
          },
          "idempotency_key": {
            "type": "string",
            "format": "uuid",
            "description": "Unique key to prevent duplicate usage recording"
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
            "$ref": "#/definitions/advanced_metadata"
          }
        },
        "required": ["id", "idempotency_key", "subscription_id", "metered_dimension_id", "quantity", "timestamp", "action"],
        "additionalProperties": false
      }
    },
    "invoices": {
      "type": "array",
      "items": {
        "type": "object",
        "allOf": [
          {"$ref": "#/definitions/auditable_entity"}
        ],
        "properties": {
          "id": {
            "$ref": "#/definitions/uuid"
          },
          "idempotency_key": {
            "type": "string",
            "format": "uuid",
            "description": "Unique key to prevent duplicate invoice creation"
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
            "$ref": "#/definitions/invoice_status"
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
            "$ref": "#/definitions/advanced_metadata"
          }
        },
        "required": ["id", "idempotency_key", "tenant_id", "subscription_id", "number", "status", "currency", "subtotal", "tax", "total", "amount_paid", "amount_due", "line_items", "period_start", "period_end", "due_date"],
        "additionalProperties": false
      }
    },
    "subscription_changes": {
      "type": "array",
      "items": {
        "type": "object",
        "allOf": [
          {"$ref": "#/definitions/auditable_entity"}
        ],
        "properties": {
          "id": {
            "$ref": "#/definitions/uuid"
          },
          "idempotency_key": {
            "type": "string",
            "format": "uuid",
            "description": "Unique key to prevent duplicate subscription changes"
          },
          "subscription_id": {
            "$ref": "#/definitions/uuid"
          },
          "change_type": {
            "type": "string",
            "enum": ["create", "upgrade", "downgrade", "seat_change", "plan_change", "cancellation", "cancel", "reactivation"]
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
          "metadata": {
            "$ref": "#/definitions/advanced_metadata"
          }
        },
        "required": ["id", "idempotency_key", "subscription_id", "change_type", "effective_date"],
        "additionalProperties": false
      }
    },
    "payment_methods": {
      "type": "array",
      "items": {
        "oneOf": [
          {
            "allOf": [
              {"$ref": "#/definitions/payment_method_base"},
              {"$ref": "#/definitions/auditable_entity"}
            ],
            "properties": {
              "type": {"const": "card"},
              "card_details": {
                "type": "object",
                "properties": {
                  "last_four": {"type": "string", "pattern": "^[0-9]{4}$"},
                  "brand": {"type": "string", "enum": ["visa", "mastercard", "amex", "discover"]},
                  "exp_month": {"type": "integer", "minimum": 1, "maximum": 12},
                  "exp_year": {"type": "integer", "minimum": 2024},
                  "token": {"type": "string", "description": "Tokenized card reference"}
                },
                "required": ["last_four", "brand", "exp_month", "exp_year", "token"]
              }
            },
            "required": ["card_details"]
          },
          {
            "allOf": [
              {"$ref": "#/definitions/payment_method_base"},
              {"$ref": "#/definitions/auditable_entity"}
            ],
            "properties": {
              "type": {"const": "bank_account"},
              "bank_details": {
                "type": "object",
                "properties": {
                  "last_four": {"type": "string", "pattern": "^[0-9]{4}$"},
                  "routing_number": {"type": "string", "pattern": "^[0-9]{9}$"},
                  "account_type": {"type": "string", "enum": ["checking", "savings"]},
                  "bank_name": {"type": "string"}
                },
                "required": ["last_four", "routing_number", "account_type"]
              }
            },
            "required": ["bank_details"]
          }
        ]
      }
    },
    "dunning_management": {
      "type": "array",
      "items": {
        "type": "object",
        "allOf": [
          {"$ref": "#/definitions/auditable_entity"}
        ],
        "properties": {
          "id": {
            "$ref": "#/definitions/uuid"
          },
          "tenant_id": {
            "$ref": "#/definitions/uuid"
          },
          "invoice_id": {
            "$ref": "#/definitions/uuid"
          },
          "retry_policy": {
            "type": "object",
            "properties": {
              "max_attempts": {"type": "integer", "minimum": 1, "maximum": 10},
              "retry_intervals": {
                "type": "array",
                "items": {"type": "integer", "minimum": 1},
                "description": "Retry intervals in hours"
              },
              "escalation_actions": {
                "type": "array",
                "items": {
                  "type": "string",
                  "enum": ["email_notification", "webhook", "suspend_service", "cancel_subscription"]
                }
              }
            },
            "required": ["max_attempts", "retry_intervals"]
          },
          "current_attempt": {
            "type": "integer",
            "minimum": 0
          },
          "next_retry_at": {
            "$ref": "#/definitions/timestamp"
          },
          "status": {
            "type": "string",
            "enum": ["active", "paused", "completed", "failed"]
          }
        },
        "required": ["id", "tenant_id", "invoice_id", "retry_policy", "current_attempt", "status"]
      }
    },
    "tax_rates": {
      "type": "array",
      "items": {
        "type": "object",
        "allOf": [
          {"$ref": "#/definitions/auditable_entity"}
        ],
        "properties": {
          "id": {
            "$ref": "#/definitions/uuid"
          },
          "jurisdiction": {
            "type": "object",
            "properties": {
              "country_code": {"type": "string", "pattern": "^[A-Z]{2}$"},
              "state_code": {"type": ["string", "null"], "pattern": "^[A-Z]{2}$"},
              "city": {"type": ["string", "null"]},
              "postal_code": {"type": ["string", "null"]}
            },
            "required": ["country_code"]
          },
          "tax_type": {
            "type": "string",
            "enum": ["sales", "vat", "gst", "hst"]
          },
          "rate": {
            "type": "number",
            "minimum": 0,
            "maximum": 1,
            "description": "Tax rate as decimal (e.g., 0.08 for 8%)"
          },
          "effective_from": {
            "$ref": "#/definitions/timestamp"
          },
          "effective_until": {
            "type": ["string", "null"],
            "format": "date-time"
          }
        },
        "required": ["id", "jurisdiction", "tax_type", "rate", "effective_from"]
      }
    },
    "credit_notes": {
      "type": "array",
      "items": {
        "type": "object",
        "allOf": [
          {"$ref": "#/definitions/auditable_entity"}
        ],
        "properties": {
          "id": {
            "$ref": "#/definitions/uuid"
          },
          "idempotency_key": {
            "type": "string",
            "format": "uuid",
            "description": "Unique key to prevent duplicate credit note creation"
          },
          "tenant_id": {
            "$ref": "#/definitions/uuid"
          },
          "invoice_id": {
            "$ref": "#/definitions/uuid"
          },
          "number": {
            "type": "string",
            "pattern": "^CN-[0-9]+$"
          },
          "reason": {
            "type": "string",
            "enum": ["duplicate_charge", "service_downtime", "billing_error", "customer_refund", "plan_downgrade"]
          },
          "amount": {
            "$ref": "#/definitions/money"
          },
          "refund_method": {
            "type": "string",
            "enum": ["account_credit", "original_payment_method", "check", "wire_transfer"]
          },
          "status": {
            "type": "string",
            "enum": ["draft", "issued", "refunded", "voided"]
          },
          "line_items": {
            "type": "array",
            "items": {
              "$ref": "#/definitions/line_item"
            }
          }
        },
        "required": ["id", "idempotency_key", "tenant_id", "invoice_id", "number", "reason", "amount", "status"]
      }
    },
    "billing_alerts": {
      "type": "array",
      "items": {
        "type": "object",
        "allOf": [
          {"$ref": "#/definitions/auditable_entity"}
        ],
        "properties": {
          "id": {
            "$ref": "#/definitions/uuid"
          },
          "tenant_id": {
            "$ref": "#/definitions/uuid"
          },
          "alert_type": {
            "type": "string",
            "enum": ["usage_threshold", "payment_failure", "trial_expiring", "subscription_change", "invoice_overdue"]
          },
          "threshold_config": {
            "type": "object",
            "properties": {
              "metric": {"type": "string"},
              "threshold_value": {"type": "number"},
              "threshold_type": {"type": "string", "enum": ["absolute", "percentage"]},
              "comparison": {"type": "string", "enum": ["greater_than", "less_than", "equals"]}
            },
            "dependencies": {
              "threshold_value": ["metric", "threshold_type", "comparison"]
            }
          },
          "notification_channels": {
            "type": "array",
            "items": {
              "type": "string",
              "enum": ["email", "webhook", "sms", "slack"]
            },
            "minItems": 1
          },
          "is_active": {
            "type": "boolean"
          },
          "last_triggered": {
            "type": ["string", "null"],
            "format": "date-time"
          }
        },
        "required": ["id", "tenant_id", "alert_type", "notification_channels", "is_active"]
      }
    }
  },
  "required": ["tenants", "plans", "subscriptions", "usage_records", "invoices", "subscription_changes", "payment_methods", "dunning_management", "tax_rates", "credit_notes", "billing_alerts"],
  "additionalProperties": false
}
```