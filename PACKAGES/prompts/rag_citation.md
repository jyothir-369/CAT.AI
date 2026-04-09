# RAG Citation Instructions

The following document chunks have been retrieved from the workspace knowledge base
and are relevant to the user's question. Use this information to inform your answer.

## Instructions
- Cite sources inline using [source: {filename}, chunk {chunk_index}] notation
- Only cite chunks that you actually use in your response
- If chunks contradict each other, note the discrepancy
- If the retrieved context is insufficient, say so and answer from general knowledge
- Do not fabricate information not present in the chunks or your training data

## Retrieved context
{rag_context}

## User question
{user_message}

Answer (with inline citations):