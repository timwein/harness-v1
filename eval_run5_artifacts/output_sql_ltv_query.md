# Sql Ltv Query — Final Harness Output

**Task:** Create a SQL query to find the top 10 customers by lifetime value excluding refunds, from a schema you define
**Harness Score:** 24.2 / 36 (67.2%)
**Baseline Score:** 23.5 / 36 (65.2%)
**Lift:** +2.0pp
**Iterations:** 3

---

```sql
-- E-commerce Database Schema
-- Normalized design supporting customer lifetime value analysis

-- Customers table
CREATE TABLE customers (
    customer_id INT PRIMARY KEY AUTO_INCREMENT,
    email VARCHAR(255) UNIQUE NOT NULL,
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    registration_date DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    status ENUM('active', 'inactive', 'suspended') DEFAULT 'active',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

-- Orders table
CREATE TABLE orders (
    order_id INT PRIMARY KEY AUTO_INCREMENT,
    customer_id INT NOT NULL,
    order_date DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    order_status ENUM('pending', 'confirmed', 'shipped', 'delivered', 'cancelled') DEFAULT 'pending',
    total_amount DECIMAL(10,2) NOT NULL,
    currency_code CHAR(3) DEFAULT 'USD',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (customer_id) REFERENCES customers(customer_id),
    INDEX idx_orders_customer_date (customer_id, order_date),
    INDEX idx_orders_date (order_date)
);

-- Order items table (normalized to support multiple items per order)
CREATE TABLE order_items (
    order_item_id INT PRIMARY KEY AUTO_INCREMENT,
    order_id INT NOT NULL,
    product_id INT NOT NULL,
    quantity INT NOT NULL CHECK (quantity > 0),
    unit_price DECIMAL(10,2) NOT NULL,
    line_total DECIMAL(10,2) NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (order_id) REFERENCES orders(order_id),
    INDEX idx_order_items_order (order_id)
);

-- Payments table (separate records for charges and refunds)
CREATE TABLE payments (
    payment_id INT PRIMARY KEY AUTO_INCREMENT,
    customer_id INT NOT NULL,
    order_id INT,
    payment_type ENUM('charge', 'refund') NOT NULL,
    amount DECIMAL(10,2) NOT NULL CHECK (amount > 0),
    payment_method ENUM('credit_card', 'debit_card', 'paypal', 'bank_transfer') NOT NULL,
    payment_date DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    reference_payment_id INT NULL, -- Links refunds to original charges
    status ENUM('pending', 'completed', 'failed', 'cancelled') DEFAULT 'pending',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (customer_id) REFERENCES customers(customer_id),
    FOREIGN KEY (order_id) REFERENCES orders(order_id),
    FOREIGN KEY (reference_payment_id) REFERENCES payments(payment_id),
    -- Performance-optimized composite index for LTV calculations
    INDEX idx_payments_customer_type_amount (customer_id, payment_type, amount),
    INDEX idx_payments_date (payment_date),
    INDEX idx_payments_status (status)
);

-- Query: Top 10 Customers by Lifetime Value (Excluding Refunds)
-- Uses CTEs for clarity and maintainability while ensuring optimal performance

WITH customer_charges AS (
    -- Aggregate all charge amounts per customer
    SELECT 
        customer_id,
        SUM(amount) AS total_charges
    FROM payments 
    WHERE payment_type = 'charge' 
        AND status = 'completed'  -- Only include successful payments
    GROUP BY customer_id
),

customer_refunds AS (
    -- Aggregate all refund amounts per customer
    SELECT 
        customer_id,
        SUM(amount) AS total_refunds
    FROM payments 
    WHERE payment_type = 'refund' 
        AND status = 'completed'  -- Only include processed refunds
    GROUP BY customer_id
),

customer_lifetime_value AS (
    -- Calculate net lifetime value: charges minus refunds
    SELECT 
        c.customer_id,
        c.first_name,
        c.last_name,
        c.email,
        -- Handle customers with charges but no refunds using COALESCE
        COALESCE(ch.total_charges, 0) - COALESCE(r.total_refunds, 0) AS lifetime_value,
        COALESCE(ch.total_charges, 0) AS total_charges,
        COALESCE(r.total_refunds, 0) AS total_refunds
    FROM customers c
    INNER JOIN customer_charges ch ON c.customer_id = ch.customer_id
    LEFT JOIN customer_refunds r ON c.customer_id = r.customer_id
)

-- Final result: Top 10 customers ranked by lifetime value
SELECT 
    customer_id,
    first_name,
    last_name,
    email,
    lifetime_value,
    total_charges,
    total_refunds,
    -- Calculate refund rate as additional insight
    ROUND((total_refunds / total_charges) * 100, 2) AS refund_rate_percent
FROM customer_lifetime_value
WHERE lifetime_value > 0  -- Exclude customers with net negative value
ORDER BY lifetime_value DESC
LIMIT 10;
```

---

*Criterion scores: sql_schema 7.5/10 (75%) | sql_correctness 6.0/12 (50%) | sql_readability 4.7/8 (59%) | sql_performance 6.0/6 (100%)*
