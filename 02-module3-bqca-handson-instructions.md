# Module 3 Lab Guide: Building & Configuring the BigQuery Conversational Data Agent

---

## 📋 Pre-Flight Environment Context

Your landing zone has already been bootstrapped with baseline data assets via Module 0 infrastructure:
- **Google Cloud Project:** `<PROJECT_ID>`
- **BigQuery Datasets & Tables:**
  - `cymbal_gold` (Structured Gold Serving Layer):
    - `pos_transactions_gold` (Real-time intraday POS checkout ledger)
    - `pos_anomaly_alerts` (Real-time anomaly & promo abuse alert ledger)
    - `gold_inventory_reconciliation_ledger` (Daily reconciled store inventory & burn-rate ledger)
    - `historical_transactional_data` (Historical customer transaction ledger)
  - `module1_unstructureddata` (Extracted Unstructured Document Layer):
    - `warranty_generic_sections_extracted` (AI-extracted warranty terms & conditions)
  - `cymbal-lakehouse.elevate_data` (Cross-Cloud AWS S3 BigLake Federated Layer):
    - `silver_pos_transactions` (Cross-cloud AWS S3 checkout ledger)
- **GCP Region:** `<REGION>` (Ensure you select **'global'**).
- **Dataplex Knowledge Catalog:** Pre-populated enterprise glossary catalog (`cymbal-retail-glossary`).

> [!IMPORTANT]
> **Project Parameterization:** Always replace `<PROJECT_ID>` with your assigned GCP Project ID in your SQL queries. Do not alter dataset names (`cymbal_gold`, `module1_unstructureddata`, `cymbal-lakehouse.elevate_data`) or table names.

> [!WARNING]
> **Data Agent Location Override Requirement (mTLS Error Mitigation):**  
> Even if your BigQuery datasets (`cymbal_gold`, `module1_unstructureddata`) and tables are created in `us-central1`, you **MUST create your BigQuery Conversational Data Agent (BQ CA Agent) with `global` as the location** by overriding the default location setting in the BigQuery Studio UI.  
> *Why?* Creating your Data Agent with `global` location (`projects/<PROJECT_ID>/locations/global/dataAgents/<DATA_AGENT_ID>`) ensures seamless API routing and completely avoids mTLS / SSL certificate errors associated with regional endpoint routing.

---

## 🏷️ Part 1: Provisioning & Data Asset Scope

### Challenge 1.1: Provision the BigQuery Conversational Data Agent

#### 🎯 Objective
Create and scope the **`Cymbal Retail Analytics Data Agent`** in BigQuery Studio to enable natural language querying across conformed retail datasets and federated AWS S3 tables.

#### ⚙️ Requirements & Constraints
1. **Agent Display Name:** Set the agent name strictly to `Cymbal Retail Analytics Data Agent`.
2. **Resource Location:** Set the location explicitly to **`global`** (overriding the default regional location setting in the BigQuery Studio UI to ensure standard global endpoint routing and avoid mTLS certificate errors).
3. **Data Asset Scope:** Scope the agent to the 6 conformed & federated tables:
   - `<PROJECT_ID>.cymbal_gold.pos_transactions_gold` (Real-time intraday POS checkout ledger)
   - `<PROJECT_ID>.cymbal_gold.pos_anomaly_alerts` (Real-time anomaly & promo abuse alert ledger)
   - `<PROJECT_ID>.cymbal_gold.gold_inventory_reconciliation_ledger` (Daily reconciled store inventory & burn-rate ledger)
   - `<PROJECT_ID>.cymbal_gold.historical_transactional_data` (Historical customer transaction ledger)
   - `<PROJECT_ID>.module1_unstructureddata.warranty_generic_sections_extracted` (AI-extracted warranty terms & conditions)
   - `<PROJECT_ID>.cymbal-lakehouse.elevate_data.silver_pos_transactions` (Cross-cloud AWS S3 checkout ledger)

#### 💡 Hints & Clues
- Open **BigQuery Studio** -> **Data Agents** -> **+ Create Data Agent**.

