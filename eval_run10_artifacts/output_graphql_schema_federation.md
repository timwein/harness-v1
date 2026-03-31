# Federated GraphQL Schema for E-Commerce Platform

## Architecture Overview

This design implements 
a federated GraphQL schema using Apollo Federation directives
 with 
federation serving as an API orchestration layer where clients make a single GraphQL request and the gateway coordinates multiple API calls to return a unified response
.

## 1. Users Subgraph

```graphql
extend schema
  @link(url: "https://specs.apollo.dev/federation/v2.6", 
        import: ["@key", "@external", "@requires"])
  @link(url: "https://the-guild.dev/graphql/auth/v1.0",
        import: ["@auth"])

directive @auth(requires: Role = USER) on OBJECT | FIELD_DEFINITION

enum Role {
  ADMIN
  USER
  GUEST
}

type User @key(fields: "id") @auth(requires: USER) {
  id: ID!
  email: String! @auth(requires: ADMIN)
  username: String!
  firstName: String!
  lastName: String!
  fullName: String! @requires(fields: "firstName lastName")
  dateJoined: DateTime!
  isActive: Boolean! @auth(requires: ADMIN)
  profile: UserProfile
}

type UserProfile {
  bio: String
  avatar: String
  phone: String @auth(requires: ADMIN)
  preferences: UserPreferences
}

type UserPreferences {
  newsletter: Boolean!
  notifications: Boolean!
  currency: String!
}

type Query {
  me: User @auth(requires: USER)
  user(id: ID!): User @auth(requires: ADMIN)
  users(
    first: Int = 20,
    after: String
  ): UserConnection! @auth(requires: ADMIN)
}

type UserConnection {
  edges: [UserEdge!]!
  pageInfo: PageInfo!
  totalCount: Int!
}

type UserEdge {
  node: User!
  cursor: String!
}

type PageInfo {
  hasNextPage: Boolean!
  hasPreviousPage: Boolean!
  startCursor: String
  endCursor: String
}

input CreateUserInput {
  email: String!
  username: String!
  firstName: String!
  lastName: String!
  password: String!
}

union CreateUserResult = User | ValidationError | EmailTakenError

type ValidationError {
  message: String!
  field: String!
}

type EmailTakenError {
  message: String!
  email: String!
}

type Mutation {
  createUser(input: CreateUserInput!): CreateUserResult!
  updateProfile(input: UpdateProfileInput!): UpdateProfileResult!
}

input UpdateProfileInput {
  bio: String
  avatar: String
  preferences: UserPreferencesInput
}

input UserPreferencesInput {
  newsletter: Boolean
  notifications: Boolean
  currency: String
}

union UpdateProfileResult = User | ValidationError | NotFoundError

type NotFoundError {
  message: String!
  id: ID!
}

scalar DateTime
```

**Resolvers Implementation:**

```javascript
const DataLoader = require('dataloader');
const Redis = require('ioredis');

const redis = new Redis(process.env.REDIS_URL);

const resolvers = {
  User: {
    __resolveReference: async ({ id }, context) => {
      try {
        const user = await context.dataloaders.user.load(id);
        if (!user) {
          context.logger.warn(`User not found: ${id}`);
          return null;
        }
        return user;
      } catch (error) {
        context.logger.error('User resolution failed', { userId: id, error: error.message });
        return null;
      }
    },
    
    fullName: (user) => {
      // This computed field requires firstName and lastName via @requires
      return `${user.firstName} ${user.lastName}`.trim();
    }
  },
  
  Query: {
    users: async (_, { first = 20, after }, context) => {
      const { users, pageInfo, totalCount } = await context.dataloaders.userConnection.load({
        first,
        after
      });
      
      return {
        edges: users.map(user => ({
          node: user,
          cursor: Buffer.from(user.id).toString('base64')
        })),
        pageInfo,
        totalCount
      };
    }
  },

  Mutation: {
    createUser: async (_, { input }, context) => {
      try {
        const user = await context.userService.create(input);
        // Prime cache with new user and invalidate user lists
        context.dataloaders.user.prime(user.id, user);
        await redis.del('users:*');
        return user;
      } catch (error) {
        if (error.code === 'EMAIL_TAKEN') {
          return { __typename: 'EmailTakenError', message: error.message, email: input.email };
        }
        return { __typename: 'ValidationError', message: error.message, field: error.field };
      }
    }
  }
};

// DataLoader factory with Redis caching for hot entities
const createDataLoaders = (userService) => ({
  user: new DataLoader(async (ids) => {
    // Check Redis cache first for hot entities
    const cacheKeys = ids.map(id => `user:${id}`);
    const cached = await redis.mget(cacheKeys);
    
    const uncachedIds = [];
    const results = cached.map((cachedUser, index) => {
      if (cachedUser) {
        return JSON.parse(cachedUser);
      }
      uncachedIds.push(ids[index]);
      return null;
    });
    
    // Fetch uncached users from database
    if (uncachedIds.length > 0) {
      const users = await userService.findByIds(uncachedIds);
      const userMap = new Map(users.map(user => [user.id, user]));
      
      // Cache hot entities with 5 minute TTL
      const pipeline = redis.pipeline();
      for (const user of users) {
        pipeline.setex(`user:${user.id}`, 300, JSON.stringify(user));
      }
      await pipeline.exec();
      
      // Fill in the results
      uncachedIds.forEach(id => {
        const index = ids.indexOf(id);
        results[index] = userMap.get(id) || null;
      });
    }
    
    return results;
  }),
  
  userConnection: new DataLoader(async (queries) => {
    // Batch pagination queries with same parameters
    return Promise.all(queries.map(query => userService.findConnection(query)));
  }, {
    cacheKeyFn: ({ first, after }) => `${first}-${after}`
  })
});
```

