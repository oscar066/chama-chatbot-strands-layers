# Chama Chatbot (Artbridge RAG Agent)

A scalable, serverless AI chatbot built for Artbridge. It leverages **AWS Bedrock** and **Amazon Titan** for RAG (Retrieval-Augmented Generation) to answer user queries about platform features, team members, and pricing by retrieving context from a PostgreSQL knowledge base.

## 🏗 System Architecture

The project is built on AWS Serverless architecture using the SAM (Serverless Application Model) framework.

### Core Components
1.  **API Gateway (HTTP API)**: 
    - Exposure point for the chatbot.
    - Receives `POST /chat` requests.
2.  **Fulfillment Lambda (`src/fulfillment_lambda`)**: 
    - **Runtime**: Python 3.11
    - **Logic**: Orchestrates the conversation using the **Strands** agentic framework.
    - **Model**: Invokes `openai.gpt-oss-120b-1:0` via Bedrock.
    - **RAG**: Queries a PostgreSQL database (`pgvector`) to find relevant knowledge base articles.
3.  **Document Processor Lambda (`src/document_processor_lambda`)**:
    - **Trigger**: S3 Object Upload (`.pdf`, `.xlsx`, `.csv`, `.txt`).
    - **Action**: Extracts text, chunks it (with safety logic for large Excel files), generates embeddings using `amazon.titan-embed-text-v2:0`, and upserts them into Postgres.
4.  **Database (RDS/Postgres)**:
    - Stores conversation history.
    - Stores vector embeddings for the knowledge base.

### Dependency Management (Layers)
To adhere to Lambda size limits, dependencies are split:
- **`CommonDepsLayer`**: Lightweight deps used by the Fulfillment Lambda (`requests`, `boto3`, `strands`).
- **`DocDepsLayer`**: Heavy deps used *only* by the Document Processor (`pandas`, `numpy`, `openpyxl`).

---

## 🚀 Deployment

### Prerequisites
- AWS CLI & SAM CLI installed.
- Docker (required for building layers).
- Access to the AWS account.

### Build & Deploy
1. **Build** the application (using Docker to ensure binary compatibility):
   ```bash
   sam build --use-container
   ```

2. **Deploy** to AWS:
   ```bash
   sam deploy
   ```

---

## 🔌 API Usage

**Endpoint**: `https://5bx5m08pud.execute-api.eu-west-1.amazonaws.com/Prod/chat`  
**Method**: `POST`  
**Content-Type**: `application/json`

### Request Format
```json
{
  "query": "Your question here",
  "user_id": "unique_user_identifier"
}
```

### Response Format
```json
{
  "response": "The chatbot's answer generated from the knowledge base.",
  "user_id": "unique_user_identifier"
}
```

---

## ✅ Live Verification Examples

The following examples demonstrate the chatbot's RAG capabilities using the current production build.

### Example 1: Platform Pricing
**Request:**
```bash
curl -X POST https://5bx5m08pud.execute-api.eu-west-1.amazonaws.com/Prod/chat \
-H "Content-Type: application/json" \
-d '{"query": "What commissions does Artbridge charge?", "user_id": "demo_user"}'
```

**Response:**
> "Artbridge charges an **8% platform fee** on each sale. This fee covers the core services of the marketplace, including transaction processing, marketing, and access to the platform’s AI‑powered tools. Additional optional services—such as profile boosts or tip‑jar processing—have their own separate rates."

### Example 2: Team Information
**Request:**
```bash
curl -X POST https://5bx5m08pud.execute-api.eu-west-1.amazonaws.com/Prod/chat \
-H "Content-Type: application/json" \
-d '{"query": "Who are the team members of Artbridge?", "user_id": "demo_user"}'
```

**Response:**
> "Here are the core members of the Artbridge leadership team:
>
> | Name | Role | Brief background |
> |------|------|-------------------|
> | **Asim Al‑Mufti** | Founder & CEO | 7+ years in strategy consulting; previously led growth strategy at Swift Scale |
> | **Elton Maynard** | AI/ML Product Leader | 8+ years in technology, investment banking, and consulting |
> | **Laila Ali** | Engineering Lead | 16+ years in tech, project, and product management |
> | **Zahi Umar** | Co‑founder & Partnerships | 25+ years in apparel and retail |
>
> These leaders drive Artbridge’s product development, AI/ML capabilities, engineering, and partnership strategy."

---

## 📂 Project Structure

```
chama/
├── layers/                  # Lambda Layers
│   ├── common-deps/         # Lightweight dependencies
│   ├── doc-deps/            # Heavy processing libraries (Pandas/Numpy)
│   └── shared-logic/        # Shared Python modules (Tools, DB Utils, Config)
├── src/
│   ├── fulfillment_lambda/  # Chatbot Agent Logic
│   └── document_processor/  # S3 File Processing Logic
├── template.yaml            # AWS SAM Template
└── README.md                # Project Documentation
```
