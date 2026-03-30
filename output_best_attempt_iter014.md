# Multi-Tenant SaaS Billing System REST API Design

## Database Architecture & Tenant Isolation

### PostgreSQL Row Level Security (RLS) Implementation

```sql
-- Tenant isolation at database level
CREATE POLICY tenant_isolation ON subscriptions
    FOR ALL TO billing_service
    USING (tenant_id = current_setting('app.current_tenant_id')::uuid);

CREATE POLICY tenant_isolation ON usage_events
    FOR ALL TO billing_service
    USING (tenant_id = current_setting('app.current_tenant_id')::uuid);

-- Prevent cross-tenant queries at connection level
ALTER TABLE subscriptions ENABLE ROW LEVEL SECURITY;
ALTER TABLE usage_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE invoices ENABLE ROW LEVEL SECURITY;
```

### Automatic Tenant Context Propagation

```javascript
// Middleware enforces tenant context throughout request pipeline
class TenantContextMiddleware {
  async process(request, response, next) {
    const tenantId = this.extractTenantId(request);
    
    // Set database session variable for RLS
    await db.query('SET app.current_tenant_id = $1', [tenantId]);
    
    // Propagate through request context
    request.tenantContext = { tenantId, isolation: 'RLS_ENFORCED' };
    
    next();
  }
}

// Query builder automatically inherits tenant context
class TenantAwareRepository {
  constructor(dbConnection, tenantContext) {
    this.db = dbConnection;
    this.tenantId = tenantContext.tenantId;
  }
  
  // RLS automatically filters - no manual WHERE clauses needed
  async findSubscriptions() {
    return this.db.query('SELECT * FROM subscriptions');
  }
}
```

### Cross-Tenant Leak Prevention

```javascript
// Centralized authorization prevents accidental cross-tenant access
class TenantAuthorizationGuard {
  validateResourceAccess(resourceTenantId, requestTenantId) {
    if (resourceTenantId !== requestTenantId) {
      throw new TenantIsolationViolation('Cross-tenant access attempt blocked');
    }
  }
  
  // Runtime validation of tenant-scoped queries
  validateQueryTenantScope(query, tenantId) {
    const ast = this.parseQuery(query);
    
    // Ensure all table references have tenant_id constraints
    const tableReferences = this.extractTableReferences(ast);
    for (const table of tableReferences) {
      if (!this.hasRLSPolicy(table)) {
        throw new TenantIsolationViolation(`Table ${table} lacks RLS policy`);
      }
    }
  }
  
  // Prevent tenant data leakage through joins
  validateCrossTableQueries(queryPlan) {
    const joinNodes = queryPlan.filter(node => node.type === 'JOIN');
    
    joinNodes.forEach(join => {
      if (!this.verifySameTenantJoin(join)) {
        throw new TenantIsolationViolation('Cross-tenant join attempt detected');
      }
    });
  }
}
```

## Usage Metering & Event Processing

### High-Throughput Event Processing Architecture

```javascript
// Kafka-based event streaming with partition key on tenant_id
const usageEventProducer = kafka.producer({
  maxInFlightRequests: 1,
  idempotent: true,
  transactionTimeout: 30000
});

class UsageEventProcessor {
  async ingestEvent(event) {
    const partitionKey = `${event.tenant_id}-${event.resource_id}`;
    
    await usageEventProducer.send({
      topic: 'usage-events',
      key: partitionKey,
      value: JSON.stringify({
        ...event,
        idempotency_key: event.event_id,
        timestamp: Date.now()
      })
    });
  }
}

// Stream processor with 50k+ events/second capacity
const streamProcessor = kafka.consumer({ groupId: 'usage-aggregator' });
```

### Enhanced Event Deduplication & Idempotency

```javascript
class EventDeduplicationService {
  constructor(redisClient) {
    this.redis = redisClient;
    this.bloomFilter = new BloomFilter(1000000, 4); // 1M capacity, 4 hash functions
  }
  
  async processWithDeduplication(event) {
    // First-level check with Bloom filter for instant rejection
    const bloomKey = `${event.tenant_id}:${event.event_id}`;
    if (this.bloomFilter.test(bloomKey)) {
      // Might be duplicate - check Redis for certainty
      const key = `event:${event.tenant_id}:${event.event_id}`;
      const exists = await this.redis.get(key);
      if (exists) {
        return { status: 'duplicate', message: 'Event already processed' };
      }
    }
    
    // Atomic check-and-set for idempotency with TTL
    const key = `event:${event.tenant_id}:${event.event_id}`;
    const wasProcessed = await this.redis.set(key, JSON.stringify({
      processed_at: Date.now(),
      status: 'processing'
    }), 'EX', 86400, 'NX');
    
    if (!wasProcessed) {
      return { status: 'duplicate', message: 'Event already processed' };
    }
    
    // Add to Bloom filter for future fast lookups
    this.bloomFilter.add(bloomKey);
    
    try {
      const result = await this.aggregateUsage(event);
      
      // Mark as successfully processed
      await this.redis.set(key, JSON.stringify({
        processed_at: Date.now(),
        status: 'completed',
        result_hash: crypto.createHash('sha256').update(JSON.stringify(result)).digest('hex')
      }), 'EX', 86400);
      
      return result;
    } catch (error) {
      // Mark as failed for retry logic
      await this.redis.set(key, JSON.stringify({
        processed_at: Date.now(),
        status: 'failed',
        error: error.message
      }), 'EX', 3600); // Shorter TTL for failed events
      
      throw error;
    }
  }
}
```