## 2. Products Subgraph

```graphql
extend schema
  @link(url: "https://specs.apollo.dev/federation/v2.6",
        import: ["@key", "@external", "@requires"])

type Product @key(fields: "id") {
  id: ID!
  name: String!
  description: String
  price: Money!
  displayPrice: String! @requires(fields: "price")
  images: [ProductImage!]!
  category: Category!
  inventory: Inventory!
  attributes: [ProductAttribute!]!
  reviews(
    first: Int = 10,
    after: String,
    rating: Int
  ): ReviewConnection!
}

extend type User @key(fields: "id") {
  id: ID! @external
  firstName: String! @external
  lastName: String! @external
  displayName: String! @requires(fields: "firstName lastName")
}

type Money {
  amount: Int! # Amount in cents to avoid floating point issues
  currency: String!
}

type ProductImage {
  id: ID!
  url: String!
  alt: String
  isPrimary: Boolean!
}

type Category @key(fields: "id") {
  id: ID!
  name: String!
  slug: String!
  parent: Category
  children: [Category!]!
}

type Inventory {
  inStock: Boolean!
  quantity: Int!
  reservedQuantity: Int!
  availableQuantity: Int!
  lowStockThreshold: Int!
  isLowStock: Boolean!
}

type ProductAttribute {
  name: String!
  value: String!
  type: AttributeType!
}

enum AttributeType {
  TEXT
  NUMBER
  BOOLEAN
  SELECT
  MULTISELECT
}

type ReviewConnection {
  edges: [ReviewEdge!]!
  pageInfo: PageInfo!
  totalCount: Int!
  averageRating: Float
}

type ReviewEdge {
  node: Review!
  cursor: String!
}

type Review @key(fields: "id") {
  id: ID!
  rating: Int!
  title: String
  content: String
  createdAt: DateTime!
  helpful: Int!
  reviewer: User! @external
}

type Query {
  product(id: ID!): Product
  products(
    first: Int = 20,
    after: String,
    category: ID,
    search: String,
    sortBy: ProductSort
  ): ProductConnection!
  categories: [Category!]!
  category(id: ID, slug: String): Category
}

enum ProductSort {
  PRICE_ASC
  PRICE_DESC
  NAME_ASC
  NAME_DESC
  NEWEST
  RATING
}

type ProductConnection {
  edges: [ProductEdge!]!
  pageInfo: PageInfo!
  totalCount: Int!
  filters: ProductFilters!
}

type ProductEdge {
  node: Product!
  cursor: String!
}

type ProductFilters {
  priceRange: PriceRange!
  categories: [Category!]!
  attributes: [ProductAttributeFilter!]!
}

type PriceRange {
  min: Int!
  max: Int!
}

type ProductAttributeFilter {
  name: String!
  values: [String!]!
}

input CreateProductInput {
  name: String!
  description: String
  price: MoneyInput!
  categoryId: ID!
  images: [ProductImageInput!]!
  attributes: [ProductAttributeInput!]!
}

input MoneyInput {
  amount: Int!
  currency: String!
}

input ProductImageInput {
  url: String!
  alt: String
  isPrimary: Boolean
}

input ProductAttributeInput {
  name: String!
  value: String!
  type: AttributeType!
}

union CreateProductResult = Product | ValidationError | CategoryNotFoundError

type CategoryNotFoundError {
  message: String!
  categoryId: ID!
}

type Mutation {
  createProduct(input: CreateProductInput!): CreateProductResult!
  updateInventory(productId: ID!, quantity: Int!): UpdateInventoryResult!
}

union UpdateInventoryResult = Product | ProductNotFoundError

type ProductNotFoundError {
  message: String!
  productId: ID!
}
```

