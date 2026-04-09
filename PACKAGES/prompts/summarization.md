# Conversation Summarization Prompt

Create a concise summary (maximum 200 words) of the following conversation excerpt.

## Purpose
This summary replaces older messages to free up context window space.
It will be injected at the start of future context as a synthetic "Earlier context" block.

## Requirements
- Write in third person past tense
- Preserve: key facts, user preferences, decisions made, technical details, open questions
- Omit: small talk, repeated questions, resolved misunderstandings
- Be specific — include names, numbers, and technical terms where relevant
- Start with the most important context

## Format
Write as flowing prose (no bullet points). Keep it under 200 words.

Conversation:
{conversation_text}

Summary: