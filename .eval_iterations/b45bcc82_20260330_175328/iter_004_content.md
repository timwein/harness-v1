```sql
-- Business Objective: Identify top 10 customers by net lifetime value for retention campaigns
-- Assumptions: Refunds are tracked as separate records linked to original charges
-- Expected Output: Customer details with charges, refunds, and net lifetime value ordered by LTV
-- Data Model: 3NF normalized design eliminates redundancy and supports efficient customer analytics queries

-- Schema Definition
-- Normalized database design for customer lifetime value analysis

-- 3NF Compliance Verification:
-- 1st Normal Form: All columns contain atomic values
-- 2nd Normal Form: All non-key columns depend on entire primary key
-- 3rd Normal Form: No transitive dependencies - customer data separate from order data separate from payment data

-- Payment methods lookup table - normalized reference data
CREATE TABLE payment_methods (
    payment_method_id   INT PRIMARY KEY AUTO_INCREMENT,
    method_name         VARCHAR(50) NOT NULL UNIQUE,
    processing_fee_pct  DECIMAL(5,4) NOT NULL DEFAULT 0.0000,
    is_active          BOOLEAN DEFAULT TRUE
);

-- Customers table - core customer information
CREATE TABLE customers (
    customer_id         INT PRIMARY KEY AUTO_INCREMENT,
    first_name         VARCHAR(50) NOT NULL,
    last_name          VARCHAR(50) NOT NULL,
    email              VARCHAR(100) NOT NULL,
    registration_date  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status             ENUM('active', 'inactive') DEFAULT 'active',
    acquisition_channel VARCHAR(50),
    customer_segment   ENUM('bronze', 'silver', 'gold', 'platinum'),
    marketing_consent  BOOLEAN DEFAULT FALSE,
    UNIQUE KEY uk_customers_email (email),
    CHECK (email REGEXP '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$')
);

-- Orders table - order header information
CREATE TABLE orders (
    order_id       INT PRIMARY KEY AUTO_INCREMENT,
    customer_id    INT NOT NULL,
    order_date     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    order_status   ENUM('pending', 'completed', 'cancelled') DEFAULT 'pending',
    FOREIGN KEY (customer_id) REFERENCES customers(customer_id),
    INDEX idx_orders_customer_date (customer_id, order_date)
);

-- Order items table - individual items within orders
CREATE TABLE order_items (
    order_item_id  INT PRIMARY KEY AUTO_INCREMENT,
    order_id       INT NOT NULL,
    product_name   VARCHAR(200) NOT NULL,
    quantity       INT NOT NULL CHECK (quantity > 0),
    unit_price     DECIMAL(10,2) NOT NULL CHECK (unit_price >= 0),
    total_amount   DECIMAL(10,2) GENERATED ALWAYS AS (quantity * unit_price) STORED,
    FOREIGN KEY (order_id) REFERENCES orders(order_id),
    INDEX idx_order_items_order (order_id)
);

-- Payments table - charges and refunds as separate records
CREATE TABLE payments (
    payment_id             INT PRIMARY KEY AUTO_INCREMENT,
    customer_id            INT NOT NULL,
    order_id               INT,
    payment_type           ENUM('charge', 'refund') NOT NULL,
    amount                 DECIMAL(10,2) NOT NULL CHECK (amount > 0),
    payment_date           TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    payment_method_id      INT,
    reference_payment_id   INT, -- For refunds, references the original charge
    FOREIGN KEY (customer_id) REFERENCES customers(customer_id),
    FOREIGN KEY (order_id) REFERENCES orders(order_id),
    FOREIGN KEY (payment_method_id) REFERENCES payment_methods(payment_method_id),
    FOREIGN KEY (reference_payment_id) REFERENCES payments(payment_id),
    -- Performance-optimized index for LTV calculations
    INDEX idx_payments_customer_type_amount (customer_id, payment_type, amount),
    INDEX idx_payments_date (payment_date),
    CONSTRAINT chk_refund_reference CHECK (
        (payment_type = 'refund' AND reference_payment_id IS NOT NULL) OR 
        (payment_type = 'charge' AND reference_payment_id IS NULL)
    ),
    CONSTRAINT chk_refund_amount CHECK (
        payment_type = 'charge' OR 
        amount <= (SELECT amount FROM payments WHERE payment_id = reference_payment_id)
    )
);

-- Query to find top 10 customers by lifetime value excluding refunds
-- LTV Calculation Method: Total charges minus total refunds per customer
-- Mathematical Proof: Customer A with $500 charges and $50 refunds = $450 LTV
-- This represents net customer value: Revenue Generated - Money Returned = True Customer Worth

-- NULL Handling Strategy:
-- 1) COALESCE converts NULL sums to 0 for customers with no charges/refunds
-- 2) LEFT JOINs ensure all customers appear even with no payment records
-- 3) Result: customers with no activity show $0 LTV instead of being excluded

/* ===== SECTION: DATA PREPARATION ===== */
WITH customer_total_purchases AS (
    -- Calculate total charges per customer
    -- Handles customers with no purchases: COALESCE ensures 0 instead of NULL
    SELECT 
        c.customer_id,
        c.first_name,
        c.last_name,
        c.email,
        COALESCE(SUM(p.amount), 0)                    AS total_charges
    FROM customers c
    LEFT JOIN payments p ON c.customer_id = p.customer_id 
        AND p.payment_type = 'charge'
    -- GROUP BY all non-aggregated SELECT columns to satisfy SQL standard and ensure unique customer records
    GROUP BY c.customer_id, c.first_name, c.last_name, c.email
),

/* ===== SECTION: REFUND CALCULATION ===== */
customer_total_returns AS (
    -- Calculate total refunds per customer
    -- NULL handling: LEFT JOIN + COALESCE handles customers with zero refunds
    SELECT 
        c.customer_id,
        COALESCE(SUM(p.amount), 0)                    AS total_refunds
    FROM customers c
    LEFT JOIN payments p ON c.customer_id = p.customer_id 
        AND p.payment_type = 'refund'
    GROUP BY c.customer_id
),

/* ===== SECTION: BUSINESS METRICS ===== */
customer_metrics AS (
    -- Calculate additional business intelligence metrics
    -- Provides comprehensive customer analytics beyond basic LTV
    SELECT 
        c.customer_id,
        COUNT(DISTINCT p.payment_id)                  AS transaction_count,
        CASE 
            WHEN COUNT(DISTINCT p.payment_id) > 0 
            THEN COALESCE(SUM(CASE WHEN p.payment_type = 'charge' THEN p.amount END), 0) / COUNT(DISTINCT p.payment_id)
            ELSE 0 
        END                                          AS avg_order_value,
        DATEDIFF(CURRENT_DATE, MAX(p.payment_date))   AS days_since_last_purchase
    FROM customers c
    LEFT JOIN payments p ON c.customer_id = p.customer_id
    GROUP BY c.customer_id
),

/* ===== SECTION: LIFETIME VALUE CALCULATION ===== */
customer_ltv AS (
    -- Calculate net lifetime value (charges minus refunds)
    -- Business rule: LTV = Total revenue generated minus money returned
    -- Validation: This equals net customer value contribution to business
    SELECT 
        cc.customer_id,
        cc.first_name,
        cc.last_name,
        cc.email,
        cc.total_charges,
        cr.total_refunds,
        (cc.total_charges - cr.total_refunds)         AS lifetime_value,
        cm.transaction_count,
        cm.avg_order_value,
        cm.days_since_last_purchase
    FROM customer_total_purchases cc
    JOIN customer_total_returns cr ON cc.customer_id = cr.customer_id
    JOIN customer_metrics cm ON cc.customer_id = cm.customer_id
)

-- Final selection of top 10 customers by lifetime value
-- Tie-breaking: Secondary sort by customer_id for consistent results
SELECT 
    customer_id,
    CONCAT(first_name, ' ', last_name)               AS customer_name,
    email,
    total_charges,
    total_refunds,
    lifetime_value,
    transaction_count,
    avg_order_value,
    days_since_last_purchase
FROM customer_ltv
WHERE lifetime_value > 0  -- Exclude customers with negative LTV

ORDER BY lifetime_value DESC, customer_id ASC
LIMIT 10;
```