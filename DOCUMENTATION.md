# Project Documentation: Chama Chatbot

This documentation allows developers and administrators to understand, maintain, and extend the **Chama Chatbot** system. The system is a serverless RAG (Retrieval-Augmented Generation) chatbot built on AWS, using Bedrock for LLMs and PostgreSQL (pgvector) for the knowledge base.

## 1. System Architecture & Components

The infrastructure is defined as code using **AWS SAM (Serverless Application Model)** in `template.yaml`.

### CloudFormation Resources
The following components are deployed via the CloudFormation template:

#### Storage
- **S3 Bucket (`KnowledgeBaseBucket`)**: Stores raw documents (PDF, Excel, etc.) uploaded by administrators.
  - *Trigger*: Uploads to this bucket trigger the `DocumentProcessorLambdaFunction`.
- **DynamoDB Table (`ConversationsTable`)**: Stores conversation history (User and Bot messages) for context retention.
- **RDS (External)**: The system connects to an existing PostgreSQL RDS instance (`parawise-prod`) which must have the `vector` extension enabled for `pgvector` support.

#### Compute (Lambda)
- **`FulfillmentLambdaFunction`**: The core chatbot logic.
  - **Runtime**: Python 3.11
  - **Role**: Handles user queries, maintains state, calls the LLM, and executes tools.
- **`DocumentProcessorLambdaFunction`**: Processes uploaded documents.
  - **Runtime**: Python 3.11
  - **Role**: Reads files from S3, chunks text, generates embeddings, and saves them to the PostgreSQL `embeddings` table.

#### Lambda Layers
To manage dependencies efficiently, the project uses three layers:
1. **`CommonDepsLayer`**: Lightweight dependencies like `psycopg2`, `strands`, `requests`.
2. **`DocDepsLayer`**: Heavy dependencies needed *only* for document processing (e.g., `pandas`, `numpy`). Attached only to the Document Processor.
3. **`SharedLogicLayer`**: Internal business logic shared across functions (`config.py`, `db_utils.py`, `tools.py`).

#### API & Security
- **API Gateway (`ChamaRestApi`)**: Exposes the chatbot via a REST API.
- **API Key (`ChamaApiKey`)**: Secures the API. Clients *must* include the `x-api-key` header in requests.
- **Usage Plan (`ChamaUsagePlan`)**: Limits traffic to prevent abuse (default: 1000 requests/day, 5 requests/sec rate limit).

---

## 2. Knowledge Base & Embeddings

The system uses a **Hybrid Search** approach (Semantic + Keyword) stored in PostgreSQL.

### Implementation Details
- **Vector Extension**: The RDS database uses `pgvector` to store embeddings.
- **Embedding Model**: `amazon.titan-embed-text-v2:0` (defined in `config.py`).
- **Hybrid Search Logic**: The `search_knowledge_base` tool in `tools.py` performs two queries:
  1. **Semantic Search**: Uses Cosine Similarity (`<=>` operator) on vector embeddings.
  2. **Keyword Search**: Uses PostgreSQL's Full-Text Search (`ts_vector`).
  - **Fusion**: Results are combined using **Reciprocal Rank Fusion (RRF)** to prioritize the most relevant matches.

---

## 3. Getting Started

### Prerequisites
- AWS CLI & SAM CLI installed.
- Access to the `parawise-prod` RDS instance.
- Python 3.11.

### Deployment
To deploy the stack:
```bash
sam build
sam deploy --guided
```

### Using the API
Once deployed, use the Output URL (`ApiEndpoint`) and the generated API Key.

**Request:**
```http
POST /chat
x-api-key: <YOUR_API_KEY>
Content-Type: application/json

{
    "user_id": "user123",
    "query": "How do I apply for a loan?"
}
```

---

## 4. How to Manage Content (Knowledge Base)

To add new knowledge to the chatbot, you do not need to modify code.

1. **Prepare Document**: Create a PDF, Excel, or Text file containing the information.
2. **Upload to S3**: Upload the file to the `KnowledgeBaseBucket`.
   - You can use the AWS Console or CLI:
     ```bash
     aws s3 cp my-doc.pdf s3://<project-name>-knowledge-base-<account-id>/
     ```
3. **Automatic Processing**:
   - The upload triggers `DocumentProcessorLambdaFunction`.
   - The function extracts text, chunks it, creates embeddings, and inserts them into the RDS `embeddings` table.
   - **Verification**: You can check the CloudWatch logs for `DocumentProcessorLambdaFunction` to confirm the upload was processed successfully.

---

## 5. Configuration & Troubleshooting

### Common Errors

#### 1. ThrottlingException (10 RPM Limit)
**Issue**: You receive throttling errors or slow responses.
**Cause**: The project is currently configured to use **Claude 3.5 Sonnet v2** (`eu.anthropic.claude-sonnet-4-5-20250929-v1:0`), which often has a low default quota (e.g., 10 RPM) in some regions.

**Solution**: Switch to a model with higher throughput (e.g., Claude 3 Haiku or Titan Express).

1. Open `layers/shared-logic/config.py`.
2. Update `GENERATION_MODEL_ID`:
   ```python
   # layers/shared-logic/config.py
   
   # CURRENT
   # GENERATION_MODEL_ID = 'eu.anthropic.claude-sonnet-4-5-20250929-v1:0'
   
   # CHANGE TO (Example: Claude 3 Haiku)
   GENERATION_MODEL_ID = 'anthropic.claude-3-haiku-20240307-v1:0'
   ```
3. Redeploy logic layer: `sam build && sam deploy`.

#### 2. Postgres Connection Errors
**Issue**: Logs show timeout or authentication failure connecting to DB.
**Check**:
- Ensure the Security Group for the RDS instance allows inbound traffic from the Lambda functions' security group (or VPC CIDR).
- Verify `DB_HOST`, `DB_USER`, and `DB_PASSWORD` are correct in the Lambda environment variables.

---

## 6. Extending the Agent

The agent is built using the **Strands** framework. To add new capabilities, you need to define a tool and register it with the agent.

### Step 1: Add a New Tool
Create a new function in `layers/shared-logic/tools.py` and decorate it with `@tool`.

**Example: Add a "weather" tool**
```python
# layers/shared-logic/tools.py
from strands.tools import tool

@tool
def check_weather(city: str) -> str:
    """
    Get the current weather for a specific city.
    
    Args:
        city: The name of the city (e.g., "Nairobi").
    """
    # Logic to fetch weather (e.g., external API call)
    return f"The weather in {city} is Sunny, 25°C."
```

### Step 2: Register the Tool
Update the agent initialization in `src/fulfillment_lambda/app.py` to include the new tool.

```python
# src/fulfillment_lambda/app.py
import tools

# ... code ...

agent = Agent(
    tools=[
        tools.search_knowledge_base,
        tools.check_weather  # <--- ADD YOUR NEW TOOL HERE
    ],
    model=bedrock_llm,
    system_prompt="..."
)
```

### Step 3: Update System Prompt (Optional)
If the tool requires specific instructions (e.g., strict rules on when to use it), update the `system_prompt` in `src/fulfillment_lambda/app.py`.

```python
system_prompt="""You are a helpful AI assistant.
...
GUIDELINES:
- Use 'check_weather' ONLY when the user explicitly asks for weather conditions.
...
"""
```

### Step 4: Redeploy
Run `sam build && sam deploy` to apply the changes.