- Ensure you select all 3 datasets (`cymbal_gold`, `module1_unstructureddata`, `cymbal-lakehouse.elevate_data`) under **Data Assets Scope**.
- If you omit `cymbal-lakehouse.elevate_data`, the Data Agent will be unable to discover the cross-cloud AWS S3 schema.
- **Important Location Selection:** Under **Location**, override the default regional dropdown and explicitly select **`global`**.

#### 🚀 Successfully Executed Steps & Evidence (Lab Completed)
- **Target Project:** `xiaoyj-lab` | **Resource Location:** `global` (configured globally to avoid regional endpoint mTLS routing collisions)
- **Agent Resource Name & ID:** `projects/xiaoyj-lab/locations/global/dataAgents/cymbal-retail-analytics`
- **Agent Display Name:** `Cymbal Retail Analytics Data Agent`
- **Data Assets Scoped (6 Tables across 3 Layers):**
  1. `xiaoyj-lab.cymbal_gold.pos_transactions_gold` (Real-time intraday POS checkout ledger)
  2. `xiaoyj-lab.cymbal_gold.pos_anomaly_alerts` (Real-time anomaly & promo abuse alert ledger)
  3. `xiaoyj-lab.cymbal_gold.gold_inventory_reconciliation_ledger` (Daily reconciled store inventory & burn-rate ledger)
  4. `xiaoyj-lab.cymbal_gold.historical_transactional_data` (Historical customer transaction ledger)
  5. `xiaoyj-lab.module1_unstructureddata.warranty_generic_sections_extracted` (AI-extracted warranty terms & conditions)
  6. `xiaoyj-lab.cymbal-lakehouse.elevate_data.silver_pos_transactions` (Cross-cloud AWS S3 Iceberg BigLake federated table)
- **API Verification Evidence:**
  ```json
  {
    "name": "projects/xiaoyj-lab/locations/global/dataAgents/cymbal-retail-analytics",
    "displayName": "Cymbal Retail Analytics Data Agent",
    "hasStaging": true,
    "hasPublished": true,
    "tableCount": 6
  }
  ```

---

## 🏷️ Part 2: Governance & System Instructions Configuration

### Challenge 2.1: Configure Intent-Driven System Instructions

#### 🎯 Objective
Write and configure intent-driven system instructions in your Data Agent to govern table selection, warranty claim triage logic, cross-cloud audit workflows, and partition guardrails.

#### ⚙️ Requirements & Constraints
Your system instructions must include 5 core sections:
1. **Role & Scope:** Identify as the relational analytical data agent operating strictly over `cymbal_gold`, `module1_unstructureddata`, and `cymbal-lakehouse.elevate_data`.
2. **Table Selection Matrix:** Map user intent to tables:
   - Intraday sales checkouts -> `pos_transactions_gold` (`business_date = CURRENT_DATE()`).
   - Past purchase lookup & warranty claims -> `historical_transactional_data` (unnesting `tx.items`).
   - Cashier promo abuse audits -> `pos_anomaly_alerts` (defaulting to last 7 days unless specified).
   - Cross-cloud offender checkout log -> `cymbal-lakehouse.elevate_data.silver_pos_transactions`.
   - Store inventory & cover hours -> `gold_inventory_reconciliation_ledger` (filtering `< 20` cover hours ONLY when stockout risk is requested).
   - Warranty policy terms -> `warranty_generic_sections_extracted`.
3. **Warranty Triage Methodology (UC 2.1):** 3-step logic: query purchase fact -> join policy terms ON `item_id = product_id` -> calculate `DATE_DIFF(CURRENT_DATE(), business_date, MONTH)`.
4. **Cross-Cloud Audit Methodology (UC 2.3):** Step 1: Rank top promo abuse offender in GCP `pos_anomaly_alerts`. Step 2: Query offender transactions directly in AWS S3 `silver_pos_transactions`.
5. **Governance Standards:** Enforce READ-ONLY access and session isolation.
6. **Result Set Limiting & Ranking:** Append `LIMIT 20` to multi-row list queries, ordering by revenue (`intraday_gross_revenue_usd DESC`), risk (`risk_score DESC`), or cover hours (`est_cover_hours_remaining ASC`).

