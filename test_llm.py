import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv('.env.agent.secret')

client = OpenAI(
    api_key=os.getenv('LLM_API_KEY'),
    base_url=os.getenv('LLM_API_BASE'),
)

response = client.chat.completions.create(
    model=os.getenv('LLM_MODEL'),
    messages=[{"role": "user", "content": "Say hello in one word"}],
)

print(response.choices[0].message.content)