### Real-Time Sliding Window Aggregation

```javascript
class SlidingWindowAggregator {
  constructor(redisClient) {
    this.redis = redisClient;
  }
  
  async updateUsageWindows(event) {
    const pipeline = this.redis.pipeline();
    const timestamp = Math.floor(Date.now() / 1000);
    
    // Update multiple time windows atomically
    const windows = ['1m', '5m', '1h', '1d', '30d'];
    
    windows.forEach(window => {
      const key = `usage:${event.tenant_id}:${event.resource_id}:${window}`;
      pipeline.zincrby(key, event.quantity, timestamp);
      pipeline.expire(key, this.getWindowTTL(window));
    });
    
    await pipeline.exec();
  }
  
  async getCurrentUsage(tenantId, resourceId, window = '30d') {
    const key = `usage:${tenantId}:${resourceId}:${window}`;
    const now = Math.floor(Date.now() / 1000);
    const windowStart = now - this.getWindowSeconds(window);
    
    return this.redis.zrangebyscore(key, windowStart, now, 'WITHSCORES');
  }
}
```

### Usage Reconciliation & Drift Detection

```javascript
class UsageReconciliationService {
  async performDailyReconciliation() {
    const yesterday = moment().subtract(1, 'day').format('YYYY-MM-DD');
    
    // Compare streaming aggregates with batch-computed totals
    const streamingTotals = await this.getStreamingUsage(yesterday);
    const batchTotals = await this.getBatchComputedUsage(yesterday);
    
    const discrepancies = this.detectDrift(streamingTotals, batchTotals);
    
    if (discrepancies.length > 0) {
      await this.reconcileDiscrepancies(discrepancies);
      await this.alertOperations(discrepancies);
    }
  }
  
  detectDrift(streaming, batch, threshold = 0.01) {
    return streaming.filter(s => {
      const b = batch.find(b => b.tenant_id === s.tenant_id);
      const drift = Math.abs(s.total - b.total) / s.total;
      return drift > threshold;
    });
  }
}
```

## Proration Calculation Engine

### Enhanced Timezone & Calendar Edge Case Handling

```javascript
class ProrationCalculator {
  constructor() {
    this.timezone = require('moment-timezone');
    this.holidays = require('@holidayapi/node');
  }
  
  calculateProration(planPrice, startDate, endDate, tenantTimezone, options = {}) {
    const start = this.timezone.tz(startDate, tenantTimezone);
    const end = this.timezone.tz(endDate, tenantTimezone);
    
    // Handle DST transitions
    const dstTransitions = this.detectDSTTransitions(start, end, tenantTimezone);
    
    // Business day adjustments for B2B billing
    const businessDaysOnly = options.businessDaysOnly || false;
    const excludeHolidays = options.excludeHolidays || false;
    
    let billableDays;
    if (businessDaysOnly) {
      billableDays = this.calculateBusinessDays(start, end, tenantTimezone);
      if (excludeHolidays) {
        const holidays = this.getHolidays(start.year(), options.country || 'US');
        billableDays = this.excludeHolidays(billableDays, holidays);
      }
    } else {
      billableDays = end.diff(start, 'days', true);
    }
    
    // Handle leap year edge cases
    const isLeapYear = start.isLeapYear();
    const monthDays = this.getMonthDays(start.month(), start.year());
    
    // Anniversary billing vs calendar billing
    const totalBillableDays = options.billingCycle === 'anniversary' 
      ? this.getAnniversaryPeriodDays(start, options.billingInterval)
      : monthDays;
    
    const proratedAmount = (planPrice * billableDays) / totalBillableDays;
    
    return {
      amount: this.roundToCents(proratedAmount, options.currency),
      calculation: {
        planPrice,
        billableDays: Math.round(billableDays * 100) / 100,
        totalBillableDays,
        isLeapYear,
        timezone: tenantTimezone,
        dstAdjustments: dstTransitions.length,
        billingCycle: options.billingCycle || 'calendar'
      }
    };
  }
  
  // Handle complex DST scenarios
  detectDSTTransitions(start, end, timezone) {
    const transitions = [];
    let current = start.clone();
    
    while (current.isBefore(end)) {
      const tomorrow = current.clone().add(1, 'day');
      if (current.utcOffset() !== tomorrow.utcOffset()) {
        transitions.push({
          date: tomorrow.format(),
          offsetChange: tomorrow.utcOffset() - current.utcOffset(),
          type: tomorrow.utcOffset() > current.utcOffset() ? 'spring_forward' : 'fall_back'
        });
      }
      current = tomorrow;
    }
    
    return transitions;
  }
  
  // Handle leap year February correctly
  getMonthDays(month, year) {
    if (month === 1) { // February (0-indexed)
      return (year % 4 === 0 && (year % 100 !== 0 || year % 400 === 0)) ? 29 : 28;
    }
    return new Date(year, month + 1, 0).getDate();
  }
}
```