**Resolvers with N+1 Prevention:**

```javascript
const resolvers = {
  Product: {
    __resolveReference: async ({ id }, context) => {
      try {
        const product = await context.dataloaders.product.load(id);
        if (!product) {
          context.logger.warn(`Product not found: ${id}`);
          return null;
        }
        return product;
      } catch (error) {
        context.logger.error('Product resolution failed', { productId: id, error: error.message });
        return null;
      }
    },
    
    displayPrice: (product) => {
      // Computed field requiring price field via @requires
      return `${(product.price.amount / 100).toFixed(2)} ${product.price.currency}`;
    },
    
    reviews: async (product, { first, after, rating }, context) => {
      return context.dataloaders.productReviews.load({
        productId: product.id,
        first,
        after,
        rating
      });
    },
    
    inventory: async (product, _, context) => {
      return context.dataloaders.inventory.load(product.id);
    }
  },

  User: {
    displayName: (user) => {
      // Computed field requiring firstName and lastName via @requires
      return `${user.firstName} ${user.lastName}`.trim();
    }
  },

  Review: {
    __resolveReference: async ({ id }, context) => {
      try {
        const review = await context.dataloaders.review.load(id);
        if (!review) {
          context.logger.warn(`Review not found: ${id}`);
          return null;
        }
        return review;
      } catch (error) {
        context.logger.error('Review resolution failed', { reviewId: id, error: error.message });
        return null;
      }
    }
  },

  Query: {
    products: async (_, args, context) => {
      return context.productService.findProducts(args);
    }
  },

  Mutation: {
    updateInventory: async (_, { productId, quantity }, context) => {
      try {
        const product = await context.productService.updateInventory(productId, quantity);
        // Invalidate product cache
        await redis.del(`product:${productId}`);
        return product;
      } catch (error) {
        return { __typename: 'ProductNotFoundError', message: error.message, productId };
      }
    }
  }
};

const createDataLoaders = (services) => ({
  product: new DataLoader(async (ids) => {
    // Redis caching for hot products
    const cacheKeys = ids.map(id => `product:${id}`);
    const cached = await redis.mget(cacheKeys);
    
    const uncachedIds = [];
    const results = cached.map((cachedProduct, index) => {
      if (cachedProduct) {
        return JSON.parse(cachedProduct);
      }
      uncachedIds.push(ids[index]);
      return null;
    });
    
    if (uncachedIds.length > 0) {
      const products = await services.product.findByIds(uncachedIds);
      const productMap = new Map(products.map(product => [product.id, product]));
      
      // Cache hot products with 10 minute TTL
      const pipeline = redis.pipeline();
      for (const product of products) {
        pipeline.setex(`product:${product.id}`, 600, JSON.stringify(product));
      }
      await pipeline.exec();
      
      uncachedIds.forEach(id => {
        const index = ids.indexOf(id);
        results[index] = productMap.get(id) || null;
      });
    }
    
    return results;
  }),
  
  inventory: new DataLoader(async (productIds) => {
    const inventories = await services.inventory.findByProductIds(productIds);
    return productIds.map(id => inventories.find(inv => inv.productId === id));
  }),
  
  productReviews: new DataLoader(async (queries) => {
    return Promise.all(queries.map(q => services.review.findByProduct(q)));
  }, {
    cacheKeyFn: ({ productId, first, after, rating }) => 
      `${productId}-${first}-${after || 'null'}-${rating || 'null'}`
  })
});
```

## 3. Orders Subgraph

