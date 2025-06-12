import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def info_agent(prompt: str) -> str:
    chat_completion = client.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You are an expert researcher who answers with accurate info."},
            {"role": "user", "content": prompt}
        ]
    )
    return chat_completion.choices[0].message.content