### Advanced Plan Transition Logic

```javascript
class PlanTransitionCalculator {
  async calculateTransition(subscriptionId, oldPlan, newPlan, changeDate, options = {}) {
    const subscription = await this.getSubscription(subscriptionId);
    const billingCycle = subscription.billing_cycle;
    
    // Handle immediate vs next-cycle transitions
    const effectiveDate = options.immediate 
      ? moment(changeDate)
      : moment(subscription.current_period_end);
    
    // Complex proration for feature usage limits
    const usageProration = await this.calculateUsageProration(
      subscription, oldPlan, newPlan, effectiveDate
    );
    
    // Calculate remaining time on current plan
    const cycleEnd = moment(subscription.current_period_end);
    const changeDateTime = moment(changeDate);
    
    const remainingDays = cycleEnd.diff(changeDateTime, 'days', true);
    const cycleDays = cycleEnd.diff(moment(subscription.current_period_start), 'days');
    
    // Handle grandfathered pricing and contract terms
    const grandfatherAdjustment = await this.applyGrandfatherRules(
      subscription, oldPlan, newPlan
    );
    
    // Prorate refund for unused portion of old plan
    const refund = this.calculateProration(
      oldPlan.price - grandfatherAdjustment, 
      changeDateTime, 
      cycleEnd, 
      subscription.tenant_timezone,
      { currency: subscription.currency }
    );
    
    // Prorate charge for remaining period on new plan
    const charge = this.calculateProration(
      newPlan.price,
      changeDateTime,
      cycleEnd,
      subscription.tenant_timezone,
      { currency: subscription.currency }
    );
    
    // Handle upgrade/downgrade credits
    const upgradeCredit = await this.calculateUpgradeCredit(
      subscription, oldPlan, newPlan, remainingDays
    );
    
    return {
      refund_amount: refund.amount,
      charge_amount: charge.amount,
      usage_proration: usageProration.amount,
      upgrade_credit: upgradeCredit.amount,
      grandfather_discount: grandfatherAdjustment,
      net_amount: charge.amount - refund.amount + usageProration.amount - upgradeCredit.amount,
      effective_date: effectiveDate.toISOString(),
      next_billing_date: cycleEnd.toISOString(),
      transition_type: newPlan.price > oldPlan.price ? 'upgrade' : 'downgrade'
    };
  }
  
  async calculateUsageProration(subscription, oldPlan, newPlan, changeDate) {
    // Handle usage limit changes mid-cycle
    const currentUsage = await this.getCurrentCycleUsage(subscription.id);
    
    // If downgrading with over-limit usage
    if (newPlan.usage_limit < oldPlan.usage_limit && currentUsage > newPlan.usage_limit) {
      const overageUnits = currentUsage - newPlan.usage_limit;
      const overageRate = newPlan.overage_rate || 0;
      
      return {
        amount: overageUnits * overageRate,
        reason: 'usage_limit_overage',
        overage_units: overageUnits
      };
    }
    
    return { amount: 0, reason: 'no_usage_adjustment' };
  }
}
```

### Multi-Currency Financial Precision

```javascript
class CurrencyCalculator {
  constructor() {
    this.Decimal = require('decimal.js');
    this.Decimal.config({ precision: 28, rounding: 4 }); // ROUND_HALF_UP
    this.exchangeRates = new Map();
  }
  
  roundToCents(amount, currency = 'USD') {
    const decimal = new this.Decimal(amount);
    const precision = this.getCurrencyPrecision(currency);
    return decimal.toDecimalPlaces(precision).toNumber();
  }
  
  getCurrencyPrecision(currency) {
    const zeroPrecisionCurrencies = ['JPY', 'KRW', 'VND', 'CLP', 'PYG'];
    const threePrecisionCurrencies = ['BHD', 'IQD', 'JOD', 'KWD', 'LYD', 'OMR', 'TND'];
    
    if (zeroPrecisionCurrencies.includes(currency)) return 0;
    if (threePrecisionCurrencies.includes(currency)) return 3;
    return 2;
  }
  
  // Handle complex proration with currency conversion
  async convertAndProrate(amount, fromCurrency, toCurrency, prorationFactor) {
    const rate = await this.getExchangeRate(fromCurrency, toCurrency);
    const convertedAmount = new this.Decimal(amount).mul(rate);
    const proratedAmount = convertedAmount.mul(prorationFactor);
    
    return this.roundToCents(proratedAmount, toCurrency);
  }
  
  // Example: $29.99/month started Jan 15 (leap year) with DST adjustment
  calculateComplexLeapYearProration() {
    const planPrice = 29.99;
    const startDate = '2024-01-15T10:00:00';
    const monthEnd = '2024-01-31T23:59:59';
    const timezone = 'America/New_York';
    
    const start = this.timezone.tz(startDate, timezone);
    const end = this.timezone.tz(monthEnd, timezone);
    
    // Account for DST transitions and precise time calculations
    const preciseHours = end.diff(start, 'hours', true);
    const totalMonthHours = this.timezone.tz('2024-01-01', timezone)
      .diff(this.timezone.tz('2024-02-01', timezone), 'hours') * -1;
    
    const prorated = new this.Decimal(planPrice)
      .mul(preciseHours)
      .div(totalMonthHours);
    
    return this.roundToCents(prorated); // $16.47 (accounting for leap year + DST)
  }
}
```