#### 💡 Hints & Clues
- System instructions guide the LLM's query generation strategy. Frame rules around **methodologies** (e.g. *"Join purchase facts with policy terms and calculate elapsed warranty months"*) rather than hardcoding exact filter constants into general routing rules.

#### 🚀 Successfully Executed Steps & Evidence (Lab Completed)
- **Configured System Instructions:** Formulated and deployed intent-driven system instructions covering all 5 core governance sections:
  1. **Role & Scope:** Explicitly restricted data agent scope to `xiaoyj-lab.cymbal_gold`, `xiaoyj-lab.module1_unstructureddata`, and `xiaoyj-lab.cymbal-lakehouse.elevate_data`.
  2. **Table Selection Matrix:** Mapped user analytical intents to target tables, partition filters (`business_date = CURRENT_DATE()`), dynamic lookback windows (`alert_ts >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 7 DAY)`), and repeated array unnesting (`UNNEST(tx.items)`).
  3. **Warranty Triage Methodology (UC 2.1):** Grounded multi-step join pattern: unnest purchase facts -> join policy terms ON `item.item_id = warr.product_id` -> calculate `DATE_DIFF(CURRENT_DATE(), tx.business_date, MONTH) <= warr.warranty_duration_months`.
  4. **Cross-Cloud Audit Methodology (UC 2.3):** Two-phase workflow: Step 1 anomaly ranking in GCP `pos_anomaly_alerts` -> Step 2 external checkout query in federated AWS S3 `silver_pos_transactions`.
  5. **Governance Standards & Limiting:** Strict READ-ONLY GoogleSQL execution, session isolation, and default `LIMIT 20` with multi-tier ordering (`intraday_gross_revenue_usd DESC`, `risk_score DESC`, `est_cover_hours_remaining ASC`).

---

## 🏷️ Part 3: High-Performance Golden Queries Registration

### Challenge 3.1: Register Verified Golden Queries

#### 🎯 Objective
Formulate and register **at least 5 verified GoogleSQL queries** in the Data Agent UI to enable NL2SQL matching for key operational prompts. Attendees are encouraged to construct additional Golden Queries for other business questions.

#### ⚙️ Requirements & Constraints
Construct and register Golden Queries for **at least the 5 core business prompts below** (plus any additional queries you wish to add):

#### **Prompt 1 (UC 1.2 Store Inventory Stockout Analysis)**
* **Natural Language Prompt:**  
  > *"What is the estimated cover hours remaining for store inventory positions experiencing stockout risk of less than 20 hours, and what is their total on-hand inventory?"*
* 💡 **Clue-Based Hint:**  
  Inspect table `gold_inventory_reconciliation_ledger`. Combine shelf and backroom unit columns to derive total on-hand units. Filter for items with elevated stockout risk and order by intraday gross revenue.

---

#### **Prompt 2A (UC 2.1 Past Warranty Lookup by Transaction ID)**
* **Natural Language Prompt:**  
  > *"Check transaction details for TXN-20260312-0015811 and show the warranty coverage policy for the purchased item."*
* 💡 **Clue-Based Hint:**  
  Table `historical_transactional_data` stores purchased items inside a repeated record array (`tx.items`). How do you flatten array elements in GoogleSQL before joining with extracted warranty terms in `warranty_generic_sections_extracted`?

---

#### **Prompt 2B (UC 2.1 Past Warranty Lookup by Customer ID)**
* **Natural Language Prompt:**  
  > *"Customer CUST_00386 purchased an item at Store 9 using a Gift Card.. Is their item covered under warranty?"*
* 💡 **Clue-Based Hint:**  
  Apply the same relational join methodology as Prompt 2A, targeting customer identity instead of transaction ID.

---

#### **Prompt 3 (UC 2.3 Step 1 Top Promo Abuse Offender Ranking in GCP)**
* **Natural Language Prompt:**  
  > *"Show cashiers with active cashier promo abuse alerts in the last 7 days and rank the top offending cashiers."*
