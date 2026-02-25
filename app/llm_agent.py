from openai import OpenAI

from app.config import LLM_MODEL, OPENROUTER_API_KEY, SUPPORT_EMAIL

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

SYSTEM_PROMPT = """You are a helpful and professional customer support agent. Your role is to:
- Respond to customer support tickets in a friendly, clear, and empathetic way.
- Acknowledge the customer's issue and provide actionable guidance or next steps.
- If you cannot fully resolve the issue, suggest escalating to a human agent or provide a timeline.
- Keep responses concise but complete (2-4 short paragraphs typically).
- Use a professional but warm tone. Do not use jargon unless the customer did."""


def get_support_response(subject: str, description: str, customer_email: str) -> str:
    """Generate an AI support response for a ticket via OpenRouter."""
    if not OPENROUTER_API_KEY:
        contact = (SUPPORT_EMAIL or customer_email).strip()
        return (
            "Thank you for your ticket. Our AI support is not configured (missing OPENROUTER_API_KEY). "
            f"A team member will respond to you at {contact} shortly."
        )

    try:
        client = OpenAI(base_url=OPENROUTER_BASE_URL, api_key=OPENROUTER_API_KEY)
        user_message = (
            f"Customer email: {customer_email}\n"
            f"Subject: {subject}\n\n"
            f"Message:\n{description}"
        )

        response = client.chat.completions.create(
            model=LLM_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
            max_tokens=500,
            temperature=0.7,
        )
        return response.choices[0].message.content or ""
    except Exception as e:
        contact = (SUPPORT_EMAIL or customer_email).strip()
        return (
            "Thank you for your ticket. We could not generate an AI response right now "
            f"(error: {str(e)}). "
            f"A team member will respond to you at {contact} shortly."
        )


CHAT_SYSTEM_PROMPT = """You are a helpful and professional customer support agent in a live chat. Your role is to:
- Reply in a friendly, clear, and empathetic way.
- Use the conversation history to provide consistent, contextual help.
- Keep responses concise (1-3 short paragraphs) unless more detail is needed.
- If you cannot resolve the issue, suggest escalating to a human agent.
- Use a professional but warm tone. Do not use jargon unless the customer did."""


def get_chat_response(
    messages: list[dict],
    customer_email: str,
    subject: str | None = None,
) -> str:
    """Generate an AI reply in a multi-turn chat via OpenRouter.
    messages: list of {"role": "user"|"assistant", "content": "..."}
    """
    if not OPENROUTER_API_KEY:
        contact = (SUPPORT_EMAIL or customer_email).strip()
        return (
            "Our AI chat is not configured (missing OPENROUTER_API_KEY). "
            f"A team member will respond to you at {contact} shortly."
        )

    try:
        client = OpenAI(base_url=OPENROUTER_BASE_URL, api_key=OPENROUTER_API_KEY)
        system_content = CHAT_SYSTEM_PROMPT
        if subject:
            system_content += f"\n\nConversation topic (optional context): {subject}"
        system_content += f"\n\nCustomer email (for reference only): {customer_email}"

        api_messages = [{"role": "system", "content": system_content}]
        for m in messages:
            api_messages.append({"role": m["role"], "content": m["content"]})

        response = client.chat.completions.create(
            model=LLM_MODEL,
            messages=api_messages,
            max_tokens=500,
            temperature=0.7,
        )
        return response.choices[0].message.content or ""
    except Exception as e:
        contact = (SUPPORT_EMAIL or customer_email).strip()
        return (
            "We could not generate a response right now "
            f"(error: {str(e)}). "
            f"A team member will respond to you at {contact} shortly."
        )