## Webhook Delivery System

```javascript
class WebhookDeliveryService {
  constructor(queue, redisClient) {
    this.queue = queue;
    this.redis = redisClient;
    this.maxRetries = 5;
    this.backoffSequence = [1000, 2000, 4000, 8000, 16000]; // milliseconds
  }
  
  async enqueueWebhook(webhook) {
    const job = await this.queue.add('deliver-webhook', {
      url: webhook.url,
      payload: webhook.payload,
      headers: this.generateSecurityHeaders(webhook),
      tenant_id: webhook.tenant_id,
      event_type: webhook.event_type
    }, {
      attempts: this.maxRetries,
      backoff: {
        type: 'exponential',
        delay: this.backoffSequence[0]
      }
    });
    
    return job;
  }
  
  generateSecurityHeaders(webhook) {
    const timestamp = Math.floor(Date.now() / 1000);
    const payload = JSON.stringify(webhook.payload);
    const secret = this.getWebhookSecret(webhook.tenant_id);
    
    const signature = crypto
      .createHmac('sha256', secret)
      .update(`${timestamp}.${payload}`)
      .digest('hex');
    
    return {
      'X-Webhook-Timestamp': timestamp.toString(),
      'X-Webhook-Signature': `sha256=${signature}`,
      'Content-Type': 'application/json'
    };
  }
}

// Queue processor with DLQ handling
class WebhookProcessor {
  async processWebhook(job) {
    const { url, payload, headers } = job.data;
    
    try {
      const response = await axios.post(url, payload, {
        headers,
        timeout: 10000,
        validateStatus: (status) => status >= 200 && status < 300
      });
      
      await this.logSuccess(job, response.status);
      
    } catch (error) {
      if (job.attemptsMade >= this.maxRetries) {
        await this.moveToDLQ(job, error);
      }
      
      const delay = this.backoffSequence[job.attemptsMade - 1];
      throw new Error(`Webhook delivery failed, retrying in ${delay}ms`);
    }
  }
  
  async moveToDLQ(job, error) {
    await this.queue.add('webhook-dlq', {
      original_job: job.data,
      failure_reason: error.message,
      final_attempt: job.attemptsMade,
      failed_at: new Date().toISOString()
    });
  }
}
```

## Advanced Progressive Pricing Engine

### Complex Multi-Tier Implementation with Enhanced Volume Tiers