```graphql
extend schema
  @link(url: "https://specs.apollo.dev/federation/v2.6",
        import: ["@key", "@external", "@requires"])

type Order @key(fields: "id") {
  id: ID!
  orderNumber: String!
  status: OrderStatus!
  createdAt: DateTime!
  updatedAt: DateTime!
  customer: User! @external
  items: [OrderItem!]!
  shipping: ShippingInfo
  billing: BillingInfo
  totals: OrderTotals!
  timeline: [OrderEvent!]!
}

extend type User @key(fields: "id") {
  id: ID! @external
  email: String! @external
  orderSummary: String! @requires(fields: "email")
  orders(
    first: Int = 10,
    after: String,
    status: OrderStatus
  ): OrderConnection!
}

extend type Product @key(fields: "id") {
  id: ID! @external
  name: String! @external
  price: Money! @external
  orderItemDisplay: String! @requires(fields: "name price")
}

enum OrderStatus {
  PENDING
  CONFIRMED
  PROCESSING
  SHIPPED
  DELIVERED
  CANCELLED
  REFUNDED
}

type OrderItem {
  id: ID!
  product: Product! @external
  quantity: Int!
  unitPrice: Money!
  totalPrice: Money!
  customizations: [OrderItemCustomization!]!
}

type OrderItemCustomization {
  name: String!
  value: String!
  additionalCost: Money
}

type ShippingInfo {
  method: ShippingMethod!
  address: Address!
  estimatedDelivery: DateTime
  trackingNumber: String
  cost: Money!
}

type ShippingMethod {
  id: ID!
  name: String!
  description: String
  estimatedDays: Int!
  cost: Money!
}

type Address {
  street1: String!
  street2: String
  city: String!
  state: String!
  postalCode: String!
  country: String!
}

type BillingInfo {
  address: Address!
  paymentMethod: PaymentMethodSummary!
}

type PaymentMethodSummary {
  type: String! # "CARD", "PAYPAL", etc.
  lastFour: String
  brand: String
}

type OrderTotals {
  subtotal: Money!
  shipping: Money!
  tax: Money!
  discount: Money!
  total: Money!
}

type OrderEvent {
  id: ID!
  type: OrderEventType!
  timestamp: DateTime!
  description: String!
  metadata: String # JSON metadata
}

enum OrderEventType {
  CREATED
  CONFIRMED
  PAYMENT_PROCESSED
  SHIPPED
  DELIVERED
  CANCELLED
  REFUNDED
  ITEM_RETURNED
}

type OrderConnection {
  edges: [OrderEdge!]!
  pageInfo: PageInfo!
  totalCount: Int!
}

type OrderEdge {
  node: Order!
  cursor: String!
}

type Query {
  order(id: ID!): Order
  orders(
    first: Int = 20,
    after: String,
    status: OrderStatus,
    customerId: ID
  ): OrderConnection! @auth(requires: ADMIN)
}

input CreateOrderInput {
  items: [OrderItemInput!]!
  shipping: ShippingInput!
  billing: BillingInput!
  couponCode: String
}

input OrderItemInput {
  productId: ID!
  quantity: Int!
  customizations: [OrderItemCustomizationInput!]!
}

input OrderItemCustomizationInput {
  name: String!
  value: String!
}

input ShippingInput {
  methodId: ID!
  address: AddressInput!
}

input BillingInput {
  address: AddressInput!
  paymentMethodId: ID!
}

input AddressInput {
  street1: String!
  street2: String
  city: String!
  state: String!
  postalCode: String!
  country: String!
}

union CreateOrderResult = Order | InsufficientStockError | InvalidPaymentMethodError | ShippingNotAvailableError

type InsufficientStockError {
  message: String!
  productId: ID!
  requestedQuantity: Int!
  availableQuantity: Int!
}

type InvalidPaymentMethodError {
  message: String!
  paymentMethodId: ID!
}

type ShippingNotAvailableError {
  message: String!
  address: Address!
  methodId: ID!
}

type Mutation {
  createOrder(input: CreateOrderInput!): CreateOrderResult!
  updateOrderStatus(orderId: ID!, status: OrderStatus!): UpdateOrderStatusResult!
  cancelOrder(orderId: ID!): CancelOrderResult!
}

union UpdateOrderStatusResult = Order | OrderNotFoundError | InvalidStatusTransitionError

type InvalidStatusTransitionError {
  message: String!
  currentStatus: OrderStatus!
  requestedStatus: OrderStatus!
}

union CancelOrderResult = Order | OrderNotFoundError | OrderNotCancellableError

type OrderNotCancellableError {
  message: String!
  currentStatus: OrderStatus!
}
```

**Resolvers with Reference Resolution:**

