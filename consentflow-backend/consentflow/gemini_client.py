"""
consentflow/gemini_client.py — Async Gemini 2.0 Flash LangChain client.

Refactored to use LangChain for:
- Prompt Templates
- Standardized Model Interfaces (ChatGoogleGenerativeAI, ChatOllama)
- Automatic Fallbacks (Gemini 2.0 -> Ollama on failure)
"""
from __future__ import annotations

import logging

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser
from langchain_core.vectorstores import InMemoryVectorStore
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_mistralai import ChatMistralAI, MistralAIEmbeddings
from langchain_ollama import ChatOllama

from consentflow.app.config import settings

logger = logging.getLogger(__name__)

_FALLBACK_REPLY = "I'm having trouble responding right now."


class GeminiClient:
    """
    Async wrapper using LangChain for the Gemini generateContent REST endpoint.
    Falls back to Ollama on quota/rate errors automatically using LangChain fallbacks.
    """

    async def chat(self, memories: list[str], user_message: str) -> str:
        """
        Build a context-aware prompt using LangChain and get a reply.

        Tier 1: Mistral (primary)
        Tier 2: Gemini 2.0 Flash (first fallback)
        Tier 3: Ollama gemma2:2b (immediate fallback on 429 / any error)
        """
        # 1. Setup Prompt Template
        system_prompt = (
            "You are a helpful AI assistant. Use context about the user "
            "naturally — don't say 'based on your profile'. Be warm and conversational. "
            "Keep response under 100 words.\n\n"
            "Here is what you know about this user from their past conversations:\n"
            "{memory_lines}"
        )

        prompt_template = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("human", "{user_message}")
        ])

        # 2. Setup Ollama Fallback Model
        ollama_model = ChatOllama(
            model=settings.ollama_model,
            base_url=settings.ollama_base_url.rstrip("/"),
            temperature=0.7,
            num_predict=200,
        )

        # 3. Setup Gemini Fallback Model
        api_key = settings.gemini_api_key
        if api_key:
            gemini_model = ChatGoogleGenerativeAI(
                model="gemini-2.0-flash",
                google_api_key=api_key,
                temperature=0.7,
                max_tokens=200,
            )
            gemini_chain = gemini_model.with_fallbacks([ollama_model])
        else:
            gemini_chain = ollama_model

        # 4. Setup Mistral Model (primary)
        mistral_api_key = settings.mistral_api_key
        if mistral_api_key:
            mistral_model = ChatMistralAI(
                model=settings.mistral_model,
                mistral_api_key=mistral_api_key,
                temperature=0.7,
                max_tokens=200,
            )
            model_chain = mistral_model.with_fallbacks([gemini_chain])
        else:
            logger.warning("MISTRAL_API_KEY not set — using Gemini/Ollama fallback directly")
            model_chain = gemini_chain

        # 5. Build LangChain RAG pipeline
        try:
            if memories and mistral_api_key:
                # Use Mistral Embeddings and InMemoryVectorStore for proper RAG
                embeddings = MistralAIEmbeddings(mistral_api_key=mistral_api_key)
                vector_store = await InMemoryVectorStore.afrom_texts(memories, embedding=embeddings)
                retriever = vector_store.as_retriever(search_kwargs={"k": 3})
                
                def format_docs(docs) -> str:
                    return "\n".join(f"- {doc.page_content}" for doc in docs)
                
                chain = (
                    {"memory_lines": retriever | format_docs, "user_message": RunnablePassthrough()}
                    | prompt_template
                    | model_chain
                    | StrOutputParser()
                )
                
                response = await chain.ainvoke(user_message)
                return response
            else:
                # Fallback to stuffing if no memories or no API key
                memory_lines = "\n".join(f"- {m}" for m in memories) if memories else ""
                chain = prompt_template | model_chain | StrOutputParser()
                response = await chain.ainvoke({
                    "memory_lines": memory_lines,
                    "user_message": user_message
                })
                return response
        except Exception as exc:  # noqa: BLE001
            logger.error("LangChain AI/RAG call failed: %s", exc)
            return _FALLBACK_REPLY


# ── Singleton ──────────────────────────────────────────────────────────────────

gemini_client = GeminiClient()