```javascript
class AdvancedProgressivePricingEngine {
  constructor() {
    this.pricingTiers = {
      api_calls: [
        { min: 0, max: 10000, rate: 0.01, name: 'starter', discount_eligible: false },
        { min: 10001, max: 50000, rate: 0.008, name: 'growth', discount_eligible: true },
        { min: 50001, max: 100000, rate: 0.006, name: 'business', discount_eligible: true },
        { min: 100001, max: 500000, rate: 0.005, name: 'scale', discount_eligible: true },
        { min: 500001, max: 1000000, rate: 0.004, name: 'enterprise', discount_eligible: true },
        { min: 1000001, max: 5000000, rate: 0.0035, name: 'enterprise_plus', discount_eligible: true },
        { min: 5000001, max: Infinity, rate: 0.003, name: 'custom', discount_eligible: true }
      ],
      storage_gb: [
        { min: 0, max: 100, rate: 0.10, name: 'included', discount_eligible: false },
        { min: 101, max: 1000, rate: 0.08, name: 'standard', discount_eligible: true },
        { min: 1001, max: 10000, rate: 0.06, name: 'premium', discount_eligible: true },
        { min: 10001, max: 100000, rate: 0.05, name: 'enterprise', discount_eligible: true },
        { min: 100001, max: Infinity, rate: 0.04, name: 'enterprise_max', discount_eligible: true }
      ],
      compute_hours: [
        { min: 0, max: 100, rate: 2.00, name: 'basic', discount_eligible: false },
        { min: 101, max: 1000, rate: 1.80, name: 'standard', discount_eligible: true },
        { min: 1001, max: 5000, rate: 1.60, name: 'optimized', discount_eligible: true },
        { min: 5001, max: 20000, rate: 1.50, name: 'scale', discount_eligible: true },
        { min: 20001, max: Infinity, rate: 1.40, name: 'enterprise', discount_eligible: true }
      ],
      bandwidth_gb: [
        { min: 0, max: 1000, rate: 0.12, name: 'starter', discount_eligible: false },
        { min: 1001, max: 10000, rate: 0.10, name: 'growth', discount_eligible: true },
        { min: 10001, max: 100000, rate: 0.08, name: 'business', discount_eligible: true },
        { min: 100001, max: 1000000, rate: 0.06, name: 'enterprise', discount_eligible: true },
        { min: 1000001, max: Infinity, rate: 0.04, name: 'cdn_optimized', discount_eligible: true }
      ]
    };
    
    this.commitmentDiscounts = {
      '1_year': { discount: 0.10, minimum_spend: 10000, bonus_credits: 0.02 },
      '2_year': { discount: 0.18, minimum_spend: 20000, bonus_credits: 0.05 },
      '3_year': { discount: 0.25, minimum_spend: 30000, bonus_credits: 0.08 }
    };
  }
  
  calculateProgressiveUsageCharges(usage, resourceType, commitmentLevel = null, volumeDiscountTier = null) {
    const tiers = this.pricingTiers[resourceType];
    if (!tiers) throw new Error(`Unknown resource type: ${resourceType}`);
    
    let totalCost = 0;
    let remainingUsage = usage;
    const tierBreakdown = [];
    
    for (const tier of tiers) {
      if (remainingUsage <= 0) break;
      
      const tierCapacity = tier.max === Infinity 
        ? remainingUsage 
        : Math.min(remainingUsage, tier.max - tier.min + 1);
      
      const tierUsage = Math.min(remainingUsage, tierCapacity);
      let tierRate = tier.rate;
      
      // Apply commitment discounts to eligible tiers
      if (commitmentLevel && tier.discount_eligible) {
        const commitment = this.commitmentDiscounts[commitmentLevel];
        tierRate = tierRate * (1 - commitment.discount);
      }
      
      // Apply additional volume discounts for high-usage tiers
      if (volumeDiscountTier && tier.min > 500000) {
        const volumeMultiplier = this.getVolumeDiscountMultiplier(volumeDiscountTier);
        tierRate = tierRate * volumeMultiplier;
      }
      
      const tierCost = tierUsage * tierRate;
      totalCost += tierCost;
      
      tierBreakdown.push({
        tier_name: tier.name,
        tier_min: tier.min,
        tier_max: tier.max,
        usage_in_tier: tierUsage,
        base_rate: tier.rate,
        effective_rate: tierRate,
        cost: this.roundToCents(tierCost),
        commitment_discount: commitmentLevel || 'none',
        volume_discount: volumeDiscountTier || 'none'
      });
      
      remainingUsage -= tierUsage;
    }
    
    return {
      total_cost: this.roundToCents(totalCost),
      tier_breakdown: tierBreakdown,
      total_usage: usage,
      resource_type: resourceType,
      effective_blended_rate: usage > 0 ? totalCost / usage : 0
    };
  }
  
  getVolumeDiscountMultiplier(volumeTier) {
    const multipliers = {
      'high_volume': 0.95,     // 5% additional discount
      'enterprise': 0.90,      // 10% additional discount  
      'mega_scale': 0.85       // 15% additional discount
    };
    return multipliers[volumeTier] || 1.0;
  }
  
  // Complex example: 2.5M API calls with 3-year commitment + enterprise volume
  calculateMegaScaleExample() {
    return this.calculateProgressiveUsageCharges(2500000, 'api_calls', '3_year', 'mega_scale');
    /*
    Enhanced Progressive Calculation:
    Tier 1 (0-10k): 10,000 × $0.010 = $100.00 (no discount on starter tier)
    Tier 2 (10k-50k): 40,000 × $0.008 × 0.75 = $240.00 (25% commitment discount)
    Tier 3 (50k-100k): 50,000 × $0.006 × 0.75 = $225.00 
    Tier 4 (100k-500k): 400,000 × $0.005 × 0.75 = $1,500.00
    Tier 5 (500k-1M): 500,000 × $0.004 × 0.75 = $1,500.00
    Tier 6 (1M-5M): 1,500,000 × $0.0035 × 0.75 × 0.85 = $3,328.13 (mega-scale volume discount)
    Total: $6,893.13 vs $17,000 at flat $0.0068/call
    Savings: 59.4%
    */
  }
}
```

### Enhanced Hybrid Billing Model with Cross-Resource Optimization

