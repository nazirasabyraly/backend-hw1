import os
import openai
from dotenv import load_dotenv

load_dotenv()
import os
import openai
from dotenv import load_dotenv

load_dotenv()

openai.api_key = os.getenv("OPENAI_API_KEY")

# ID ассистента можно получить через Dashboard или API
ASSISTANT_ID = "asst_JsZWI9QPR3Mk3rMlOFFF6YC8"  # ← вставь свой ID

# Создание сессии (thread) и отправка сообщения
def send_message_to_assistant(message: str):
    thread = openai.beta.threads.create()

    openai.beta.threads.messages.create(
        thread_id=thread.id,
        role="user",
        content=message,
    )

    run = openai.beta.threads.runs.create(
        thread_id=thread.id,
        assistant_id=ASSISTANT_ID,
    )

    # Ждём завершения
    while True:
        status = openai.beta.threads.runs.retrieve(run.id, thread_id=thread.id)
        if status.status == "completed":
            break

    # Получаем ответ
    messages = openai.beta.threads.messages.list(thread_id=thread.id)
    latest = messages.data[0].content[0].text.value
    return latest

openai.api_key = os.getenv("OPENAI_API_KEY")

def ask_openai(prompt: str) -> str:
    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": prompt}
        ]
    )
    return response.choices[0].message["content"]
