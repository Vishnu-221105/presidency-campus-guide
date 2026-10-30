# Presidency University Campus Guide

Streamlit campus navigation assistant with Gemini photo identification, a Plotly campus map, NetworkX shortest-path routing, and a RAG knowledge search pipeline.

## RAG pipeline

1. Campus directory facts are split into overlapping word chunks.
2. `sentence-transformers/all-MiniLM-L6-v2` creates normalized embeddings.
3. ChromaDB stores the embeddings in an in-memory collection.
4. A query embedding retrieves the configured Top-K most similar chunks.
5. Gemini can phrase an answer using retrieved context; NetworkX remains responsible for route calculation.

The initial knowledge base is generated from the campus locations and draft route graph already in the application. It is a starter directory, not an official campus handbook. Office hours, exact positions, and walking connections are not independently verified.

## Run locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

Set `GEMINI_API_KEY` as an environment variable or in Streamlit Community Cloud Secrets. Never commit API keys.