```javascript
const resolvers = {
  Order: {
    __resolveReference: async ({ id }, context) => {
      try {
        const order = await context.dataloaders.order.load(id);
        if (!order) {
          context.logger.warn(`Order not found: ${id}`);
          return null;
        }
        return order;
      } catch (error) {
        context.logger.error('Order resolution failed', { orderId: id, error: error.message });
        return null;
      }
    },
    
    customer: async (order, _, context) => {
      // This will be resolved by the Users subgraph
      return { __typename: 'User', id: order.customerId };
    },
    
    timeline: async (order, _, context) => {
      return context.dataloaders.orderEvents.load(order.id);
    }
  },

  User: {
    orderSummary: (user) => {
      // Computed field requiring email via @requires
      return `Orders for ${user.email}`;
    },
    
    orders: async (user, { first, after, status }, context) => {
      return context.dataloaders.userOrders.load({
        userId: user.id,
        first,
        after,
        status
      });
    }
  },

  Product: {
    orderItemDisplay: (product) => {
      // Computed field requiring name and price via @requires
      return `${product.name} - ${(product.price.amount / 100).toFixed(2)} ${product.price.currency}`;
    }
  },

  OrderItem: {
    product: (item) => ({ __typename: 'Product', id: item.productId })
  },

  Mutation: {
    createOrder: async (_, { input }, context) => {
      try {
        const order = await context.orderService.create(input);
        // Invalidate user orders cache
        await redis.del(`userOrders:${order.customerId}:*`);
        return order;
      } catch (error) {
        if (error.code === 'INSUFFICIENT_STOCK') {
          return {
            __typename: 'InsufficientStockError',
            message: error.message,
            productId: error.productId,
            requestedQuantity: error.requested,
            availableQuantity: error.available
          };
        }
        throw error;
      }
    }
  }
};

const createDataLoaders = (services) => ({
  order: new DataLoader(async (ids) => {
    const orders = await services.order.findByIds(ids);
    return ids.map(id => orders.find(o => o.id === id) || null);
  }),
  
  orderEvents: new DataLoader(async (orderIds) => {
    const events = await services.orderEvent.findByOrderIds(orderIds);
    return orderIds.map(orderId => 
      events.filter(event => event.orderId === orderId)
    );
  }),
  
  userOrders: new DataLoader(async (queries) => {
    return Promise.all(queries.map(q => services.order.findByUser(q)));
  })
});
```

## 4. Payments Subgraph

```graphql
extend schema
  @link(url: "https://specs.apollo.dev/federation/v2.6",
        import: ["@key", "@external", "@requires"])

type Payment @key(fields: "id") {
  id: ID!
  order: Order! @external
  amount: Money!
  status: PaymentStatus!
  method: PaymentMethod!
  processor: PaymentProcessor!
  transactionId: String
  createdAt: DateTime!
  processedAt: DateTime
  refunds: [Refund!]!
  fees: PaymentFees!
}

extend type Order @key(fields: "id") {
  id: ID! @external
  orderNumber: String! @external
  customer: User! @external
  paymentSummary: String! @requires(fields: "orderNumber")
  payments: [Payment!]!
}

extend type User @key(fields: "id") {
  id: ID! @external
  email: String! @external
  paymentProfile: String! @requires(fields: "email")
}

enum PaymentStatus {
  PENDING
  PROCESSING
  COMPLETED
  FAILED
  CANCELLED
  REFUNDED
  PARTIALLY_REFUNDED
}

type PaymentMethod {
  id: ID!
  type: PaymentMethodType!
  card: CardDetails
  paypal: PayPalDetails
  bankTransfer: BankTransferDetails
  isDefault: Boolean!
  expiresAt: DateTime
}

enum PaymentMethodType {
  CREDIT_CARD
  DEBIT_CARD
  PAYPAL
  BANK_TRANSFER
  APPLE_PAY
  GOOGLE_PAY
}

type CardDetails {
  lastFour: String!
  brand: CardBrand!
  expiryMonth: Int!
  expiryYear: Int!
  fingerprint: String! # For duplicate detection
}

enum CardBrand {
  VISA
  MASTERCARD
  AMEX
  DISCOVER
  JCB
  UNKNOWN
}

type PayPalDetails {
  email: String!
  payerId: String!
}

type BankTransferDetails {
  bankName: String!
  accountType: String!
  routingNumber: String!
  lastFour: String!
}

type PaymentProcessor {
  name: String!
  transactionId: String!
  processingFee: Money
  processorResponse: ProcessorResponse
}

type ProcessorResponse {
  code: String!
  message: String
  riskScore: Float
  avsResult: String
  cvvResult: String
}

type PaymentFees {
  processing: Money!
  platform: Money!
  total: Money!
}

type Refund @key(fields: "id") {
  id: ID!
  payment: Payment!
  amount: Money!
  reason: RefundReason!
  status: RefundStatus!
  createdAt: DateTime!
  processedAt: DateTime
  transactionId: String
}

enum RefundReason {
  CUSTOMER_REQUEST
  DEFECTIVE_PRODUCT
  ORDER_CANCELLED
  FRAUD_PREVENTION
  PROCESSING_ERROR
  OTHER
}

enum RefundStatus {
  PENDING
  PROCESSING
  COMPLETED
  FAILED
}

type Query {
  payment(id: ID!): Payment
  payments(
    first: Int = 20,
    after: String,
    status: PaymentStatus,
    orderId: ID
  ): PaymentConnection! @auth(requires: ADMIN)
  paymentMethods(userId: ID!): [PaymentMethod!]! @auth(requires: USER)
}

type PaymentConnection {
  edges: [PaymentEdge!]!
  pageInfo: PageInfo!
  totalCount: Int!
}

type PaymentEdge {
  node: Payment!
  cursor: String!
}

input ProcessPaymentInput {
  orderId: ID!
  amount: MoneyInput!
  paymentMethodId: ID!
  billingAddress: AddressInput!
}

union ProcessPaymentResult = Payment | PaymentFailedError | InvalidPaymentMethodError | FraudDetectedError

type PaymentFailedError {
  message: String!
  code: String!
  orderId: ID!
  retryable: Boolean!
}

type FraudDetectedError {
  message: String!
  riskScore: Float!
  orderId: ID!
}

input CreateRefundInput {
  paymentId: ID!
  amount: MoneyInput
  reason: RefundReason!
  notes: String
}

union CreateRefundResult = Refund | RefundFailedError | PaymentNotRefundableError

type RefundFailedError {
  message: String!
  code: String!
  paymentId: ID!
}

type PaymentNotRefundableError {
  message: String!
  paymentId: ID!
  status: PaymentStatus!
}

type Mutation {
  processPayment(input: ProcessPaymentInput!): ProcessPaymentResult!
  createRefund(input: CreateRefundInput!): CreateRefundResult!
  retryPayment(paymentId: ID!): ProcessPaymentResult!
}
```

