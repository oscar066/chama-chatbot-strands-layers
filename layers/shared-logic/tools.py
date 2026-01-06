import json
import boto3
import os
import logging
import psycopg2
from strands.tools import tool
from config import logger, DB_HOST, DB_NAME, DB_USER, DB_PASS, DB_PORT, EMBEDDING_MODEL_ID

bedrock = boto3.client('bedrock-runtime')

def get_db_connection():
    """Establishes a connection to the PostgreSQL database."""
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASS,
            port=DB_PORT
        )
        return conn
    except Exception as e:
        logger.error(f"Error connecting to database: {e}")
        raise e

def get_embedding(text):
    """Generates an embedding for the given text using Amazon Titan."""
    body = json.dumps({"inputText": text})
    response = bedrock.invoke_model(
        body=body,
        modelId=EMBEDDING_MODEL_ID,
        contentType='application/json',
        accept='application/json'
    )
    response_body = json.loads(response.get('body').read())
    return response_body.get('embedding')

@tool
def search_knowledge_base(query: str) -> str:
    """
    Search the Pula Pitch knowledge base for information related to the user's query.
    Use this tool whenever the user asks about Pula Pitch features, missions, pricing, or support.
    
    Args:
        query: The search terms or question from the user.
        
    Returns:
        A string containing relevant information from the knowledge base.
    """
    conn = None
    try:
        logger.info(f"RAG Tool: Searching for '{query}'")
        query_embedding = get_embedding(query)
        keyword_query = query.replace("'", "").replace(";", "")
        
        conn = get_db_connection()
        cur = conn.cursor()
        
        sql = """
        WITH semantic_search AS (
            SELECT id, content, RANK() OVER (ORDER BY embedding <=> %s::vector) as rank
            FROM embeddings
            ORDER BY embedding <=> %s::vector
            LIMIT 20
        ),
        keyword_search AS (
            SELECT id, content, RANK() OVER (ORDER BY ts_rank_cd(fts, websearch_to_tsquery('english', %s)) DESC) as rank
            FROM embeddings
            WHERE fts @@ websearch_to_tsquery('english', %s)
            LIMIT 20
        )
        SELECT 
            COALESCE(s.content, k.content) as content,
            (COALESCE(1.0 / (60 + s.rank), 0.0) + COALESCE(1.0 / (60 + k.rank), 0.0)) as rrf_score
        FROM semantic_search s
        FULL OUTER JOIN keyword_search k ON s.id = k.id
        ORDER BY rrf_score DESC
        LIMIT 5;
        """
        
        cur.execute(sql, (query_embedding, query_embedding, keyword_query, keyword_query))
        hits = cur.fetchall()
        
        contexts = [hit[0] for hit in hits]
        cur.close()
        
        if not contexts:
            return "No relevant information found in the knowledge base."
            
        return "\n\n---\n\n".join(contexts)
    except Exception as e:
        logger.error(f"Error in RAG tool: {e}")
        return f"Error retrieving information: {str(e)}"
    finally:
        if conn:
            conn.close()
