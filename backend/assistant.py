# assistant.py
# Manages conversation memory and OpenAI tool calling loop.

import json
import os
from pathlib import Path
from datetime import datetime, timedelta
from dotenv import load_dotenv
from openai import OpenAI
from prompts import get_system_prompt
from tools import TOOLS, run_tool

env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=env_path, override=True)

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

MODEL = "gpt-4o-mini"
MAX_HISTORY = 20

conversation_sessions: dict[str, list] = {}


def get_or_create_session(session_id: str) -> list:
    if session_id not in conversation_sessions:
        conversation_sessions[session_id] = [
            {"role": "system", "content": get_system_prompt()}
        ]
        print(f"[SESSION] New session: {session_id}")
    return conversation_sessions[session_id]


def trim_history(messages: list) -> list:
    if len(messages) <= MAX_HISTORY + 1:
        return messages
    return [messages[0]] + messages[-(MAX_HISTORY):]


def inject_date_reminder(user_message: str) -> str:
    """
    Prepends the real current date to every user message.
    This guarantees the AI always knows the correct date,
    even if the session is old or the system prompt was cached.
    """
    now = datetime.now()
    date_str  = now.strftime("%Y-%m-%d")      # e.g. 2026-05-14
    day_name  = now.strftime("%A")            # e.g. Wednesday
    full_date = now.strftime("%B %d, %Y")     # e.g. May 14, 2026

    # FIX: was using now.replace(day=now.day+1) which crashed on day>=28
    # and produced month=13 in December. timedelta(days=1) is always correct.
    tomorrow     = now + timedelta(days=1)
    tomorrow_str = tomorrow.strftime("%Y-%m-%d")

    reminder = (
        f"[SYSTEM DATE REMINDER: Today is {day_name}, {full_date}. "
        f"ISO date: {date_str}. Tomorrow is {tomorrow_str}. "
        f"Always use {now.year} as the year for all reservations.]\n\n"
    )
    return reminder + user_message


def chat(session_id: str, user_message: str) -> str:
    messages = get_or_create_session(session_id)

    # Always update the system prompt with today's real date
    # This fixes old sessions that were created with a stale prompt
    messages[0] = {"role": "system", "content": get_system_prompt()}

    # Inject today's date into the user message itself
    stamped_message = inject_date_reminder(user_message)
    messages.append({"role": "user", "content": stamped_message})
    messages = trim_history(messages)
    conversation_sessions[session_id] = messages

    print(f"[CHAT] {session_id} | User: {user_message}")
    print(f"[DATE] Injected: {datetime.now().strftime('%Y-%m-%d')}")

    response = client.chat.completions.create(
        model=MODEL,
        messages=messages,
        tools=TOOLS,
        tool_choice="auto",
        temperature=0.7
    )

    response_message = response.choices[0].message

    while response_message.tool_calls:
        messages.append(response_message)
        for tool_call in response_message.tool_calls:
            tool_name = tool_call.function.name
            tool_args = json.loads(tool_call.function.arguments)
            print(f"[TOOL] Calling: {tool_name} | Args: {tool_args}")
            tool_result = run_tool(tool_name, tool_args)
            print(f"[TOOL] Result: {tool_result}")
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": tool_result
            })
        response = client.chat.completions.create(
            model=MODEL, messages=messages,
            tools=TOOLS, tool_choice="auto", temperature=0.7
        )
        response_message = response.choices[0].message

    final_reply = response_message.content or "I am sorry, I did not catch that. Could you repeat?"
    messages.append({"role": "assistant", "content": final_reply})
    conversation_sessions[session_id] = messages

    print(f"[CHAT] Reply: {final_reply}")
    return final_reply


def clear_session(session_id: str):
    if session_id in conversation_sessions:
        del conversation_sessions[session_id]
        print(f"[SESSION] Cleared: {session_id}")