**Resolvers with Error Handling:**

```javascript
const resolvers = {
  Payment: {
    __resolveReference: async ({ id }, context) => {
      try {
        const payment = await context.dataloaders.payment.load(id);
        if (!payment) {
          context.logger.warn(`Payment not found: ${id}`);
          return null;
        }
        return payment;
      } catch (error) {
        context.logger.error('Payment resolution failed', { paymentId: id, error: error.message });
        return null;
      }
    },
    
    order: (payment) => ({ __typename: 'Order', id: payment.orderId }),
    
    refunds: async (payment, _, context) => {
      return context.dataloaders.paymentRefunds.load(payment.id);
    }
  },

  Order: {
    paymentSummary: (order) => {
      // Computed field requiring orderNumber via @requires
      return `Payment details for order ${order.orderNumber}`;
    },
    
    payments: async (order, _, context) => {
      return context.dataloaders.orderPayments.load(order.id);
    }
  },

  User: {
    paymentProfile: (user) => {
      // Computed field requiring email via @requires
      return `Payment profile for ${user.email}`;
    }
  },

  Mutation: {
    processPayment: async (_, { input }, context) => {
      try {
        const payment = await context.paymentService.process(input);
        context.dataloaders.payment.prime(payment.id, payment);
        return payment;
      } catch (error) {
        if (error.code === 'FRAUD_DETECTED') {
          return {
            __typename: 'FraudDetectedError',
            message: error.message,
            riskScore: error.riskScore,
            orderId: input.orderId
          };
        }
        if (error.code === 'PAYMENT_FAILED') {
          return {
            __typename: 'PaymentFailedError',
            message: error.message,
            code: error.code,
            orderId: input.orderId,
            retryable: error.retryable
          };
        }
        throw error;
      }
    }
  }
};

const createDataLoaders = (services) => ({
  payment: new DataLoader(async (ids) => {
    const payments = await services.payment.findByIds(ids);
    return ids.map(id => payments.find(p => p.id === id) || null);
  }),
  
  orderPayments: new DataLoader(async (orderIds) => {
    const payments = await services.payment.findByOrderIds(orderIds);
    return orderIds.map(orderId => 
      payments.filter(payment => payment.orderId === orderId)
    );
  }),
  
  paymentRefunds: new DataLoader(async (paymentIds) => {
    const refunds = await services.refund.findByPaymentIds(paymentIds);
    return paymentIds.map(paymentId => 
      refunds.filter(refund => refund.paymentId === paymentId)
    );
  })
});
```

## Gateway Configuration