* 💡 **Clue-Based Hint:**  
  Query table `pos_anomaly_alerts`. Filter for promo abuse alert types within a dynamic 7-day timestamp window, group by cashier and store, and rank by alert count.

---

#### **Prompt 4 (UC 2.3 Step 2 Cross-Cloud AWS S3 Checkout Audit)**
* **Natural Language Prompt:**  
  > *"Retrieve historical checkout transaction logs for top promo abuse offender Cashier CASH_1164."*
* 💡 **Clue-Based Hint:**  
  This query targets AWS S3 data federated through BigLake / AWS Glue Catalog in dataset `cymbal-lakehouse.elevate_data.silver_pos_transactions`. Filter directly by the target cashier ID.

---

#### **Prompt 5+ (Optional Additional Golden Queries)**
* *Construct your own analytical queries* over intraday checkouts (`pos_transactions_gold`), supplier warranty durations, or store revenue performance to further enhance your Data Agent's prompt library!

#### 🚀 Successfully Executed Steps & Evidence (Lab Completed)
- **Registered Golden Queries Library:** Deployed 6 high-performance pre-verified GoogleSQL query blueprints under `exampleQueries`:
  1. **Prompt 1 (UC 1.2 Store Inventory Stockout Risk):**
     - Prompt: *"What is the estimated cover hours remaining for store inventory positions experiencing stockout risk of less than 20 hours, and what is their total on-hand inventory?"*
     - SQL: Queries `gold_inventory_reconciliation_ledger`, filters `est_cover_hours_remaining < 20.0`, calculates `(shelf_qty + backroom_qty) AS total_on_hand_inventory`, ordered by `intraday_gross_revenue_usd DESC, est_cover_hours_remaining ASC LIMIT 20`.
  2. **Prompt 2A (UC 2.1 Past Warranty Lookup by Transaction ID):**
     - Prompt: *"Check transaction details for TXN-20260312-0015811 and show the warranty coverage policy for the purchased item."*
     - SQL: Flattens `tx.items` from `historical_transactional_data` via `UNNEST(tx.items) AS item`, joins `warranty_generic_sections_extracted` on `product_id`, filters by transaction ID.
  3. **Prompt 2B (UC 2.1 Past Warranty Lookup by Customer ID):**
     - Prompt: *"Customer CUST_00386 purchased an item at Store 9 using a Gift Card.. Is their item covered under warranty?"*
     - SQL: Relational join with `DATE_DIFF` month calculation and `CASE WHEN ... <= warranty_duration_months THEN 'COVERED' ELSE 'EXPIRED' END`.
  4. **Prompt 3 (UC 2.3 Step 1 Top Promo Abuse Offender Ranking in GCP):**
     - Prompt: *"Show cashiers with active cashier promo abuse alerts in the last 7 days and rank the top offending cashiers."*
     - SQL: Queries `pos_anomaly_alerts`, filters for `cashier_promo_abuse` in the last 7 days, groups by cashier & store, and orders by `alert_count DESC, avg_risk_score DESC LIMIT 20`.
  5. **Prompt 4 (UC 2.3 Step 2 Cross-Cloud AWS S3 Checkout Audit):**
     - Prompt: *"Retrieve historical checkout transaction logs for top promo abuse offender Cashier CASH_1164."*
     - SQL: Federated BigLake / Iceberg query against `cymbal-lakehouse.elevate_data.silver_pos_transactions` filtering directly on `cashier_id = 'CASH_1164'`.
  6. **Prompt 5 (Bestselling Items Intraday):**
     - Prompt: *"What are the top 10 bestselling items by total sales amount today across all stores?"*
     - SQL: Intraday checkout aggregation on `pos_transactions_gold` partitioned by `business_date = CURRENT_DATE()`.

---

## 🏷️ Part 4: Semantic Metric Verification & Custom Terms (Glossary)

### Challenge 4.1: Verify Knowledge Catalog Business Terms Import

#### 🎯 Objective
Verify that the Business Glossary terms bound to your Gold data sources during Lab 1 (Semantic Layer) are automatically imported and visible in your Data Agent configuration.

