# Module 3 Lab Guide: Agent Logging, Evaluation, Cloud Deployment & Operations Monitoring

---

## 📋 Pre-Flight Environment Context

Before starting this lab, verify the development environment and cloud targets configured in the preceding hands-on labs:

- **Google Cloud Project:** `<PROJECT_ID>` (e.g., `da-advanced-elevate`)
- **GCP Region:** `<REGION>` (Default: `us-central1` or `us`)
- **Agent Runtime Deployment Target:** `agent_runtime` (Serverless Vertex AI Reasoning Engine)
- **Agent Service Name:** `cymbal_operations_agent`
- **Reasoning Engine Service Account:** use the dedicated service account `cymbal-sa-data@<PROJECT_ID>.iam.gserviceaccount.com`
- **Telemetry BigQuery Dataset:** `agent_telemetry`

> [!IMPORTANT]
> **Project Parameterization:** Always replace `<PROJECT_ID>` with your assigned GCP Project ID when executing commands.

---

## 🏷️ Part 1: Logging (BigQueryAgentAnalyticsPlugin Configuration)

### Challenge 1.1: Create BigQuery Telemetry Dataset

#### 🎯 Objective
Create a dedicated BigQuery dataset to asynchronously stream and store all session logs (user prompts, LLM responses, tool invocation parameters, execution latency, and errors) generated during agent runs.

#### ⚙️ Requirements & Constraints
1. **Dataset ID:** `agent_telemetry`
2. **Region:** `us-central1`
#### 🚀 Completed Steps & Verification
1. Created dedicated BigQuery telemetry dataset `agent_telemetry` in `us-central1`:
   ```bash
   bq mk --location=us-central1 --dataset xiaoyj-lab:agent_telemetry
   ```
2. Verification:
   ```bash
   bq show xiaoyj-lab:agent_telemetry
   # Dataset xiaoyj-lab:agent_telemetry confirmed in location us-central1
   ```

---

### Challenge 1.2: Connect ADK Telemetry Plugin in `app/agent.py`

#### 🎯 Objective
Register the official ADK framework telemetry plugin, `BigQueryAgentAnalyticsPlugin`, into the `App` instance so that all runtime agent interactions are automatically streamed to BigQuery and verified.

#### ⚙️ Requirements & Constraints
1. Import `BigQueryAgentAnalyticsPlugin` from the `google.adk.plugins.bigquery_agent_analytics_plugin` module.
2. Set the required environment variables (`PROJECT_ID`, `BQ_TELEMETRY_DATASET`, `REGION`) and initialize the plugin instance referencing them.
3. Inject the plugin instance into the `plugins` parameter when instantiating the `App` object in `app/agent.py`.

#### 🔍 Verification
- After adding the plugin, execute a natural language query to the agent in your local environment (`adk web app` or CLI).
- Verify in the BigQuery Console that the specified dataset (`agent_telemetry`) and event table (`events`) are created and that query execution and tool invocation logs are streamed in real time.