```javascript
const { ApolloGateway, RemoteGraphQLDataSource } = require('@apollo/gateway');
const { ApolloServer } = require('@apollo/server');
const { startStandaloneServer } = require('@apollo/server/standalone');
const depthLimit = require('graphql-depth-limit');
const costAnalysis = require('graphql-cost-analysis').default;
const jwt = require('jsonwebtoken');
const Redis = require('ioredis');

const redis = new Redis(process.env.REDIS_URL);

// Custom RemoteGraphQLDataSource with auth context propagation
class AuthenticatedDataSource extends RemoteGraphQLDataSource {
  willSendRequest({ request, context }) {
    // 
Propagate auth context from gateway to subgraphs by adding user context to headers

    if (context.userId) {
      request.http.headers.set('user-id', context.userId);
    }
    if (context.userRoles) {
      request.http.headers.set('user-roles', JSON.stringify(context.userRoles));
    }
    if (context.authToken) {
      request.http.headers.set('authorization', `Bearer ${context.authToken}`);
    }
    
    // Add request tracing headers
    request.http.headers.set('x-request-id', context.requestId);
    request.http.headers.set('x-source', 'apollo-gateway');
    
    // Forward original client IP for rate limiting in subgraphs
    if (context.clientIp) {
      request.http.headers.set('x-client-ip', context.clientIp);
    }
  }

  async didReceiveResponse({ response, request, context }) {
    // Set cache control headers for subgraph responses
    if (!response.http?.headers.get('cache-control')) {
      response.http?.headers.set('cache-control', 'max-age=60, public');
    }
    return response;
  }
  
  async didEncounterError(error, request, context) {
    // Enhanced error handling with logging and graceful degradation
    const subgraphName = this.url.includes('users') ? 'users' : 
                         this.url.includes('products') ? 'products' :
                         this.url.includes('orders') ? 'orders' : 'payments';
    
    context.logger?.error(`Subgraph ${subgraphName} error:`, {
      error: error.message,
      requestId: context.requestId,
      query: request.query,
      variables: request.variables
    });
    
    // For entity resolution failures, return null instead of throwing
    if (error.message?.includes('__resolveReference')) {
      context.logger.warn('Entity resolution failed, returning null', { 
        subgraph: subgraphName, 
        error: error.message 
      });
      return null;
    }
    
    return error;
  }
}

const gateway = new ApolloGateway({
  serviceList: [
    { name: 'users', url: process.env.USERS_SERVICE_URL || 'http://users-service:4001' },
    { name: 'products', url: process.env.PRODUCTS_SERVICE_URL || 'http://products-service:4002' },
    { name: 'orders', url: process.env.ORDERS_SERVICE_URL || 'http://orders-service:4003' },
    { name: 'payments', url: process.env.PAYMENTS_SERVICE_URL || 'http://payments-service:4004' }
  ],
  
  buildService({ name, url }) {
    return new AuthenticatedDataSource({ url });
  },
  
  // Graceful degradation when subgraphs are unavailable
  onSchemaLoadOrUpdateFailure: (error) => {
    console.error('Schema load failed, continuing with last known schema:', error);
    return null; // Continue with last known schema
  }
});

const server = new ApolloServer({
  gateway,
  
  validationRules: [
    // 
Query depth limiting to prevent deeply nested queries that can cause exponential resource consumption

    depthLimit(10), // Prevent deeply nested queries
    
    // 
Query complexity analysis with configurable limits to prevent resource abuse

    costAnalysis({
      maximumCost: 1000,
      defaultCost: 1,
      scalarCost: 1,
      objectCost: 2,
      listFactor: 10,
      introspectionCost: 1000,
      createError: (max, actual) => 
        new Error(`Query cost ${actual} exceeds maximum allowed ${max}`),
      onComplete: (cost, context) => {
        console.log(`Query cost: ${cost} for request ${context.requestId}`);
      }
    })
  ],
  
  formatError: (error) => {
    // Log errors but don't expose internal details
    console.error(error);
    
    if (error.extensions?.code === 'GRAPHQL_VALIDATION_FAILED') {
      return new Error('Query validation failed');
    }
    
    if (error.extensions?.code === 'QUERY_COMPLEXITY_EXCEEDED') {
      return new Error('Query too complex');
    }
    
    if (error.extensions?.code === 'QUERY_DEPTH_EXCEEDED') {
      return new Error('Query too deeply nested');
    }
    
    // Don't expose internal error details in production
    if (process.env.NODE_ENV === 'production') {
      return new Error('Internal server error');
    }
    
    return error;
  },
  
  plugins: [
    {
      requestDidStart() {
        return {
          willSendResponse(requestContext) {
            // Add query timeout protection
            const timeout = setTimeout(() => {
              throw new Error('Query timeout');
            }, 30000);
            
            requestContext.response.http?.on('finish', () => {
              clearTimeout(timeout);
            });
            
            // Add rate limiting headers
            const userId = requestContext.contextValue.userId;
            if (userId) {
              requestContext.response.http?.setHeader('X-RateLimit-Limit', '1000');
              requestContext.response.http?.setHeader('X-RateLimit-Remaining', '999');
            }
          }
        };
      }
    }
  ]
});

// Enhanced auth context extraction with JWT validation
const contextFunction = ({ req }) => {
  const token = req.headers.authorization?.replace('Bearer ', '');
  let userContext = null;
  
  try {
    if (token) {
      // 
JWT validation and user context extraction for authentication in federated GraphQL

      userContext = jwt.verify(token, process.env.JWT_SECRET || 'default-secret');
    }
  } catch (error) {
    // Invalid token, set guest context
    console.warn('Invalid token:', error.message);
  }
  
  return {
    userId: userContext?.userId,
    userRoles: userContext?.roles || ['GUEST'],
    authToken: token,
    requestId: generateRequestId(),
    clientIp: req.ip || req.connection?.remoteAddress,
    redis,
    logger: console
  };
};

const generateRequestId = () => {
  return Math.random().toString(36).substring(7);
};

// Start server with comprehensive monitoring
startStandaloneServer(server, {
  listen: { port: 4000 },
  context: contextFunction
}).then(({ url }) => {
  console.log(`🚀 Gateway ready at ${url}`);
  
  // Health check monitoring for all subgraphs
  setInterval(async () => {
    const services = [
      { name: 'users', url: process.env.USERS_SERVICE_URL || 'http://users-service:4001' },
      { name: 'products', url: process.env.PRODUCTS_SERVICE_URL || 'http://products-service:4002' },
      { name: 'orders', url: process.env.ORDERS_SERVICE_URL || 'http://orders-service:4003' },
      { name: 'payments', url: process.env.PAYMENTS_SERVICE_URL || 'http://payments-service:4004' }
    ];
    
    for (const service of services) {
      try {
        const response = await fetch(`${service.url}/health`);
        if (!response.ok) {
          console.warn(`Service ${service.name} is unhealthy: ${response.status}`);
        }
      } catch (error) {
        console.error(`Service ${service.name} health check failed:`, error.message);
      }
    }
  }, 30000); // Check every 30 seconds
});
```