#### ⚙️ Verification Steps
1. Ensure your BigQuery Gold tables are selected under the **Data sources** section during Data Agent creation.
2. In the **Glossary** section on the agent creation page, click **Manage terms** to view terms synced from Dataplex Knowledge Catalog.
3. Verify that the enterprise business terms associated with your selected tables (e.g., `Net Transaction Revenue`, `Estimated Inventory Cover Hours`, `Cashier Promo Override Rate`, `Total On-Hand Inventory`, `Warranty Policy Duration`) are automatically imported and listed.

---

### [Optional] Challenge 4.2: Add Custom Agent-Specific Glossary Terms

#### 🎯 Objective (Optional Extension)
Explore defining custom calculated metrics directly within the Data Agent inline Glossary UI for agent-specific business logic that is not registered in the central Knowledge Catalog.

#### ⚙️ Optional Practice
If you wish to test custom inline glossary creation:
1. In the **Glossary** section on the agent creation page, click **+ Create Term**.
2. Define a custom metric (e.g., store sales floor shelf stock proportion):
   - **Term Name:** `Shelf Stock Ratio`
   - **Definition:** `[Definition]: Percentage of total on-hand store inventory units placed on retail sales floor shelves. - Target Table: gold_inventory_reconciliation_ledger - Calculation Formula: SAFE_DIVIDE(shelf_qty, (shelf_qty + backroom_qty)) * 100`
3. Click **Add** to save the term and observe how the Data Agent leverages inline definitions alongside catalog-synced terms during SQL generation.

#### 🚀 Successfully Executed Steps & Evidence (Lab Completed)
- **Knowledge Catalog Synced Terms & Custom Metrics Configured:**
  - **Catalog-Synced Enterprise Terms (Challenge 4.1):**
    1. `Net Transaction Revenue`: Subtotal minus discount plus tax amount (`subtotal_amount - discount + tax_amount`) mapped to `pos_transactions_gold`.
    2. `Estimated Inventory Cover Hours`: Operational runway in hours remaining (`est_cover_hours_remaining`) mapped to `gold_inventory_reconciliation_ledger`.
    3. `Cashier Promo Override Rate`: Frequency of cashier promo overrides mapped to `pos_anomaly_alerts`.
    4. `Total On-Hand Inventory`: Combined units across sales floor shelves and backroom storage (`shelf_qty + backroom_qty`) mapped to `gold_inventory_reconciliation_ledger`.
    5. `Warranty Policy Duration`: Guaranteed service coverage SLA in months (`warranty_duration_months`) mapped to `warranty_generic_sections_extracted`.
  - **Custom Agent-Specific Inline Term (Challenge 4.2):**
    - **Term Name:** `Shelf Stock Ratio`
    - **Labels:** `["inventory-mgmt"]`
    - **Definition & Formula:** `[Definition]: Percentage of total on-hand store inventory units placed on retail sales floor shelves. - Target Table: gold_inventory_reconciliation_ledger - Calculation Formula: SAFE_DIVIDE(shelf_qty, (shelf_qty + backroom_qty)) * 100`

---

## 🏷️ Part 5: Interactive Validation & Querying

### Challenge 5.1: Validate Data Agent Execution in BigQuery Studio

#### 🎯 Objective
Publish the Data Agent and test natural language queries directly inside BigQuery Studio to verify SQL generation, accuracy against business logic, and cross-cloud execution.

#### ⚙️ Validation Workflow
1. Click **Publish** in the top-right corner to deploy your Data Agent revision.
2. Open the **Preview / Chat** pane inside BigQuery Studio.
3. Test your prompts for UC 1.2, UC 2.1, and UC 2.3. Compare the generated GoogleSQL against the expected reference SQL queries below to confirm your Data Agent is performing as intended.

---

### 🔍 Verification Benchmark SQL Queries

