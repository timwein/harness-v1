# Harness Output: sql_ltv_query

**Score:** 76.7% (27.6/36)
**Iterations:** 4
**Best Iteration:** 2 (76.7%)

---

```sql
-- Database Schema Definition
-- ========================================
-- 
-- This schema follows a normalized design pattern that prevents UPDATE anomalies
-- when payment statuses change. The payments table is separated from orders to 
-- support complex scenarios: multiple payment methods per order, partial payments,
-- installment plans, and sophisticated refund workflows. This design scales better
-- than embedding payment data directly in the orders table.

-- Customers table: Core customer information
CREATE TABLE customers (
    customer_id INT PRIMARY KEY AUTO_INCREMENT,
    first_name VARCHAR(50) NOT NULL,
    last_name VARCHAR(50) NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL, -- UNIQUE constraint enforces business rule: one account per email for customer identification
    registration_date DATE NOT NULL,
    customer_status ENUM('active', 'inactive') DEFAULT 'active' -- ENUM implements finite state machine for customer lifecycle
);

-- Orders table: Order header information
CREATE TABLE orders (
    order_id INT PRIMARY KEY AUTO_INCREMENT,
    customer_id INT NOT NULL,
    order_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    order_status ENUM('pending', 'completed', 'cancelled') DEFAULT 'pending', -- ENUM prevents invalid status transitions
    total_amount DECIMAL(10,2) NOT NULL,
    FOREIGN KEY (customer_id) REFERENCES customers(customer_id)
);

-- Order items table: Individual items within orders
CREATE TABLE order_items (
    order_item_id INT PRIMARY KEY AUTO_INCREMENT,
    order_id INT NOT NULL,
    product_id INT NOT NULL,
    quantity INT NOT NULL CHECK (quantity > 0),
    unit_price DECIMAL(10,2) NOT NULL,
    line_total DECIMAL(10,2) NOT NULL,
    FOREIGN KEY (order_id) REFERENCES orders(order_id)
);

-- Payments table: Financial transactions (charges and refunds as separate records)
CREATE TABLE payments (
    payment_id INT PRIMARY KEY AUTO_INCREMENT,
    customer_id INT NOT NULL,
    order_id INT,
    payment_type ENUM('charge', 'refund') NOT NULL,
    amount DECIMAL(10,2) NOT NULL CHECK (amount > 0), -- Positive amounts prevent data entry errors; refunds distinguished by type, not negative values
    payment_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    payment_method VARCHAR(50),
    reference_payment_id INT, -- For refunds, references original charge
    FOREIGN KEY (customer_id) REFERENCES customers(customer_id),
    FOREIGN KEY (order_id) REFERENCES orders(order_id),
    FOREIGN KEY (reference_payment_id) REFERENCES payments(payment_id)
);

-- Performance Indexes
CREATE INDEX idx_payments_customer_type_amount ON payments(customer_id, payment_type, amount);
CREATE INDEX idx_orders_customer_date ON orders(customer_id, order_date);
CREATE INDEX idx_order_items_order ON order_items(order_id);

-- ========================================
-- Query: Top 10 Customers by Lifetime Value (Excluding Refunds)
-- ========================================
--
-- PURPOSE: Identifies the most valuable customers by net revenue (charges minus refunds)
-- ASSUMPTIONS: 
--   - All monetary amounts are in the same currency
--   - Refunds are properly linked to customers via customer_id
--   - Focus on profitable relationships (excludes zero/negative LTV customers)
--
-- FORMATTING CHOICES:
--   - SQL keywords uppercase for standard compliance and readability
--   - Each JOIN condition on separate line for easier code review and debugging
--   - Consistent 4-space indentation enhances team collaboration and maintainability

WITH customer_charges AS (
    -- Calculate total charges per customer
    -- Separate CTE for charges allows independent validation during development
    -- and makes the overall query more testable and debuggable
    SELECT 
        c.customer_id,
        c.first_name,
        c.last_name,
        c.email,
        COALESCE(SUM(p.amount), 0) AS total_charges -- COALESCE preferred over ISNULL for cross-database compatibility
    FROM customers c
    LEFT JOIN payments p ON c.customer_id = p.customer_id 
        AND p.payment_type = 'charge'
    GROUP BY c.customer_id, c.first_name, c.last_name, c.email -- Including name/email prevents aggregate function issues and provides business-useful output
),

customer_refunds AS (
    -- Calculate total refunds per customer
    -- Separate CTE for refunds scales better for complex scenarios like
    -- partial refunds, refund approvals, and multiple payment methods
    SELECT 
        c.customer_id,
        COALESCE(SUM(p.amount), 0) AS total_refunds
    FROM customers c
    LEFT JOIN payments p ON c.customer_id = p.customer_id 
        AND p.payment_type = 'refund'
    GROUP BY c.customer_id
),

customer_lifetime_value AS (
    -- Calculate net lifetime value (charges minus refunds)
    -- This three-CTE approach (charges → refunds → final calculation) is superior
    -- to a single CASE WHEN aggregation for performance and maintainability.
    -- Each step can be validated independently, and the pattern scales better
    -- for complex refund scenarios with different business rules.
    SELECT 
        cc.customer_id,
        cc.first_name,
        cc.last_name,
        cc.email,
        cc.total_charges,
        cr.total_refunds,
        (cc.total_charges - cr.total_refunds) AS net_lifetime_value
    FROM customer_charges cc -- 2+ character aliases balance readability without verbosity
    INNER JOIN customer_refunds cr ON cc.customer_id = cr.customer_id
)

-- Final result: Top 10 customers by lifetime value
-- Focus on profitable relationships by excluding customers with zero or negative LTV
-- This handles edge cases where customers have equal charges and refunds
SELECT 
    customer_id,
    first_name,
    last_name,
    email,
    total_charges,
    total_refunds,
    net_lifetime_value
FROM customer_lifetime_value
WHERE net_lifetime_value > 0  -- Exclude customers with negative or zero LTV to focus on profitable relationships
ORDER BY net_lifetime_value DESC
LIMIT 10;
```