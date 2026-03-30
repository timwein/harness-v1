## Database Schema and SQL Query for Top 10 Customers by Lifetime Value

### Database Schema

```sql
-- E-commerce database schema optimized for customer lifetime value calculations
-- Designed following Third Normal Form (3NF) principles

-- Customers table: Core customer information
CREATE TABLE customers (
    customer_id BIGINT PRIMARY KEY AUTO_INCREMENT,
    email VARCHAR(255) UNIQUE NOT NULL,
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    phone VARCHAR(20),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

-- Orders table: Order header information
CREATE TABLE orders (
    order_id BIGINT PRIMARY KEY AUTO_INCREMENT,
    customer_id BIGINT NOT NULL,
    order_number VARCHAR(50) UNIQUE NOT NULL,
    order_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status ENUM('pending', 'confirmed', 'shipped', 'delivered', 'cancelled') DEFAULT 'pending',
    currency_code CHAR(3) DEFAULT 'USD',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    FOREIGN KEY (customer_id) REFERENCES customers(customer_id) ON DELETE RESTRICT
);

-- Order items table: Individual items within orders
CREATE TABLE order_items (
    order_item_id BIGINT PRIMARY KEY AUTO_INCREMENT,
    order_id BIGINT NOT NULL,
    product_id BIGINT NOT NULL,
    quantity INT NOT NULL CHECK (quantity > 0),
    unit_price DECIMAL(10,2) NOT NULL CHECK (unit_price >= 0),
    line_total DECIMAL(10,2) NOT NULL CHECK (line_total >= 0),
    
    FOREIGN KEY (order_id) REFERENCES orders(order_id) ON DELETE CASCADE,
    INDEX idx_order_items_order_id (order_id),
    INDEX idx_order_items_product_id (product_id)
);

-- Payments table: All payment transactions (charges and refunds as separate records)
CREATE TABLE payments (
    payment_id BIGINT PRIMARY KEY AUTO_INCREMENT,
    order_id BIGINT NOT NULL,
    customer_id BIGINT NOT NULL,
    payment_type ENUM('charge', 'refund') NOT NULL,
    amount DECIMAL(10,2) NOT NULL CHECK (amount > 0),
    currency_code CHAR(3) DEFAULT 'USD',
    payment_method VARCHAR(50) NOT NULL,
    payment_gateway VARCHAR(50),
    gateway_transaction_id VARCHAR(255),
    payment_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status ENUM('pending', 'completed', 'failed', 'cancelled') DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (order_id) REFERENCES orders(order_id) ON DELETE RESTRICT,
    FOREIGN KEY (customer_id) REFERENCES customers(customer_id) ON DELETE RESTRICT
);

-- Performance optimization indexes
CREATE INDEX idx_orders_customer_id ON orders(customer_id);
CREATE INDEX idx_payments_customer_id_type ON payments(customer_id, payment_type);
CREATE INDEX idx_payments_order_id ON payments(order_id);
CREATE INDEX idx_payments_date ON payments(payment_date);
```

### SQL Query: Top 10 Customers by Lifetime Value

```sql
-- Find the top 10 customers by lifetime value (total charges minus refunds)
-- Uses CTEs for readability and proper null handling

WITH customer_charges AS (
    -- Calculate total charges per customer
    SELECT 
        customer_id,
        COALESCE(SUM(amount), 0) as total_charges
    FROM payments
    WHERE payment_type = 'charge' 
      AND status = 'completed'
    GROUP BY customer_id
),

customer_refunds AS (
    -- Calculate total refunds per customer
    SELECT 
        customer_id,
        COALESCE(SUM(amount), 0) as total_refunds
    FROM payments
    WHERE payment_type = 'refund' 
      AND status = 'completed'
    GROUP BY customer_id
),

customer_lifetime_value AS (
    -- Calculate net lifetime value by combining charges and refunds
    SELECT 
        c.customer_id,
        c.first_name,
        c.last_name,
        c.email,
        COALESCE(charges.total_charges, 0) as total_charges,
        COALESCE(refunds.total_refunds, 0) as total_refunds,
        (COALESCE(charges.total_charges, 0) - COALESCE(refunds.total_refunds, 0)) as lifetime_value
    FROM customers c
    LEFT JOIN customer_charges charges ON c.customer_id = charges.customer_id
    LEFT JOIN customer_refunds refunds ON c.customer_id = refunds.customer_id
    -- Only include customers who have made at least one completed charge
    WHERE charges.total_charges > 0
)

-- Final result: Top 10 customers by lifetime value
SELECT 
    customer_id,
    CONCAT(first_name, ' ', last_name) as customer_name,
    email,
    total_charges,
    total_refunds,
    lifetime_value,
    -- Calculate percentage of charges that were refunded
    CASE 
        WHEN total_charges > 0 THEN 
            ROUND((total_refunds / total_charges) * 100, 2)
        ELSE 0 
    END as refund_percentage
FROM customer_lifetime_value
ORDER BY lifetime_value DESC
LIMIT 10;
```

### Key Design Features

**Schema Normalization**: 
The schema follows Third Normal Form (3NF) principles to eliminate redundancy and ensure data integrity
. 
Each table has proper primary and foreign keys with normalized relationships between customers, orders, order_items, and payments
.

**Refund Modeling**: 
Refunds are modeled as separate payment records with type='refund' rather than negative amounts, following financial transaction best practices
. This approach maintains clear audit trails and simplifies aggregation logic.

**Performance Optimization**: 
The schema includes strategic indexes on foreign key columns and frequently queried fields
, particularly the composite index on `payments(customer_id, payment_type)` which optimizes the lifetime value calculation query.

**Query Design**: The query uses CTEs for readability and employs proper null handling with `COALESCE()` functions to ensure accurate calculations when customers have charges but no refunds, or vice versa. 
The aggregation logic properly handles the separation of charges and refunds before combining them for the final lifetime value calculation
.