#### **1. UC 1.2 Validation (Store Inventory Stockout Analysis)**
* **Prompt to Submit in Chat:**  
```text
What is the estimated cover hours remaining for store inventory positions experiencing stockout risk of less than 20 hours, and what is their total on-hand inventory?
```
* **Expected Reference GoogleSQL Generated by Agent:**
```sql
SELECT
  store_id,
  store_name,
  city,
  item_id,
  shelf_qty,
  backroom_qty,
  (shelf_qty + backroom_qty) AS total_on_hand_inventory,
  intraday_gross_revenue_usd,
  est_cover_hours_remaining,
  reconciliation_status
FROM `<PROJECT_ID>.cymbal_gold.gold_inventory_reconciliation_ledger`
WHERE est_cover_hours_remaining < 20.0
ORDER BY intraday_gross_revenue_usd DESC, est_cover_hours_remaining ASC
LIMIT 20;
```
* **Verification Criteria:** The agent correctly identifies `gold_inventory_reconciliation_ledger`, applies the filter `est_cover_hours_remaining < 20.0`, calculates total on-hand stock (`shelf_qty + backroom_qty`), and orders by gross revenue.

---

#### **2. UC 2.1 Validation (Past Purchase & Warranty Policy Triage)**
* **Prompt to Submit in Chat:**  
```text
Check transaction details for TXN-20260312-0015811 and show the warranty coverage policy for the purchased item.
```
* **Expected Reference GoogleSQL Generated by Agent:**
```sql
SELECT
  tx.transaction_id,
  tx.business_date,
  tx.customer_loyalty_tier,
  tx.store_id,
  tx.payment_method,
  item.item_id AS product_id,
  item.item_name AS product_name,
  item.unit_price,
  warr.warranty_duration_months,
  warr.service_level,
  warr.coverage_scope_details,
  warr.exclusions_and_limitations,
  warr.official_retailer_guarantee_and_sla,
  warr.support_url
FROM `<PROJECT_ID>.cymbal_gold.historical_transactional_data` tx,
UNNEST(tx.items) AS item
JOIN `<PROJECT_ID>.module1_unstructureddata.warranty_generic_sections_extracted` warr
  ON item.item_id = warr.product_id
WHERE tx.transaction_id = 'TXN-20260312-0015811'
LIMIT 1;
```
* **Verification Criteria:** The agent successfully unnests the repeated `tx.items` array from `historical_transactional_data` and joins with `warranty_generic_sections_extracted` on `product_id`.

---

#### **3. UC 2.3 Validation (Cross-Cloud Promo Abuse & AWS S3 Audit)**

* **Step 1 Prompt (Identify Top Promo Abuse Offender in GCP BigQuery):**  
```text
Show cashiers with active cashier promo abuse alerts in the last 7 days and rank the top offending cashiers.
```
* **Expected Reference GoogleSQL:**
```sql
SELECT
  store_id,
  cashier_id,
  COUNT(alert_id) AS alert_count,
  ROUND(AVG(risk_score), 4) AS avg_risk_score,
  MAX(risk_score) AS max_risk_score,
  MAX(alert_ts) AS latest_alert_ts
FROM `<PROJECT_ID>.cymbal_gold.pos_anomaly_alerts`
WHERE alert_type = 'cashier_promo_abuse'
  AND alert_ts >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 7 DAY)
GROUP BY store_id, cashier_id
ORDER BY alert_count DESC, avg_risk_score DESC
LIMIT 20;
```

* **Step 2 Prompt (Cross-Cloud Federated AWS S3 Checkout Query):**  
```text
Retrieve historical checkout transaction logs for top promo abuse offender Cashier CASH_1164.
```
* **Expected Reference GoogleSQL:**
```sql
SELECT
  transaction_id,
  event_timestamp,
  store_id,
  pos_terminal_id,
  cashier_id,
  payment_method,
  total_amount_usd
FROM `<PROJECT_ID>.cymbal-lakehouse.elevate_data.silver_pos_transactions`
WHERE cashier_id = 'CASH_1164'
ORDER BY event_timestamp ASC
LIMIT 10;
```
* **Verification Criteria:** The agent queries `pos_anomaly_alerts` for the GCP ranking step, and routes the cross-cloud query to `cymbal-lakehouse.elevate_data.silver_pos_transactions` querying AWS S3 directly via BigLake federation.

