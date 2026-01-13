import logging
import os

# --- Configuration & Setup ---
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Using your specific model ID
GENERATION_MODEL_ID = 'anthropic.claude-3-haiku-20240307-v1:0'
EMBEDDING_MODEL_ID = 'amazon.titan-embed-text-v2:0'

CONVERSATION_TABLE_NAME = os.environ.get('CONVERSATION_TABLE')
DB_HOST = os.environ.get('DB_HOST')
DB_NAME = os.environ.get('DB_NAME', 'postgres')
DB_USER = os.environ.get('DB_USER')
DB_PASS = os.environ.get('DB_PASSWORD')
DB_PORT = os.environ.get('DB_PORT', '5432')