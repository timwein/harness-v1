# Rubric: infrastructure_as_code

**Task:** Write Terraform HCL for a production-grade AWS deployment with VPC, ECS Fargate, RDS, and ALB across dev/staging/prod environments using workspaces and modules, with least-privilege IAM

**Domain:** infrastructure_as_code
**Total Points:** 56
**Pass Threshold:** 85%
**Criteria Count:** 5
**Generated:** 2026-03-31 05:57:05 UTC

---

## 1. tf_modularity

**Category:** architecture
**Description:** Infrastructure is decomposed into reusable, composable Terraform modules

**Pass Condition:** Separate modules for VPC, ECS, RDS, ALB, IAM. Root module composes them. Modules are parameterized via variables, not hardcoded. Module outputs feed into dependent modules.

**Scoring Method:** `weighted_components`
**Max Points:** 12

### Sub-Attributes

| Sub-ID | Weight | Description | Measurement |
|--------|--------|-------------|-------------|
| `module_decomposition` | 35% | Separate modules for each infrastructure concern | % of components in dedicated modules (VPC, ECS, RDS, ALB, IAM = 5) |
| `parameterization` | 30% | Modules use variables, not hardcoded values | 1.0 if fully parameterized, 0.5 if mixed, 0.0 if hardcoded |
| `module_composition` | 35% | Root module wires modules together via outputs/inputs | 1.0 if clean composition, 0.5 if some direct references, 0.0 if monolithic |

### Pass Examples

- modules/vpc/, modules/ecs/, modules/rds/ — root main.tf: module "vpc" { source = "./modules/vpc" ... }

### Fail Examples

- Single main.tf with 500 lines and no modules

---

## 2. tf_multi_env

**Category:** operations
**Description:** Dev/staging/prod environments are properly isolated with environment-specific config

**Pass Condition:** Workspace-based or directory-based env separation. Environment-specific tfvars. Resource naming includes environment. Different sizing per environment (smaller instances in dev). State isolation.

**Scoring Method:** `weighted_components`
**Max Points:** 12

### Sub-Attributes

| Sub-ID | Weight | Description | Measurement |
|--------|--------|-------------|-------------|
| `env_separation` | 30% | Clear mechanism for env isolation (workspaces or directories) | 1.0 if workspaces with var files, 0.5 if basic separation, 0.0 if not separated |
| `config_differentiation` | 30% | Resource sizes/counts differ by environment | 1.0 if env-specific sizing (e.g., t3.micro in dev, r5.xlarge in prod), 0.5 if some, 0.0 if identical |
| `naming_convention` | 20% | Resources named with environment prefix/suffix | 1.0 if consistent naming, 0.5 if partial, 0.0 if no env in names |
| `state_isolation` | 20% | Separate state files per environment | 1.0 if isolated state (workspace or backend key), 0.0 if shared state |

### Pass Examples

- terraform workspace select prod && terraform apply -var-file=envs/prod.tfvars

### Fail Examples

- Same config for all environments, no workspace or var-file differentiation

---

## 3. tf_iam_security

**Category:** security
**Description:** IAM follows least-privilege with no wildcards in production policies

**Pass Condition:** Task execution role with minimal permissions. No Action: '*' or Resource: '*'. Service-linked roles where appropriate. Separate roles for ECS task vs execution. Secrets in SSM/Secrets Manager, not environment variables.

**Scoring Method:** `penalty_based`
**Max Points:** 14

### Penalties

- **action_wildcard:** -4.0 pts
- **resource_wildcard:** -3.0 pts
- **combined_task_execution_role:** -2.0 pts
- **hardcoded_secrets:** -4.0 pts
- **no_secrets_management:** -2.0 pts
- **overly_permissive_sg:** -2.0 pts
- **admin_access_policy:** -4.0 pts

### Pass Examples

- aws_iam_role.ecs_task_role with policy allowing only s3:GetObject on specific bucket ARN

### Fail Examples

- Action: ['*'], Resource: ['*'] — admin access on ECS task role

---

## 4. tf_networking

**Category:** infrastructure
**Description:** VPC and networking are production-grade with proper isolation and security groups

**Pass Condition:** Multi-AZ VPC with public/private/data subnets. NAT Gateway for private subnet egress. Security groups with specific rules (not 0.0.0.0/0 ingress). ALB in public subnet, ECS in private, RDS in data subnet.

**Scoring Method:** `weighted_components`
**Max Points:** 10

### Sub-Attributes

| Sub-ID | Weight | Description | Measurement |
|--------|--------|-------------|-------------|
| `subnet_design` | 30% | Public/private/data subnets across multiple AZs | 1.0 if 3-tier multi-AZ, 0.5 if 2-tier, 0.0 if single subnet |
| `security_groups` | 35% | Specific ingress/egress rules, no 0.0.0.0/0 except ALB HTTP/S | 1.0 if specific rules, 0.5 if mostly specific, 0.0 if wide open |
| `tier_isolation` | 35% | ALB→public, ECS→private, RDS→data with proper routing | 1.0 if correct tier placement, 0.5 if partially correct, 0.0 if flat |

### Pass Examples

- Private subnets for ECS with NAT GW egress; RDS in data subnets with SG allowing only ECS task SG ingress on 5432

### Fail Examples

- Single public subnet for everything, 0.0.0.0/0 on all security groups

---

## 5. tf_best_practices

**Category:** quality
**Description:** Follows Terraform best practices: remote state, locking, tagging, outputs

**Pass Condition:** Remote state backend (S3 + DynamoDB). Consistent tagging strategy. terraform.tfvars for defaults. Outputs for important values. Version constraints on providers and modules.

**Scoring Method:** `weighted_components`
**Max Points:** 8

### Sub-Attributes

| Sub-ID | Weight | Description | Measurement |
|--------|--------|-------------|-------------|
| `remote_state` | 30% | S3 backend with DynamoDB locking | 1.0 if S3+DynamoDB, 0.5 if S3 only, 0.0 if local state |
| `tagging` | 25% | Consistent tagging (Environment, Project, ManagedBy) on all resources | 1.0 if consistent tags, 0.5 if partial, 0.0 if none |
| `version_constraints` | 25% | Provider and module versions pinned | 1.0 if versions pinned, 0.5 if partial, 0.0 if unpinned |
| `outputs` | 20% | Key values (endpoints, ARNs) exposed as outputs | 1.0 if comprehensive outputs, 0.5 if some, 0.0 if none |

### Pass Examples

- backend "s3" { bucket = "tfstate-myproject", dynamodb_table = "tfstate-lock", key = "env/${terraform.workspace}" }

### Fail Examples

- Local state, no tagging, no version pins

---
