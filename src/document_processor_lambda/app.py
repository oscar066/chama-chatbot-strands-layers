import json
import boto3
import os
import logging
import io
import csv
import re
import time
import random
import urllib.parse
import psycopg2
import PyPDF2
import pandas as pd

from botocore.exceptions import ClientError

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize clients
s3 = boto3.client('s3')
bedrock = boto3.client('bedrock-runtime')

# DB Config
db_host = os.environ.get('DB_HOST')
db_name = os.environ.get('DB_NAME', 'parawise_db')
db_user = os.environ.get('DB_USER')
db_pass = os.environ.get('DB_PASSWORD')
db_port = os.environ.get('DB_PORT', '5432')

def get_db_connection():
    """Establishes a connection to the PostgreSQL database."""
    try:
        conn = psycopg2.connect(
            host=db_host,
            database=db_name,
            user=db_user,
            password=db_pass,
            port=db_port
        )
        return conn
    except Exception as e:
        logger.error(f"Error connecting to database: {e}")
        raise e

def get_embedding(text, max_retries=5):
    """
    Generates an embedding using Amazon Titan with exponential backoff.
    """
    body = json.dumps({"inputText": text})
    for attempt in range(max_retries):
        try:
            response = bedrock.invoke_model(
                body=body,
                modelId='amazon.titan-embed-text-v2:0',
                contentType='application/json',
                accept='application/json'
            )
            response_body = json.loads(response.get('body').read())
            return response_body.get('embedding')
        except ClientError as e:
            if e.response['Error']['Code'] == 'ThrottlingException':
                wait_time = (2 ** attempt) + random.uniform(0, 1)
                logger.warning(f"ThrottlingException. Retrying in {wait_time:.2f}s...")
                time.sleep(wait_time)
            else:
                logger.error(f"Bedrock error: {e}")
                raise e
        except Exception as e:
            logger.error(f"Error generating embedding: {e}")
            return None
    return None

def process_pdf(pdf_content):
    """Extracts text from PDF."""
    try:
        pdf_file = io.BytesIO(pdf_content)
        reader = PyPDF2.PdfReader(pdf_file)
        text = ""
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
        return text.strip()
    except Exception as e:
        logger.error(f"Error processing PDF: {e}")
        return ""

def process_csv(csv_content):
    """Extracts text from CSV."""
    try:
        csv_string = csv_content.decode('utf-8')
        reader = csv.reader(io.StringIO(csv_string))
        faqs = []
        next(reader, None) # Skip header
        for row in reader:
            if len(row) >= 2 and row[0].strip() and row[1].strip():
                faqs.append(f"Q: {row[0].strip()}\nA: {row[1].strip()}")
        return "\n\n".join(faqs)
    except Exception as e:
        logger.error(f"Error processing CSV: {e}")
        return ""

def process_excel(file_content):
    """Extracts text from Excel (.xls, .xlsx)."""
    try:
        excel_file = io.BytesIO(file_content)
        # Read all sheets
        dict_df = pd.read_excel(excel_file, sheet_name=None)
        all_text = []
        
        for sheet_name, df in dict_df.items():
            all_text.append(f"--- Sheet: {sheet_name} ---")
            # Filter out empty rows and columns
            df = df.dropna(how='all').dropna(axis=1, how='all')
            if not df.empty:
                # Convert to string representation (TSV-like for readability)
                all_text.append(df.to_string(index=False))
        
        return "\n\n".join(all_text).strip()
    except Exception as e:
        logger.error(f"Error processing Excel: {e}")
        return ""

def clean_text(text):
    """Cleans extracted text to remove TOC noise."""
    if not text: return ""
    lines = text.splitlines()
    cleaned_lines = []
    for line in lines:
        if line.count('.') > 10: continue
        cleaned_lines.append(line)
    return "\n".join(cleaned_lines).strip()