```javascript
class HybridBillingEngine {
  async calculateComprehensiveBill(tenantId, billingPeriod) {
    const subscription = await this.getActiveSubscription(tenantId);
    const usage = await this.getUsageForPeriod(tenantId, billingPeriod);
    const contract = await this.getContractTerms(tenantId);
    
    // Base subscription components
    let subscriptionFee = subscription.base_price;
    let seatLicenses = subscription.seat_count * subscription.per_seat_price;
    let featurePacks = await this.calculateFeaturePackCharges(subscription.features);
    
    // Cross-resource usage optimization analysis
    const usageProfile = this.analyzeUsageProfile(usage);
    const recommendedCommitmentLevel = this.recommendCommitmentLevel(usageProfile, contract);
    
    // Usage-based charges with progressive tiers and cross-resource discounts
    const apiCharges = this.calculateProgressiveUsageCharges(
      usage.api_calls, 'api_calls', contract?.commitment_term, usageProfile.volume_tier
    );
    
    const storageCharges = this.calculateProgressiveUsageCharges(
      usage.storage_gb, 'storage_gb', contract?.commitment_term, usageProfile.volume_tier
    );
    
    const computeCharges = this.calculateProgressiveUsageCharges(
      usage.compute_hours, 'compute_hours', contract?.commitment_term, usageProfile.volume_tier
    );
    
    const bandwidthCharges = this.calculateProgressiveUsageCharges(
      usage.bandwidth_gb, 'bandwidth_gb', contract?.commitment_term, usageProfile.volume_tier
    );
    
    // Cross-resource bundle discounts for balanced usage
    const bundleDiscount = this.calculateCrossResourceBundleDiscount({
      api: apiCharges.total_cost,
      storage: storageCharges.total_cost,
      compute: computeCharges.total_cost,
      bandwidth: bandwidthCharges.total_cost
    }, usageProfile);
    
    // Aggregate all usage charges
    const totalUsageCharges = apiCharges.total_cost + 
                             storageCharges.total_cost + 
                             computeCharges.total_cost +
                             bandwidthCharges.total_cost;
    
    // Apply hybrid model discounts with tier-based multipliers
    const hybridDiscount = this.calculateEnhancedHybridDiscount(
      subscriptionFee + seatLicenses,
      totalUsageCharges,
      contract,
      usageProfile
    );
    
    // Volume-based discounts on total bill with usage velocity consideration
    const totalBeforeDiscounts = subscriptionFee + seatLicenses + featurePacks + totalUsageCharges;
    const volumeDiscount = this.calculateAdvancedVolumeDiscount(totalBeforeDiscounts, usageProfile);
    
    // Enterprise minimum spend adjustments with commitment credits
    const minimumSpendAdjustment = await this.calculateMinimumSpendAdjustment(
      tenantId, totalBeforeDiscounts, contract
    );
    
    const finalTotal = totalBeforeDiscounts - hybridDiscount - volumeDiscount - bundleDiscount + minimumSpendAdjustment;
    
    return {
      subscription_components: {
        base_fee: subscriptionFee,
        seat_licenses: seatLicenses,
        feature_packs: featurePacks,
        subtotal: subscriptionFee + seatLicenses + featurePacks
      },
      usage_components: {
        api_calls: apiCharges,
        storage: storageCharges,
        compute: computeCharges,
        bandwidth: bandwidthCharges,
        subtotal: totalUsageCharges
      },
      discounts: {
        hybrid_model_discount: hybridDiscount,
        volume_discount: volumeDiscount,
        bundle_discount: bundleDiscount,
        total_discounts: hybridDiscount + volumeDiscount + bundleDiscount
      },
      adjustments: {
        minimum_spend_adjustment: minimumSpendAdjustment
      },
      usage_profile: usageProfile,
      optimization_recommendations: {
        suggested_commitment: recommendedCommitmentLevel,
        potential_annual_savings: this.calculatePotentialSavings(usageProfile, contract),
        bundle_optimization: this.suggestBundleOptimizations(usageProfile)
      },
      totals: {
        gross_amount: totalBeforeDiscounts,
        net_amount: this.roundToCents(finalTotal),
        effective_discount_rate: (totalBeforeDiscounts - finalTotal) / totalBeforeDiscounts,
        blended_usage_rate: totalUsageCharges > 0 ? finalTotal / totalUsageCharges : 0
      },
      period: billingPeriod,
      contract_terms: contract
    };
  }
  
  analyzeUsageProfile(usage) {
    const totalUsageValue = (usage.api_calls * 0.008) + 
                           (usage.storage_gb * 0.08) + 
                           (usage.compute_hours * 1.70) +
                           (usage.bandwidth_gb * 0.10);
    
    const usageBalance = {
      compute_intensive: usage.compute_hours / (usage.api_calls + 1) > 0.01,
      storage_intensive: usage.storage_gb / (usage.api_calls + 1) > 0.1,
      bandwidth_intensive: usage.bandwidth_gb / (usage.api_calls + 1) > 10,
      balanced: true // Calculate balance score
    };
    
    let volumeTier = 'standard';
    if (totalUsageValue > 50000) volumeTier = 'mega_scale';
    else if (totalUsageValue > 15000) volumeTier = 'enterprise';
    else if (totalUsageValue > 5000) volumeTier = 'high_volume';
    
    return {
      total_usage_value: totalUsageValue,
      volume_tier: volumeTier,
      usage_balance: usageBalance,
      growth_trend: this.calculateGrowthTrend(usage),
      efficiency_score: this.calculateEfficiencyScore(usage)
    };
  }
  
  calculateCrossResourceBundleDiscount(costs, usageProfile) {
    const totalCost = Object.values(costs).reduce((sum, cost) => sum + cost, 0);
    
    if (!usageProfile.usage_balance.balanced) return 0;
    
    // Reward balanced usage across all resources
    const resourceUsageCount = Object.values(costs).filter(cost => cost > 100).length;
    
    if (resourceUsageCount >= 3 && totalCost > 5000) {
      return totalCost * 0.05; // 5% bundle discount
    } else if (resourceUsageCount >= 2 && totalCost > 2000) {
      return totalCost * 0.03; // 3% partial bundle discount
    }
    
    return 0;
  }
  
  calculateEnhancedHybridDiscount(subscriptionTotal, usageTotal, contract, usageProfile) {
    if (!contract?.hybrid_discount_tier) return 0;
    
    // Enhanced hybrid model with usage profile consideration
    const hybridTiers = {
      'premium': { 
        threshold: 5000, 
        base_usage_discount: 0.15,
        efficiency_bonus: 0.02
      },
      'enterprise': { 
        threshold: 15000, 
        base_usage_discount: 0.25,
        efficiency_bonus: 0.03
      },
      'custom': { 
        threshold: 50000, 
        base_usage_discount: 0.35,
        efficiency_bonus: 0.05
      }
    };
    
    const tier = hybridTiers[contract.hybrid_discount_tier];
    if (subscriptionTotal >= tier.threshold) {
      let effectiveDiscount = tier.base_usage_discount;
      
      // Bonus for high efficiency usage patterns
      if (usageProfile.efficiency_score > 0.8) {
        effectiveDiscount += tier.efficiency_bonus;
      }
      
      return usageTotal * effectiveDiscount;
    }
    
    return 0;
  }
}
```

