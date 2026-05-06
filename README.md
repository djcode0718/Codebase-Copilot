# 🚀 Codebase Copilot

> An AI-powered codebase intelligence system that understands repositories using hybrid retrieval, reranking, query routing, conversational memory, and evaluation-driven RAG pipelines.

---

# 📌 Overview

**Codebase Copilot** is a modular Retrieval-Augmented Generation (RAG) system designed to help developers understand large and unfamiliar repositories through natural language interaction.

The system combines:

* hybrid retrieval
* semantic search
* BM25 keyword retrieval
* reranking
* query routing
* conversational memory
* evaluation pipelines
* multi-LLM orchestration

to provide both:

✅ low-level code understanding
✅ higher-order architectural reasoning

Unlike simple repository chatbots, this project focuses heavily on:

* retrieval quality
* evaluation methodology
* latency analysis
* modular AI engineering
* production-style RAG architecture

---

# ✨ Key Features

## 🧠 Hybrid Retrieval Pipeline

The system combines:

* dense semantic retrieval
* sparse keyword retrieval (BM25)
* Reciprocal Rank Fusion (RRF)
* reranking pipelines

to improve:

* retrieval precision
* contextual relevance
* architectural understanding

---

## 🔀 Intelligent Query Routing

Queries are automatically classified into:

| Mode            | Purpose                            |
| --------------- | ---------------------------------- |
| `code_lookup`   | strict grounded code explanations  |
| `architectural` | higher-order engineering reasoning |

This enables the system to:

* remain faithful for code lookup
* reason more broadly for design discussions

---

## ⚡ Multi-LLM Support

Supports:

* Ollama (offline/local)
* Groq
* Gemini
* OpenAI

The system supports:

* local inference
* cloud inference
* evaluation-specific switching

through centralized configuration.

---

## 💬 Conversational Memory

Includes:

* multi-turn conversation support
* persistent chat context
* memory-aware prompting
* ChatGPT-style interface

---

## 📊 Evaluation Framework

The project includes a complete evaluation pipeline for measuring:

### Retrieval Quality

* Hit Rate
* MRR (Mean Reciprocal Rank)

### Generation Quality

* Faithfulness
* Relevancy

### System Metrics

* retrieval latency
* reranking latency
* LLM latency
* routing accuracy

---

## 🧩 Advanced Parsing & Chunking

The pipeline supports:

* recursive repository traversal
* metadata-rich chunking
* function-aware splitting
* tree-sitter parsing
* semantic file summaries

---

# 🏗️ System Architecture

```text
                    ┌──────────────────────┐
                    │     Streamlit UI     │
                    └──────────┬───────────┘
                               │
                               ▼
                  ┌────────────────────────┐
                  │      Query Router      │
                  │   Code vs Architecture │
                  └────────┬───────────────┘
                           │
           ┌───────────────┴────────────────┐
           ▼                                ▼
  ┌─────────────────┐            ┌────────────────────┐
  │ Hybrid Retriever│            │ Architectural Flow │
  │  BM25 + Dense   │            │ Contextual Reasoner│
  └────────┬────────┘            └────────┬───────────┘
           │                              │
           └──────────────┬───────────────┘
                          ▼
                ┌──────────────────┐
                │  ColBERT Rerank  │
                └────────┬─────────┘
                         ▼
                ┌──────────────────┐
                │   LlamaIndex     │
                │  Retrieval Core  │
                └────────┬─────────┘
                         ▼
                ┌──────────────────┐
                │   LLM Provider   │
                │ Ollama/Groq/etc  │
                └────────┬─────────┘
                         ▼
                ┌──────────────────┐
                │  Final Response  │
                └──────────────────┘
```

---

# ⚙️ Tech Stack

## AI / Retrieval

* LlamaIndex
* BM25
* ChromaDB
* ColBERT
* Hybrid Retrieval
* Reciprocal Rank Fusion

## LLMs

* Ollama
* Groq
* Gemini
* OpenAI

## Parsing

* tree-sitter
* tree-sitter-language-pack

## Frontend

* Streamlit

## Evaluation

* LlamaIndex Evaluators
* FaithfulnessEvaluator
* RelevancyEvaluator

---

# 📂 Project Structure

```text
codebase-copilot/
│
├── app/
│   │
│   ├── config.py
│   │
│   ├── ingestion/
│   │   ├── repo_loader.py
│   │   └── file_filter.py
│   │
│   ├── parsing/
│   │   ├── code_parser.py
│   │   └── chunk_utils.py
│   │
│   ├── indexing/
│   │   ├── index_builder.py
│   │   ├── vector_store.py
│   │   ├── file_map_builder.py
│   │   └── summary_index_builder.py
│   │
│   ├── retrieval/
│   │   ├── retriever.py
│   │   ├── hybrid_retriever.py
│   │   ├── reranker.py
│   │   ├── ranking.py
│   │   ├── query_router.py
│   │   └── file_map_retriever.py
│   │
│   ├── llm/
│   │   ├── llm_client.py
│   │   └── prompts.py
│   │
│   ├── memory/
│   │   └── chat_memory.py
│   │
│   ├── services/
│   │   ├── repo_service.py
│   │   └── qa_service.py
│   │
│   └── utils/
│       ├── logger.py
│       └── helpers.py
│
├── ui/
│   └── streamlit_app.py
│
├── data/
│   ├── repos/
│   ├── index/
│   └── eval_results*.json
│
├── evaluate.py
├── copy_codes.py
│
├── requirements.txt
├── requirements-llamaindex.txt
│
├── .env
├── .gitignore
└── README.md
```

