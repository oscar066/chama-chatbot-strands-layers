import boto3
import time
from config import logger, CONVERSATION_TABLE_NAME

dynamodb = boto3.resource('dynamodb')
conversation_table = dynamodb.Table(CONVERSATION_TABLE_NAME)

def store_conversation(user_id, message, role, session_id='default-session'):
    """Stores conversation history in DynamoDB."""
    try:
        conversation_table.put_item(
            Item={
                'user_id': user_id,
                'timestamp': int(time.time()),
                'session_id': session_id,
                'message': message,
                'role': role
            }
        )
    except Exception as e:
        logger.error(f"Error storing conversation to DynamoDB: {e}")
