import json
from strands import Agent
from strands.models import BedrockModel
from config import logger, GENERATION_MODEL_ID

from db_utils import store_conversation
import tools

#  Model & Agent Initialization
# 2. Initialize the BedrockModel explicitly
bedrock_llm = BedrockModel(
    model_id=GENERATION_MODEL_ID,
    temperature=0.0, 
    streaming=False
)

# 3. Pass the initialized bedrock_llm object to the Agent
agent = Agent(
    tools=[tools.search_knowledge_base],
    model=bedrock_llm,
    system_prompt="""You are a helpful AI assistant. Respond professionally and warmly.

    GUIDELINES:
    1. GREETINGS: If the user greets you, respond politely and ask how you can help.
    2. KNOWLEDGE: If the user asks about Company Info, Product Info, or Support, you MUST use the 'search_knowledge_base' tool.
    3. FALLBACK: If you do not understand the query or it is unrelated to the business, apologize and ask the user to rephrase.
    4. Provide direct, concise answers based on the tool output.

    CRITICAL:
    - When invoking tools, do NOT output any reasoning, commentary, or thoughts. Output ONLY the tool use structure.
    - Do NOT use custom roles or delimiters like '<|channel|>'.
    """
)

def lambda_handler(event, context):
    logger.info(f"Received event: {json.dumps(event)}")
    
    try:
        # 1. Parse Input (API Gateway)
        body = json.loads(event.get('body', '{}'))
        raw_user_query = body.get('query', '').strip()
        user_id = body.get('user_id', '').strip()

        if not raw_user_query or not user_id:
            return {
                'statusCode': 400, 
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'error': 'Missing query or user_id'})
            }

        # Store the ORIGINAL message the user typed
        store_conversation(user_id, raw_user_query, 'user')
        
        # 2. Execute Strands Agent (Directly with user query)
        agent_response_raw = agent(raw_user_query)
        
        # Clean response
        final_response = str(agent_response_raw).strip()

        # Remove reasoning tags if present
        if '</reasoning>' in final_response:
            final_response = final_response.split('</reasoning>')[-1].strip()

        # Store the FINAL message the user sees
        store_conversation(user_id, final_response, 'bot')

        # 3. Return Response (API Gateway Format)
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'response': final_response, 
                'user_id': user_id,
            })
        }
        
    except Exception as e:
        logger.error(f"Unhandled error: {e}", exc_info=True)
        return {
            'statusCode': 500, 
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'error': "Technical difficulties."})
        }