---

# 🔄 End-to-End Workflow

## 1️⃣ Repository Ingestion

The system accepts:

* GitHub repository URLs
* local repository paths

Repositories are:

* cloned locally
* recursively traversed
* filtered for relevant files

Ignored directories:

```text
node_modules/
.git/
dist/
venv/
__pycache__/
```

---

## 2️⃣ Parsing & Chunking

The parser:

* reads code safely
* extracts metadata
* performs semantic chunking
* generates file-level summaries

Each chunk stores:

* file path
* file name
* entity information
* chunk text
* metadata

---

## 3️⃣ Embedding & Indexing

Dense embeddings:

```text
nomic-embed-text
```

Storage:

```text
ChromaDB
```

Keyword retrieval:

```text
BM25
```

---

## 4️⃣ Hybrid Retrieval

The retrieval system combines:

* semantic retrieval
* keyword retrieval
* file-level retrieval

using:

* QueryFusionRetriever
* Reciprocal Rank Fusion (RRF)

This improves:

* retrieval precision
* architectural reasoning
* contextual grounding

---

## 5️⃣ Reranking

Optional ColBERT reranking improves:

* ranking quality
* retrieval precision
* Mean Reciprocal Rank (MRR)

---

## 6️⃣ Query Routing

Queries are classified into:

* code lookup mode
* architectural reasoning mode

This allows:

* stricter grounded answers
* broader engineering analysis
* better faithfulness control

---

## 7️⃣ Prompt Construction

Prompts include:

* retrieved chunks
* repository summaries
* metadata
* routing instructions
* conversational history

---

## 8️⃣ Conversational Memory

The memory system:

* stores previous interactions
* enables follow-up questions
* preserves context across turns

---

## 9️⃣ LLM Generation

Responses are generated using:

* Ollama
* Groq
* Gemini
* OpenAI

The system supports:

* local inference
* cloud inference
* evaluation-specific LLM switching

---

# 📊 Evaluation Framework

The project includes a dedicated evaluation pipeline.

## Metrics Measured

| Category    | Metrics                        |
| ----------- | ------------------------------ |
| Retrieval   | Hit Rate, MRR                  |
| Generation  | Faithfulness, Relevancy        |
| Routing     | Mode Accuracy                  |
| Performance | Retrieval, rerank, LLM latency |

---

# 📈 Example Evaluation Results

| Metric            | Score     |
| ----------------- | --------- |
| Hit Rate          | 0.80+     |
| MRR               | 0.60+     |
| Faithfulness      | 0.60–0.80 |
| Relevancy         | 0.90+     |
| Routing Accuracy  | 1.00      |
| Retrieval Latency | ~0.1s     |
| Rerank Latency    | ~1s       |
| Local LLM Latency | ~15s      |
| Groq LLM Latency  | ~2–4s     |

---

# 🧠 Key Engineering Insights

## Retrieval Pipeline

The retrieval stack is highly optimized:

* retrieval latency is extremely low (~0.1s)
* reranking adds modest overhead (~1s)
* the primary bottleneck is local LLM inference

---

## Local AI Optimization

The system was optimized specifically for:

* Apple Silicon Macs
* 16GB RAM systems
* local inference workflows

---

## Hallucination Reduction

Implemented using:

* hybrid retrieval
* reranking
* query routing
* retrieval-grounded prompting

---

# 💬 Example Queries

## Code Lookup

```text
How does retrieve_relevant_chunks work?
```

```text
Where is the vector store initialized?
```

```text
How does the indexing pipeline work?
```

---

## Architectural Reasoning

```text
What are the main limitations of this project?
```

```text
How can retrieval quality be improved?
```

```text
What changes are needed for production deployment?
```

---

# 🚀 Running the Project

## 1️⃣ Create Environment

```bash
conda create -n ai-copilot-env python=3.10
conda activate ai-copilot-env
```

---

## 2️⃣ Install Dependencies

```bash
pip install -r requirements-llamaindex.txt
```

---

## 3️⃣ Start Ollama

```bash
ollama serve
```

Pull required models:

```bash
ollama pull mistral
ollama pull nomic-embed-text
```

---

## 4️⃣ Configure `.env`

```env
LLM_PROVIDER=ollama

OLLAMA_MODEL=mistral
OLLAMA_EMBED_MODEL=nomic-embed-text

USE_COLBERT=true
USE_FAST_LLM=false
```

---

## 5️⃣ Launch Streamlit App

```bash
streamlit run ui/streamlit_app.py
```

---

# 🧪 Running Evaluation

```bash
python evaluate.py
```

---

# 🔮 Future Improvements

## Retrieval

* GraphRAG integration
* dependency graph reasoning
* AST-aware retrieval
* cross-repository retrieval

---

## LLM

* streaming responses
* tool-using agents
* autonomous debugging workflows
* structured reasoning pipelines

---

## Product Features

* Supabase integration
* authentication
* persistent long-term memory
* multi-user support

---

# 🎯 What This Project Demonstrates

This project demonstrates practical understanding of:

* Retrieval-Augmented Generation (RAG)
* hybrid retrieval systems
* reranking pipelines
* evaluation engineering
* conversational memory
* LLM orchestration
* routing systems
* latency optimization
* AI infrastructure design
* production-style AI workflows

---

# 🙌 Final Note

Codebase Copilot was built to deeply explore:

* retrieval quality
* architectural reasoning
* evaluation methodology
* scalable AI system design

with a strong focus on:

* modularity
* explainability
* optimization
* extensibility
* real-world AI engineering workflows.