---

### 🚀 Successfully Executed Steps & Evidence (Lab Completed)

#### 1. Data Agent Publishing Status
- **Data Agent:** `projects/xiaoyj-lab/locations/global/dataAgents/cymbal-retail-analytics`
- **Publish Status:** Verified active in `publishedContext` and accessible via the global Conversational Analytics chat endpoint (`https://geminidataanalytics.googleapis.com/v1/projects/xiaoyj-lab/locations/global:chat`).

#### 2. Live Interactive Validation Execution Results

##### **Test Case 1: UC 1.2 Store Inventory Stockout Analysis**
* **Prompt:**  
  `What is the estimated cover hours remaining for store inventory positions experiencing stockout risk of less than 20 hours, and what is their total on-hand inventory?`
* **Generated GoogleSQL:**
  ```sql
  SELECT store_id,
         store_name,
         city,
         item_id,
         shelf_qty,
         backroom_qty,
         (shelf_qty + backroom_qty) AS total_on_hand_inventory,
         intraday_gross_revenue_usd,
         est_cover_hours_remaining,
         reconciliation_status
  FROM `xiaoyj-lab.cymbal_gold.gold_inventory_reconciliation_ledger`
  WHERE est_cover_hours_remaining < 20.0
  ORDER BY intraday_gross_revenue_usd DESC,
           est_cover_hours_remaining ASC
  LIMIT 20;
  ```
* **Execution Metric:** Returned **20 rows in 1.22s**.
* **Agent Response:**  
  > *"Here is the estimated cover hours remaining and total on-hand inventory for store inventory positions experiencing stockout risk of less than 20 hours (showing the top 20 by intraday gross revenue), adapted from the standard inventory risk assessment query."*

---

##### **Test Case 2: UC 2.1 Past Purchase & Warranty Policy Triage (Prompt 2A)**
* **Prompt:**  
  `Check transaction details for TXN-20260312-0015811 and show the warranty coverage policy for the purchased item.`
* **Generated GoogleSQL:**
  ```sql
  SELECT tx.transaction_id,
         tx.business_date,
         tx.customer_loyalty_tier,
         tx.store_id,
         tx.payment_method,
         item.item_id AS product_id,
         item.item_name AS product_name,
         item.unit_price,
         warr.warranty_duration_months,
         warr.service_level,
         warr.coverage_scope_details,
         warr.exclusions_and_limitations,
         warr.official_retailer_guarantee_and_sla,
         warr.support_url
  FROM `xiaoyj-lab.cymbal_gold.historical_transactional_data` tx,
       UNNEST(tx.items) AS item
  JOIN `xiaoyj-lab.module1_unstructureddata.warranty_generic_sections_extracted` warr ON item.item_id = warr.product_id
  WHERE tx.transaction_id = 'TXN-20260312-0015811'
  LIMIT 1;
  ```
* **Execution Metric:** Returned **1 row in 1.77s**.
* **Agent Response:**  
  > *"Transaction **TXN-20260312-0015811** on **2026-03-12** recorded the purchase of a **Samsung Galaxy Watch4 Classic LTE (4.6cm, Black)** (Product ID: `prod_1954`) for **$222.99** at store `STORE_005` using a `DEBIT_CARD` by a `BRONZE` tier customer.  
  > **Warranty Coverage Highlights:**  
  > - **Warranty Duration:** 24 Months Limited Hardware Warranty.  
  > - **Service Level:** Authorized Audio Lab Testing & Immediate Unit Replacement.  
  > - **Coverage Scope:** Comprehensive protection against defects in materials and workmanship under normal consumer use. Includes free repair using new/certified refurbished parts or immediate unit replacement.  
  > - **Exclusions:** Excludes accidental damage, abuse, cosmetic damage, and normal consumable battery wear."*

---

##### **Test Case 3: UC 2.1 Customer Warranty Eligibility Verification (Prompt 2B)**
* **Prompt:**  
  `Customer CUST_00386 purchased an item at Store 9 using a Gift Card.. Is their item covered under warranty?`