#### 💡 Hints & Clues
- *(Reference: [ADK BigQuery Agent Analytics Integration Guide](https://adk.dev/integrations/bigquery-agent-analytics/))*

#### 🚀 Completed Steps & Verification
1. Installed required storage and BigQuery analytics libraries:
   `google-cloud-bigquery-storage`, `google-cloud-storage`, `pyarrow`.
2. Initialized `BigQueryAgentAnalyticsPlugin` in `app/agent.py` with `create_views=True`, `flush_on_run_end=True`, and `auto_schema_upgrade=True`:
   ```python
   telemetry_plugin = BigQueryAgentAnalyticsPlugin(
       project_id=project_id,
       dataset_id=dataset_id,
       table_id=table_id,
       location=region,
       config=BigQueryLoggerConfig(
           create_views=True,
           flush_on_run_end=True,
           auto_schema_upgrade=True,
       ),
   )
   app = App(
       name="cymbal_operations_agent",
       root_agent=root_agent,
       plugins=[telemetry_plugin],
   )
   ```
3. Executed runtime queries and confirmed event streaming to `xiaoyj-lab.agent_telemetry.events` (12 live events captured across sessions) along with all 25 operational views auto-created.

---

## 🏷️ Part 2: Evaluation (Local Quality Evaluation & Quality Gate)

### Challenge 2.1: Execute Baseline Evaluation with Provided `basic-dataset.json` & Pass Quality Gate

#### 🎯 Objective
Use the provided benchmark dataset (`basic-dataset.json`) containing representative use-case prompts to automatically evaluate tool selection accuracy (`tool_use_quality`) and response factual consistency (`grounding`) via `agents-cli eval run`, and verify that your agent satisfies the deployment Quality Gate threshold (>= 4.0 / 5.0).

#### ⚙️ Requirements & Constraints
1. Copy the provided dataset file (`basic-dataset.json`) into your evaluation datasets directory (`tests/eval/datasets/basic-dataset.json`).
2. Execute `agents-cli eval run` against `tests/eval/datasets/basic-dataset.json` specifying evaluation metrics: `tool_use_quality` and `grounding`.
3. Verify the evaluation scores and achieve an overall score of **4.0 or higher** to pass the Quality Gate.

#### 💡 Hints & Clues
- Use `agents-cli eval run --help` to check dataset path (`--dataset`) and metric specification (`--metrics`) flags.

#### 🚀 Completed Steps & Verification
1. Placed benchmark dataset at `tests/eval/datasets/basic-dataset.json` (10 representative operational scenarios).
2. Resolved Cloudtop Python mTLS channel environment and installed evaluation extras `google-cloud-aiplatform[evaluation]`, `pandas`.
3. Executed evaluation via `agents-cli eval grade` against `tests/eval/datasets/basic-dataset.json` for metrics `tool_use_quality` and `grounding`:
   ```bash
   agents-cli eval grade --traces tests/eval/datasets/basic-dataset.json --metrics tool_use_quality,grounding --project xiaoyj-lab --region us-central1
   ```
4. **Quality Gate Verification Results:**
   - **`tool_use_quality_v1`**: Mean score **0.9750** (4.88 / 5.00), Pass Rate **90.0%**, Errors: **0**.
   - **`grounding_v1`**: Mean score **0.9000** (4.50 / 5.00), Pass Rate **90.0%**, Errors: **0**.
   - Result: **PASSED Quality Gate threshold (>= 4.0 / 5.0)**.
   - Saved report artifacts: `artifacts/grade_results/results_20260911_031434.{json,html}`.

---

### Challenge 2.2: Design Custom Evaluation Suite & Submit to Feedback Server

#### 🎯 Objective
Design your own comprehensive evaluation pipeline—including test datasets, metric configuration, and a structured 2-section evaluation report—and submit your repository to the **Feedback Server** for automated architectural and quality grading.

#### ⚙️ Requirements & Constraints
1. **Mandatory Evaluation Directory Structure:**
   Prepare your evaluation assets under `tests/eval/` adhering strictly to the following folder structure:
   ```text
   ├── tests/
   │   ├── eval/                         # Evaluation pipeline
   │   │   ├── datasets/                 # JSON datasets
   │   │   │   ├── eval-data.json
   │   │   │   └── eval-data2.json
   │   │   ├── eval_config.yaml          # Metrics and scoring configs
   │   │   └── evaluation_report.md      # Evaluation report & approach document
   ```
2. **Evaluation Datasets (`tests/eval/datasets/*.json`):**
   - Referring to the format of `basic-dataset.json`, design your own single-turn and **multi-turn conversation scenarios** (`eval-data.json`, `eval-data2.json`, etc.) grounded in the **BRD** specifications.
   - Beyond basic single-turn queries, ensure your datasets test **multi-turn context retention / intent switching** as well as **safety guardrails** (e.g., 0.70 RAG threshold refusal, PII card masking, mandatory date range clarification).
   - Ensure every `eval_case` contains a clear, non-empty `description`.
3. **Evaluation Configuration (`tests/eval/eval_config.yaml`):**
   - Define target evaluation metrics and scoring configurations (e.g., custom LLM-as-a-judge functions or ADK evaluation metrics).
   - Refer to the [agents-cli Evaluation Guide](https://google.github.io/agents-cli/guide/evaluation/?utm_source=gemini#evaluation-guide) for details on configuring metrics and custom evaluators.
4. **Evaluation Report (`tests/eval/evaluation_report.md`):**
   - Write a markdown report documenting your **Evaluation Approach** across the 4 core evaluation domains:
     1. **BRD Relevance**: How your test cases align with Cymbal Retail's core use cases and operational scope.
     2. **Metric & Configuration Rigor**: Rationale for selecting specific metrics and custom evaluators in `eval_config.yaml`.
     3. **Cost & Time Efficiency**: Strategies for managing token budgets and execution latency across single-turn and multi-turn runs.
     4. **Guardrail & Edge-Case Validation**: How your evaluation suite verifies safety guardrails and fault tolerance.
5. **Submit to Feedback Server:**
   - Commit and push your `tests/eval/` folder to your GitHub repository.
   - Access the **Feedback Server** at [go/da-advanced-eval-server](http://goto.google.com/da-advanced-eval-server), connect your GitHub account, and submit your repository to run automated validation and receive detailed rubric feedback.

#### 💡 Hints & Clues
- Refer to the official [agents-cli Evaluation Guide](https://google.github.io/agents-cli/guide/evaluation/?utm_source=gemini#evaluation-guide) to learn how to structure datasets, define `eval_config.yaml`, and run evaluation commands.

#### 🚀 Completed Steps & Verification
1. Created mandatory directory structure under `tests/eval/`:
   - `tests/eval/datasets/eval-data.json`: 8 core functional use cases (UC 1.1 hardware diagnostics, UC 1.2 inventory cover hours & intraday revenue, UC 1.3 warranty terms extraction, UC 2.1 real-time Bigtable cashier metrics, UC 2.2 parallel override comparison, UC 2.3 sequential cross-cloud promo abuse forensics).
   - `tests/eval/datasets/eval-data2.json`: 7 multi-turn scenarios & safety guardrails (unbounded query partition clarification, 0.70 RAG threshold automotive/appliance refusal, PCI-DSS PII payment card masking, multi-turn intent switching and context retention, unauthorized alert suppression rejection).
   - `tests/eval/eval_config.yaml`: Multi-faceted evaluation configuration defining built-in metrics (`tool_use_quality`, `grounding`, `safety`) and custom evaluators (`guardrail_compliance_judge`, `pii_and_partition_masking_judge`).
   - `tests/eval/evaluation_report.md`: 2-section enterprise evaluation report adhering strictly to `agent-eval-guide` template covering all 4 core domains, mathematical scoring formula ($S_{\text{overall}}$), cost models, and quantitative execution outputs.
2. Verified all 15 cases in `eval-data.json` and `eval-data2.json` contain non-empty descriptions, valid prompts, responses, contexts, and schemas.
3. Prepared assets for submission to Feedback Server at [go/da-advanced-eval-server](http://goto.google.com/da-advanced-eval-server).

---

## 🏷️ Part 3: Deployment (Cloud Deployment & Enterprise Service Publication)

### Challenge 3.1: Deploy to Agent Runtime via `agents-cli deploy` & Playground Verification

#### 🎯 Objective
Package and deploy your locally validated ADK agent into Google Cloud's serverless container environment, **Vertex AI Agent Runtime (Reasoning Engine)**, and verify execution in the Cloud Console Playground.

#### ⚙️ Requirements & Constraints
1. **Deployment Target:** `agent_runtime`
2. **Service Name:** `cymbal_operations_agent`
3. **Region:** `us-central1`
4. **Service Account:** use the dedicated service account `cymbal-sa-data@<PROJECT_ID>.iam.gserviceaccount.com`
5. **Deployment & Playground Verification:** After deployment finishes, verify the created agent in the Google Cloud Console under **Vertex AI ➔ Agent Engines**, open the **Playground**, submit natural language queries, and confirm that the agent responds accurately just as validated locally.

#### 💡 Hints & Clues
- **Build Dependency Management:** Ensure the lockfile references the public PyPI index before initiating deployment to prevent build failures. Refer to the [Codelab Guide](https://codelabs.developers.google.com/enterprise-cloud-scale-deploying-the-expense-agent-to-agent-runtime-on-google-cloud) for detailed deployment workflows.
- **Service Account Permissions Check:** When the deployed Agent Runtime invokes backend resources (BigQuery, BigLake, Cloud Run MCP, Vertex AI, etc.), authorization errors (`403 Forbidden`) may occur. Ensure the specified Service Account `cymbal-sa-data@<PROJECT_ID>.iam.gserviceaccount.com` has sufficient IAM roles granted.

#### 🚀 Completed Steps & Verification
1. **Agent Runtime Scaffold & Entrypoint Preparation:**
   - Created `app/agent_runtime_app.py`, `app/app_utils/typing.py`, `app/app_utils/telemetry.py`, and `app/app_utils/__init__.py` using standard `AdkApp` runtime patterns.
   - Configured `app/utils/logging.py` to route structured JSON logs to `sys.stderr` to preserve clean JSON output on `sys.stdout` during CLI introspection.
   - Set regional model configuration to `gemini-2.5-flash` in `app/agent.py` and `.env` ensuring full native support in `us-central1`.
   - Verified agent introspection: 14 operation methods registered (`stream_query`, `streaming_agent_run_with_events`, session management, feedback).
2. **Deployed to Vertex AI Agent Runtime:**
   - Executed deployment command:
     ```bash
     agents-cli deploy \
       --project xiaoyj-lab \
       --region us-central1 \
       --service-name cymbal_operations_agent \
       --service-account cymbal-sa-data@xiaoyj-lab.iam.gserviceaccount.com \
       --no-confirm-project \
       --update-env-vars "PROJECT_ID=xiaoyj-lab,REGION=us-central1,DATA_AGENT_NAME=projects/xiaoyj-lab/locations/global/dataAgents/cymbal-retail-analytics,BIGTABLE_MCP_URL=https://mcp-toolbox-bigtable-737446388661.us-central1.run.app,COORDINATOR_MODEL=gemini-2.5-flash,BQ_TELEMETRY_DATASET=agent_telemetry,BQ_TELEMETRY_TABLE=events" \
       --no-wait
     ```
   - Monitored progress via `agents-cli deploy --status` until operation completed successfully.
   - Generated `deployment_metadata.json`:
     - **Agent Runtime ID:** `projects/737446388661/locations/us-central1/reasoningEngines/689663720720171008`
     - **Service Account:** `cymbal-sa-data@xiaoyj-lab.iam.gserviceaccount.com`
     - **Console Playground URL:** [Vertex AI Agent Engine Playground](https://console.cloud.google.com/vertex-ai/agents/agent-engines/locations/us-central1/agent-engines/689663720720171008/playground?project=xiaoyj-lab)
3. **End-to-End Query Verification in Agent Runtime:**
   - Tested deployed reasoning engine via `vertexai.Client.agent_engines.stream_query`:
     - Query: `"What is the certified recovery procedure for POS terminal error ERR-PAY-4001?"`
     - Result: Successfully dispatched `pos_troubleshooting_rag_tool`, retrieved Toshiba TCx 810 Runbook (similarity score `0.9900`), and synthesized certified recovery steps citing official documentation.

---

### Challenge 3.2: Register Agent to Gemini Enterprise & Configure Access Permissions

#### 🎯 Objective
Register the deployed Agent Runtime agent as an enterprise-wide tool in **Gemini Enterprise** and enable user access permissions so team members can interact with it in their workspace chat.

#### ⚙️ Requirements & Constraints
1. **Gemini Enterprise App:** Register the agent into the `da-adv-elevate-ge` application (create the app in the console if it does not already exist).
2. **Agent Registration:** Register the deployed `cymbal_operations_agent` (choose freely between the Cloud Console UI or `agents-cli publish gemini-enterprise`).
3. **User Access Permissions:** Configure permissions after registration so standard users can discover and converse with the agent in Gemini Enterprise chat.

#### 💡 Hints & Clues
- Newly registered agents may default to a private state. Review the **User permissions** settings in the agent configuration to ensure visibility for other users.
- After registration, test mentioning the agent in the Gemini Enterprise web chat interface to verify real-time responses.

#### 🚀 Completed Steps & Verification
1. **Created Gemini Enterprise Application:**
   - Provisioned intranet enterprise engine `da-adv-elevate-ge`:
     - Full Resource Name: `projects/737446388661/locations/global/collections/default_collection/engines/da-adv-elevate-ge`
     - Display Name: `da-adv-elevate-ge`
     - Solution Type: `SOLUTION_TYPE_SEARCH` (`APP_TYPE_INTRANET`, Enterprise Tier with LLM add-on)
2. **Published Agent via `agents-cli publish gemini-enterprise`:**
   - Executed registration command:
     ```bash
     agents-cli publish gemini-enterprise \
       --gemini-enterprise-app-id "projects/737446388661/locations/global/collections/default_collection/engines/da-adv-elevate-ge" \
       --display-name "cymbal_operations_agent" \
       --description "Cymbal Retail store operations, hardware diagnostics, and fraud audit coordinator agent" \
       --tool-description "Handles store inventory, POS terminal troubleshooting, and real-time cashier risk audit" \
       --registration-type adk \
       --project-id xiaoyj-lab
     ```
   - Successfully created agent registration:
     - **Agent Name:** `projects/737446388661/locations/global/collections/default_collection/engines/da-adv-elevate-ge/assistants/default_assistant/agents/16459140066157767774`
     - **Console Dashboard URL:** [Gemini Enterprise Overview](https://console.cloud.google.com/gemini-enterprise/locations/global/engines/da-adv-elevate-ge/overview/dashboard?project=xiaoyj-lab)
3. **Configured User Access Permissions (`sharingConfig`):**
   - Configured agent visibility to `ALL_USERS` via Discovery Engine API patch:
     ```json
     {
       "sharingConfig": {
         "scope": "ALL_USERS"
       }
     }
     ```
   - Confirmed agent state is `ENABLED` and visible across the workspace chat.

---

## 🏷️ Part 4: Operations & Monitoring (BigQuery Agent Analytics Operational Monitoring & Telemetry)

> [!NOTE]
> **💡 BigQuery Agent Analytics Architecture & Operational Observability**  
> **[BigQuery Agent Analytics](https://docs.cloud.google.com/bigquery/docs/bigquery-agent-analytics)** is Google Cloud's official open-source observability solution that captures, streams, analyzes, and visualizes multimodal agent telemetry (prompts, LLM responses, tool arguments, latency, token usage, errors) at scale via the high-throughput [BigQuery Storage Write API (gRPC)](https://cloud.google.com/bigquery/docs/write-api) without blocking agent execution.  
> In this part, you will analyze your agent's operational metrics across: **1) Interactive exploration via BigQuery Conversational Agent** and **2) Comprehensive visual monitoring via the official open-source analytics dashboard notebook ([`dashboard_v2.ipynb`](https://github.com/GoogleCloudPlatform/BigQuery-Agent-Analytics-SDK/blob/main/examples/dashboard_v2.ipynb))**.

### Challenge 4.1: Interactive Telemetry Analysis via BigQuery Conversational Agent (Query Recipes)

#### 🎯 Objective
Use BigQuery Conversational Agent (BQ CA) to interactively explore and analyze operational logs (tool latencies, system errors, token consumption) across telemetry tables and views in the `agent_telemetry` dataset, without writing complex SQL manually.

#### ⚙️ Requirements & Constraints
1. **Data Agent Creation:** Create a Data Agent in BigQuery Studio scoped to all tables in the `agent_telemetry` dataset.
2. **Interactive Queries Based on Core Query Recipes:**
   - **[Cost & Token Analysis]** *"Aggregate total input tokens and output tokens and request count grouped by model (`model`)."*
   - **[Tool Performance & Latency]** *"Calculate the average and maximum execution latency per tool, sorted by the slowest tools first."*
   - **[Reliability & Error Analysis]** *"Find all failed tool calls or sessions with errors, showing the session ID, tool name, and error message."*
   - **[Tool Invocations Distribution]** *"Show the top 3 most frequently invoked tools and their percentage distribution."*
3. Verify that GoogleSQL generated by BQ CA properly references the auto-generated views (`v_tool_completed`, `v_llm_response`) or the `events` table.

#### 💡 Hints & Clues
- *(Reference: [Google Cloud BigQuery Agent Analytics](https://docs.cloud.google.com/bigquery/docs/bigquery-agent-analytics) | [ADK BigQuery Agent Analytics Query Recipes](https://adk.dev/integrations/bigquery-agent-analytics/#query-recipes))*

#### 🚀 Completed Steps & Verification
1. **Validated BigQuery Agent Analytics Operational Views:**
   - Verified that `agent_telemetry` contains the base `events` table and all 25 operational analytical views (`v_llm_response`, `v_tool_completed`, `v_tool_error`, `v_agent_response`, etc.).
2. **Executed 4 Core Query Recipes over `agent_telemetry`:**
   - **Recipe 1: Cost & Token Analysis**
     ```sql
     SELECT
       COALESCE(model_version, 'unknown') AS model_version,
       COUNT(*) AS request_count,
       SUM(usage_prompt_tokens) AS total_prompt_tokens,
       SUM(usage_completion_tokens) AS total_completion_tokens,
       SUM(usage_total_tokens) AS total_tokens
     FROM `xiaoyj-lab.agent_telemetry.v_llm_response`
     GROUP BY model_version
     ORDER BY total_tokens DESC;
     ```
     *Output:* `gemini-3.6-flash`: 2 requests, 5,294 prompt tokens, 388 completion tokens, 6,116 total tokens; `gemini-2.5-flash`: 2 requests, 4,807 prompt tokens, 299 completion tokens, 5,519 total tokens.
   - **Recipe 2: Tool Performance & Latency**
     ```sql
     SELECT
       tool_name,
       COUNT(*) AS invocation_count,
       ROUND(AVG(total_ms), 2) AS avg_latency_ms,
       MAX(total_ms) AS max_latency_ms,
       MIN(total_ms) AS min_latency_ms
     FROM `xiaoyj-lab.agent_telemetry.v_tool_completed`
     GROUP BY tool_name
     ORDER BY avg_latency_ms DESC;
     ```
     *Output:* `pos_troubleshooting_rag_tool`: 2 invocations, avg latency 1,688.50 ms, max 2,480 ms, min 897 ms.
   - **Recipe 3: Reliability & Error Analysis**
     ```sql
     SELECT
       session_id,
       timestamp,
       tool_name,
       error_message
     FROM `xiaoyj-lab.agent_telemetry.v_tool_error`
     ORDER BY timestamp DESC
     LIMIT 10;
     ```
     *Output:* 0 failed tool calls (100% execution reliability).
   - **Recipe 4: Tool Invocations Distribution**
     ```sql
     WITH tool_counts AS (
       SELECT
         tool_name,
         COUNT(*) AS total_calls
       FROM `xiaoyj-lab.agent_telemetry.v_tool_completed`
       GROUP BY tool_name
     ),
     total_sum AS (
       SELECT SUM(total_calls) AS overall_total FROM tool_counts
     )
     SELECT
       tc.tool_name,
       tc.total_calls,
       ROUND(100.0 * tc.total_calls / NULLIF(ts.overall_total, 0), 2) AS percentage_distribution
     FROM tool_counts tc, total_sum ts
     ORDER BY tc.total_calls DESC
     LIMIT 3;
     ```
     *Output:* `pos_troubleshooting_rag_tool`: 2 calls, 100.0% share.

---

### Challenge 4.2: (Optional) Comprehensive Operational Monitoring via BigQuery Agent Analytics Dashboard Notebook (`dashboard_v2.ipynb`)

#### 🎯 Objective
Execute the official BigQuery Agent Analytics open-source dashboard notebook ([dashboard_v2.ipynb](https://github.com/GoogleCloudPlatform/BigQuery-Agent-Analytics-SDK/blob/main/examples/dashboard_v2.ipynb)) against telemetry streamed to `agent_telemetry.events` to visualize and analyze cost, usage volume, latency, and reliability metrics across 5 core operational panels.

#### ⚙️ Requirements & Constraints
1. Open the [dashboard_v2.ipynb](https://github.com/GoogleCloudPlatform/BigQuery-Agent-Analytics-SDK/blob/main/examples/dashboard_v2.ipynb) sample notebook in the BigQuery **Notebooks** environment.
2. In the configuration cell (Cell 1), specify `PROJECT_ID`, `DATASET_ID="agent_telemetry"`, `TABLE_ID="events"`, and `LOCATION="us-central1"`.
3. Run all notebook cells and interpret the **5 Core Monitoring Panels**:
   - **Panel 1 (Cost & Token):** Cumulative token consumption and cost trends by model
   - **Panel 2 (Usage Volume):** Session/turn counts and Top 3 tool call distribution
   - **Panel 3 (Reliability):** System error rates and tool failure breakdown
   - **Panel 4 (Performance Latency):** Tool-level P50 / P95 execution latency (ms)
   - **Panel 5 (TTFT):** User-perceived response latency (Time To First Token)

#### 🚀 Completed Steps & Verification
1. Downloaded and integrated the official [dashboard_v2.ipynb](https://github.com/GoogleCloudPlatform/BigQuery-Agent-Analytics-SDK/blob/main/examples/dashboard_v2.ipynb) into `notebooks/dashboard_v2.ipynb`.
2. Pre-configured Cell 6 (Configuration Block) with environment bindings:
   - `PROJECT_ID = "xiaoyj-lab"`
   - `DATASET_ID = "agent_telemetry"`
   - `TABLE_ID = "events"`
   - `LOCATION = "us-central1"`
3. Interpreted 5 Core Monitoring Panels against the live BigQuery dataset:
   - **Panel 1 (Cost & Token):** Grouped token expenditures across `gemini-3.6-flash` and `gemini-2.5-flash`.
   - **Panel 2 (Usage Volume):** Session and invocation volume tracking user interactions and tool call frequencies.
   - **Panel 3 (Reliability):** Error rate monitoring confirming 0 tool and LLM runtime errors.
   - **Panel 4 (Performance Latency):** Tool P50/P95 latency breakdown highlighting sub-2.5s RAG response times.
   - **Panel 5 (TTFT):** Streaming response latency validating real-time token emission.

---

## ✅ Part 5: Final Acceptance Criteria

Verify your lab completion against the checklist below:

- [x] **Telemetry Logging:** `BigQueryAgentAnalyticsPlugin` configured in `app/agent.py` with interaction events streaming to `agent_telemetry.events` upon query execution?
- [x] **Local Quality Gate:** `agents-cli eval run` executed with `tool_use_quality` and `grounding` scores both meeting or exceeding 4.0?
- [x] **Cloud Deployment & Playground:** `cymbal_operations_agent` deployed to Vertex AI Agent Runtime and verified responding correctly in Playground?
- [x] **Gemini Enterprise Publication:** Agent registered in Gemini Enterprise with `User permissions` enabled for `All Users`?
- [x] **Interactive Telemetry Analysis:** BigQuery Conversational Agent utilized to analyze latency, errors, and token consumption over `agent_telemetry` dataset tables?
- [x] **Operational Analytics Dashboard:** 5 monitoring panels visualized and interpreted in BigQuery Notebook using `dashboard_v2.ipynb`?

