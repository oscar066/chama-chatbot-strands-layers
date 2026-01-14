# Chama Chatbot

A scalable, serverless AI chatbot built for **Artbridge**. It leverages **AWS Bedrock** and **Amazon Titan** for RAG (Retrieval-Augmented Generation) to answer user queries about platform features, team members, and pricing by retrieving context from a PostgreSQL knowledge base.

> **📖 Full Documentation**: For detailed architecture, setup, troubleshooting, and extension guides, please see [DOCUMENTATION.md](DOCUMENTATION.md).

## 🏗 System Architecture

The project is built on AWS Serverless architecture using the **SAM (Serverless Application Model)** framework.

### Core Components
1.  **API Gateway (REST API)**: Exposes the `POST /chat` endpoint, secured by an API Key.
2.  **Fulfillment Lambda**: Python-based Lambda that orchestrates the conversation using the **Strands** agentic framework and **Claude 3.5 Sonnet v2**.
3.  **Document Processor Lambda**: Automatically processes uploaded documents (PDF, Excel, etc.) from S3, generates embeddings, and updates the knowledge base.
4.  **Database**: External PostgreSQL (RDS) with `pgvector` for storing embeddings and conversation history.

## 🚀 Quick Start

### Prerequisites
- AWS CLI & SAM CLI installed.
- Docker (for building layers).
- Access to the target AWS account.
- `api-key` (generated after deployment).

### Build & Deploy
```bash
# Build the application (containers required for native deps)
sam build --use-container

# Deploy to AWS
sam deploy --guided
```

## 🔌 API Usage

**Endpoint**: `https://<api-id>.execute-api.<region>.amazonaws.com/Prod/chat`
**Headers**:
- `Content-Type`: `application/json`
- `x-api-key`: `<YOUR_API_KEY>`

**Request:**
```json
{
  "query": "What commissions does Artbridge charge?",
  "user_id": "demo_user"
}
```

**Response:**
```json
{
  "response": "Artbridge charges an 8% platform fee...",
  "user_id": "demo_user"
}
```

## 📂 Project Structure

```
chama/
├── layers/                  # Lambda Layers
│   ├── common-deps/         # Lightweight dependencies (requests, strands)
│   ├── doc-deps/            # Heavy processing libraries (pandas, numpy)
│   └── shared-logic/        # Shared Python modules (Tools, Config, DB Utils)
├── src/
│   ├── fulfillment_lambda/  # Main Chatbot Agent Logic
│   └── document_processor/  # S3 File ingestion & embedding logic
├── template.yaml            # AWS SAM Template
├── DOCUMENTATION.md         # Detailed System Documentation
└── README.md                # Overview
```