* **Generated GoogleSQL:**
  ```sql
  SELECT tx.transaction_id,
         tx.customer_id,
         tx.store_id,
         tx.payment_method,
         item.item_id AS product_id,
         item.item_name AS product_name,
         tx.business_date,
         warr.warranty_duration_months,
         DATE_DIFF(CURRENT_DATE(), tx.business_date, MONTH) AS elapsed_months,
         CASE
             WHEN DATE_DIFF(CURRENT_DATE(), tx.business_date, MONTH) <= warr.warranty_duration_months THEN 'COVERED'
             ELSE 'EXPIRED'
         END AS warranty_status,
         warr.coverage_scope_details,
         warr.support_url
  FROM `xiaoyj-lab.cymbal_gold.historical_transactional_data` tx,
       UNNEST(tx.items) AS item
  JOIN `xiaoyj-lab.module1_unstructureddata.warranty_generic_sections_extracted` warr ON item.item_id = warr.product_id
  WHERE tx.customer_id = 'CUST_00386'
    AND tx.store_id = 'STORE_009'
    AND tx.payment_method = 'GIFT_CARD'
  ORDER BY tx.business_date DESC
  LIMIT 1;
  ```
* **Execution Metric:** Returned **1 row in 2.10s**.
* **Agent Response:**  
  > *"Yes, the item purchased by customer **CUST_00386** is **COVERED** under warranty. Based on the historical transaction records and warranty policies, the customer purchased a **Samsung Galaxy M04** on **February 21, 2026**, which has a **24-month** warranty duration. Only **7 months** have elapsed, so the warranty is still active."*

---

##### **Test Case 4: UC 2.3 Step 1 Top Promo Abuse Offender Ranking in GCP**
* **Prompt:**  
  `Show cashiers with active cashier promo abuse alerts in the last 7 days and rank the top offending cashiers.`
* **Generated GoogleSQL:**
  ```sql
  SELECT store_id,
         cashier_id,
         COUNT(alert_id) AS alert_count,
         ROUND(AVG(risk_score), 4) AS avg_risk_score,
         MAX(risk_score) AS max_risk_score,
         MAX(alert_ts) AS latest_alert_ts
  FROM `xiaoyj-lab.cymbal_gold.pos_anomaly_alerts`
  WHERE alert_type = 'cashier_promo_abuse'
    AND alert_ts >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 7 DAY)
  GROUP BY store_id,
           cashier_id
  ORDER BY alert_count DESC,
           avg_risk_score DESC
  LIMIT 20;
  ```
* **Execution Metric:** Returned **10 rows in 1.14s**.
* **Agent Response:**  
  > *"Based on the active cashier promo abuse alert analysis over the last 7 days, Cashier `CASH_1190` at `STORE_048` is the top offender with 37 alerts, closely followed by `CASH_1164` at `STORE_041` with 35 alerts."*

---

##### **Test Case 5: UC 2.3 Step 2 Cross-Cloud AWS S3 Checkout Audit via BigLake Federation**
* **Prompt:**  
  `Retrieve historical checkout transaction logs for top promo abuse offender Cashier CASH_1164.`
* **Generated GoogleSQL:**
  ```sql
  SELECT transaction_id,
         event_timestamp,
         store_id,
         pos_terminal_id,
         cashier_id,
         payment_method,
         total_amount_usd
  FROM `xiaoyj-lab.cymbal-lakehouse.elevate_data.silver_pos_transactions`
  WHERE cashier_id = 'CASH_1164'
  ORDER BY event_timestamp ASC
  LIMIT 10;
  ```
* **Execution Metric:** Returned **10 rows in 5.38s** from federated AWS S3 Iceberg data layer (`s3://cymbal-global-retail-demo/lakehouse/elevate_data/silver_pos_transactions`).
* **Agent Response:**  
  > *"The historical checkout transaction logs for cashier **CASH_1164** (identified as a top promo abuse offender) have been retrieved from the federated S3 data layer, adapted from the standard transaction log query."*

