import os
from langchain_groq import ChatGroq

groq_api_key = os.environ.get("GROQ_API_KEY", "")

def get_groq_llm():
    return ChatGroq(
        api_key=groq_api_key,
        model="llama-3.3-70b-versatile",
        temperature=0,
        max_tokens=2048
    )

supervisor_llm = get_groq_llm()
logs_llm = get_groq_llm()
metrics_llm = get_groq_llm()
deploy_intelligence_llm = get_groq_llm()

__all__ = [
    "supervisor_llm",
    "logs_llm",
    "metrics_llm",
    "deploy_intelligence_llm",
]