def chunk_text(text, chunk_size=400, max_chars=8000):
    """
    Splits text into chunks respecting sentence boundaries, but forces a split
    if a segment is too long (e.g. excel data without punctuation).
    chunk_size: approximate words.
    max_chars: strict character limit per chunk (Safety for Bedrock).
    """
    if not text: return []
    
    # 1. Split by sentence endings (. ! ?) using regex
    # If no punctuation, this returns the whole text as one item.
    sentences = re.split(r'(?<=[.!?]) +', text)
    
    chunks = []
    current_chunk = []
    current_length = 0 # in words
    current_char_count = 0 
    
    for sentence in sentences:
        # 2. Safety check: If a single "sentence" is massive (e.g. data table), hard split it
        if len(sentence) > max_chars:
            # Force flush current chunk
            if current_chunk:
                chunks.append(" ".join(current_chunk))
                current_chunk = []
                current_length = 0
                current_char_count = 0
            
            # Sub-chunk this massive block by rigid character count
            # Overlap slightly to maintain context
            step = max_chars - 200 
            for i in range(0, len(sentence), step):
                chunks.append(sentence[i : i + max_chars])
            continue

        # Normal processing
        word_count = len(sentence.split())
        char_count = len(sentence)
        
        # Check standard limits (word count OR char count safety)
        if (current_length + word_count > chunk_size) or (current_char_count + char_count > max_chars):
            if current_chunk:
                chunks.append(" ".join(current_chunk))
            
            # Overlap logic (Keep last sentence)
            if len(current_chunk) > 0:
                last_sent = current_chunk[-1]
                # Only keep it if it's not huge
                if len(last_sent) < max_chars // 2:
                    current_chunk = [last_sent]
                    current_length = len(last_sent.split())
                    current_char_count = len(last_sent)
                else:
                    current_chunk = []
                    current_length = 0
                    current_char_count = 0
            else:
                current_chunk = []
                current_length = 0
                current_char_count = 0
        
        current_chunk.append(sentence)
        current_length += word_count
        current_char_count += char_count
    
    if current_chunk:
        chunks.append(" ".join(current_chunk))
        
    return chunks

def index_in_pgvector(document_id, content):
    """
    Indexes content using the optimized table structure.
    """
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        logger.info(f"Deleting existing documents for: {document_id}")
        cur.execute("DELETE FROM embeddings WHERE document_id = %s", (document_id,))
        
        chunks = chunk_text(content)
        if not chunks:
            logger.warning(f"No chunks to index for {document_id}")
            return False

        logger.info(f"Indexing {len(chunks)} chunks for {document_id}...")
        
        for i, chunk in enumerate(chunks):
            embedding = get_embedding(chunk)
            if embedding:
                # Note: We do NOT insert into 'fts'. 
                # The Postgres trigger 'tsvectorupdate' handles keyword tokenization automatically.
                cur.execute(
                    """
                    INSERT INTO embeddings (document_id, chunk_id, content, embedding) 
                    VALUES (%s, %s, %s, %s::vector)
                    """,
                    (document_id, i, chunk, embedding)
                )
            time.sleep(0.1) # Prevent rate limiting
        
        conn.commit()
        logger.info(f"Successfully indexed {document_id}")
        return True
    except Exception as e:
        logger.error(f"Indexing error: {e}")
        if conn: conn.rollback()
        return False
    finally:
        if conn: conn.close()

def lambda_handler(event, context):
    """Main handler to process S3 documents."""
    try:
        bucket = event['Records'][0]['s3']['bucket']['name']
        key = urllib.parse.unquote_plus(event['Records'][0]['s3']['object']['key'])
        logger.info(f"Processing: {bucket}/{key}")

        s3_object = s3.get_object(Bucket=bucket, Key=key)
        file_content = s3_object['Body'].read()
        
        extracted_text = ""
        if key.lower().endswith('.pdf'):
            extracted_text = process_pdf(file_content)
        elif key.lower().endswith('.txt'):
            extracted_text = file_content.decode('utf-8')
        elif key.lower().endswith('.csv'):
            extracted_text = process_csv(file_content)
        elif key.lower().endswith(('.xls', '.xlsx')):
            extracted_text = process_excel(file_content)
        else:
            return {'statusCode': 400, 'body': f'Unsupported file type: {key}'}
        
        extracted_text = clean_text(extracted_text)
        
        if extracted_text:
            index_in_pgvector(key, extracted_text)
            return {'statusCode': 200, 'body': f'Successfully processed {key}'}
        
        return {'statusCode': 200, 'body': 'No content extracted'}
    except Exception as e:
        logger.error(f"Handler error: {e}")
        raise e