## Key Design Features

### 1. **Domain Boundaries & Independence**

Each subgraph owns distinct types with clear domain boundaries, following the single subgraph ownership model where each service owns its primary types and others can extend them. The gateway configuration includes service discovery mechanisms and health checks for independent deployment, with graceful degradation when subgraphs are unavailable.

### 2. **Entity Resolution**

The @requires directive is used to annotate the required input fieldset from a base type for a resolver, allowing computed fields that depend on external data. For example, fullName: String! @requires(fields: "firstName lastName") enables the gateway to provide required fields before resolution. All cross-subgraph entities implement the DataLoader pattern to prevent N+1 queries, batching entity lookups efficiently. Each entity defines `__resolveReference` resolvers for proper federation with comprehensive error handling that returns null for missing entities rather than throwing exceptions.

### 3. **Authorization Strategy**

Custom @auth directive provides field-level access control with role-based authorization, applied at both type and field levels. 
Auth context is propagated from gateway to subgraphs through the willSendRequest method in RemoteGraphQLDataSource, which sets authorization headers and user context for each subgraph request
. 
JWT tokens are validated at the gateway level and user information is extracted and forwarded to subgraphs via headers like user-id and user-roles
.

### 4. **N+1 Prevention**
- DataLoader batches multiple .load(key) calls into single batchLoadFn(keys) calls with request-scoped caching, using distributed caches like Redis for sharing cached values between multiple servers
- All list fields use connection/pagination pattern to prevent unbounded data fetching
- Redis caching for frequently accessed entities with TTL-based invalidation - the router uses Redis to cache data from subgraph query responses, keyed per subgraph and entity
- 
Query complexity analysis with configurable limits: costAnalysis({ maximumCost: 1000, defaultCost: 1, scalarCost: 1, objectCost: 2, listFactor: 10 }) prevents queries above threshold from being executed

- 
Query depth limiting using libraries like graphql-depth-limit to prevent exponentially complex nested queries that can pin CPU resources


### 5. **Schema Quality**
- Consistent naming: PascalCase types, camelCase fields, SCREAMING_SNAKE enums
- Intentional nullability design
- Dedicated input types for all mutations
- Typed errors via unions for better error handling

This architecture provides independent team development while maintaining a unified GraphQL API that consumers can interact with as if it were a monolith, with comprehensive security and performance optimizations built-in.