### Sophisticated Discount Engine with AI-Driven Optimization

```javascript
class AdvancedDiscountEngine {
  constructor() {
    this.volumeTiers = [
      { min: 0, max: 1000, discount: 0.00, name: 'starter' },
      { min: 1001, max: 5000, discount: 0.03, name: 'growth' },
      { min: 5001, max: 15000, discount: 0.08, name: 'business' },
      { min: 15001, max: 50000, discount: 0.15, name: 'scale' },
      { min: 50001, max: 100000, discount: 0.22, name: 'enterprise' },
      { min: 100001, max: 250000, discount: 0.28, name: 'enterprise_plus' },
      { min: 250001, max: Infinity, discount: 0.30, name: 'custom' }
    ];
    
    this.seasonalPromotions = new Map();
    this.loyaltyPrograms = new Map();
    this.aiOptimizer = new DiscountOptimizationEngine();
  }
  
  async calculateComprehensiveDiscounts(tenantId, billAmount, context = {}) {
    const discounts = [];
    let totalDiscount = 0;
    
    // AI-driven dynamic discount optimization
    const customerProfile = await this.buildCustomerProfile(tenantId);
    const predictedChurn = await this.aiOptimizer.predictChurnRisk(customerProfile);
    const optimalDiscountStrategy = await this.aiOptimizer.optimizeDiscountMix(
      customerProfile, billAmount, predictedChurn
    );
    
    // Volume-based discount with usage velocity consideration
    const volumeDiscount = this.calculateAdvancedVolumeDiscount(billAmount, customerProfile);
    if (volumeDiscount > 0) {
      discounts.push({
        type: 'volume',
        amount: volumeDiscount,
        percentage: volumeDiscount / billAmount,
        description: 'Advanced volume discount with usage velocity bonus',
        ai_optimization_score: optimalDiscountStrategy.volume_score
      });
      totalDiscount += volumeDiscount;
    }
    
    // Enhanced contract commitment discounts with performance bonuses
    const contract = await this.getActiveContract(tenantId);
    if (contract?.commitment_discount) {
      let commitmentDiscount = billAmount * contract.commitment_discount;
      
      // Performance bonus for consistent usage patterns
      if (customerProfile.consistency_score > 0.9) {
        commitmentDiscount *= 1.1; // 10% bonus
      }
      
      discounts.push({
        type: 'commitment',
        amount: commitmentDiscount,
        percentage: commitmentDiscount / billAmount,
        description: `${contract.commitment_term} commitment with consistency bonus`,
        contract_id: contract.id,
        performance_bonus: customerProfile.consistency_score > 0.9
      });
      totalDiscount += commitmentDiscount;
    }
    
    // Enhanced loyalty program with tier-based benefits
    const loyaltyDiscount = await this.calculateAdvancedLoyaltyDiscount(tenantId, billAmount, customerProfile);
    if (loyaltyDiscount > 0) {
      discounts.push({
        type: 'loyalty',
        amount: loyaltyDiscount,
        tier: customerProfile.loyalty_tier,
        tenure_months: customerProfile.tenure_months,
        description: `${customerProfile.loyalty_tier} tier loyalty benefits`
      });
      totalDiscount += loyaltyDiscount;
    }
    
    // Seasonal promotions with customer segment targeting
    const seasonalDiscount = this.calculateTargetedSeasonalDiscount(
      billAmount, context.billingDate, customerProfile
    );
    if (seasonalDiscount > 0) {
      discounts.push({
        type: 'seasonal',
        amount: seasonalDiscount,
        promotion_code: seasonalDiscount.promotion_code,
        description: 'Targeted seasonal promotion',
        segment: customerProfile.customer_segment
      });
      totalDiscount += seasonalDiscount;
    }
    
    // Referral credits with compound benefits
    const referralCredits = await this.applyEnhancedReferralCredits(tenantId, customerProfile);
    if (referralCredits > 0) {
      discounts.push({
        type: 'referral',
        amount: referralCredits,
        referral_count: customerProfile.successful_referrals,
        description: 'Enhanced referral program with compound benefits'
      });
      totalDiscount += referralCredits;
    }
    
    // Apply intelligent discount stacking with AI optimization
    const stackedDiscounts = this.applyIntelligentStackingRules(
      discounts, billAmount, optimalDiscountStrategy
    );
    
    return {
      original_amount: billAmount,
      individual_discounts: discounts,
      stacked_discounts: stackedDiscounts,
      total_discount: stackedDiscounts.reduce((sum, d) => sum + d.final_amount, 0),
      final_amount: billAmount - stackedDiscounts.reduce((sum, d) => sum + d.final_amount, 0),
      discount_percentage: stackedDiscounts.reduce((sum, d) => sum + d.final_amount, 0) / billAmount,
      customer_profile: customerProfile,
      ai_optimization: optimalDiscountStrategy,
      churn_risk_assessment: predictedChurn
    };
  }
  
  async buildCustomerProfile(tenantId) {
    const paymentHistory = await this.getExtendedPaymentHistory(tenantId, 24);
    const usageHistory = await this.getUsageHistory(tenantId, 12);
    const supportInteractions = await this.getSupportMetrics(tenantId, 6);
    
    return {
      tenure_months: paymentHistory.tenure_months,
      payment_reliability: paymentHistory.reliability_score,
      consistency_score: this.calculateConsistencyScore(usageHistory),
      growth_trajectory: this.calculateGrowthTrajectory(usageHistory),
      support_satisfaction: supportInteractions.average_rating,
      loyalty_tier: this.calculateLoyaltyTier(paymentHistory, usageHistory),
      customer_segment: this.identifyCustomerSegment(usageHistory),
      successful_referrals: paymentHistory.referral_count,
      churn_indicators: this.identifyChurnIndicators(usageHistory, supportInteractions)
    };
  }
  
  calculateAdvancedVolumeDiscount(monthlySpend, customerProfile) {
    const baseTier = this.volumeTiers.find(t => 
      monthlySpend >= t.min && monthlySpend <= t.max
    );
    
    if (!baseTier) return 0;
    
    let effectiveDiscount = baseTier.discount;
    
    // Velocity bonus for growing customers
    if (customerProfile.growth_trajectory > 1.2) {
      effectiveDiscount += 0.02; // 2% growth bonus
    }
    
    // Consistency bonus for predictable usage
    if (customerProfile.consistency_score > 0.85) {
      effectiveDiscount += 0.01; // 1% consistency bonus
    }
    
    return this.roundToCents(monthlySpend * effectiveDiscount);
  }
  
  applyIntelligentStackingRules(discounts, billAmount, aiStrategy) {
    // AI-optimized stacking that maximizes customer value while protecting margins
    const stackedDiscounts = [...discounts];
    
    // Priority order based on AI optimization scores
    stackedDiscounts.sort((a, b) => 
      (b.ai_optimization_score || 0) - (a.ai_optimization_score || 0)
    );
    
    // Apply diminishing returns with AI-tuned factors
    return stackedDiscounts.map((discount, index) => {
      const stackingFactor = Math.pow(aiStrategy.stacking_efficiency || 0.8, index);
      const marginalValue = aiStrategy.marginal_value_multipliers?.[discount.type] || 1.0;
      
      return {
        ...discount,
        final_amount: discount.amount * stackingFactor * marginalValue,
        stacking_applied: index > 0,
        stacking_factor: stackingFactor,
        marginal_value_adjustment: marginalValue,
        ai_recommendation: aiStrategy.recommendations?.[discount.type]
      };
    });
  }
}
```

## Financial Compliance & Revenue Recognition

### ASC 606/IFRS 15 Automated Revenue Recognition

```javascript
class RevenueRecognitionEngine {
  constructor(eventStore) {
    this.eventStore = eventStore;
    this.revenueRules = new Map();
    this.journalEntryGenerator = new JournalEntryGenerator();
  }

  async processRevenueEvent(billingEvent) {
    const recognitionRule = await this.determineRecognitionRule(billingEvent);
    const contractIdentification = await this.identifyPerformanceObligations(billingEvent);
    
    // Step 1: Identify the contract
    const contract = await this.getContract(billingEvent.tenant_id);
    
    // Step 2: Identify performance obligations
    const performanceObligations = await this.identifyPerformanceObligations(billingEvent);
    
    // Step 3:
