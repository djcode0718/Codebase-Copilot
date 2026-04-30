# 🚀 Codebase Copilot

An AI-powered system that understands any GitHub repository or local codebase and answers natural language questions using a custom-built Retrieval-Augmented Generation (RAG) pipeline.

---

## 🔥 Overview

**Codebase Copilot** allows you to:

* 📂 Load any GitHub repository or local project
* 🧠 Index and understand the code structure
* 💬 Ask natural language questions about the code
* ⚡ Get intelligent, context-aware answers

Unlike typical LLM wrappers, this project is built **from scratch**, implementing core RAG components manually—making it both educational and production-relevant.

---

## 🧠 Key Features

* ✅ Custom RAG pipeline (no dependency on frameworks)
* ✅ Multi-LLM support (Groq, Gemini, OpenAI, Ollama)
* ✅ Lightweight TF-IDF embeddings (no GPU required)
* ✅ FAISS-based vector storage
* ✅ Streamlit-based interactive UI
* ✅ Handles real-world constraints (token limits, memory issues)
* ✅ Modular and extensible architecture

---

## 🏗️ Architecture

```text
User Query
   ↓
Streamlit UI
   ↓
QA Service
   ↓
Retriever (TF-IDF + Cosine Similarity)
   ↓
Vector Store (FAISS + Metadata)
   ↓
LLM (Groq / Gemini / OpenAI / Ollama)
   ↓
Final Answer
```

---

## ⚙️ Project Structure

```text
codebase-copilot/
│
├── app/                       # Main application logic 
│   ├── main.py              # Entry point (connects everything)
│   ├── config.py            # Configs (paths, model names)
│
│   ├── ingestion/           # Step 1: Load code
│   │   ├── repo_loader.py   # Clone/load repo
│   │   └── file_filter.py   # Ignore unnecessary files
│
│   ├── parsing/             # Step 2: Structure code
│   │   ├── code_parser.py   # Break into chunks
│   │   └── chunk_utils.py   # Chunking logic
│
│   ├── indexing/            # Step 3: Create embeddings
│   │   ├── index_builder.py # Build vector index
│   │   └── vector_store.py  # FAISS/Chroma setup
│
│   ├── retrieval/           # Step 4: Search relevant code
│   │   ├── retriever.py     # Query → relevant chunks
│   │   └── ranking.py       # Optional reranking
│
│   ├── llm/                 # Step 5: Reasoning
│   │   ├── llm_client.py    # Connect to LLM (Ollama/Gemini)
│   │   └── prompts.py       # All prompts stored here
│
│   ├── services/            # Step 6: Orchestration
│   │   ├── qa_service.py    # Main Q&A pipeline
│   │   └── repo_service.py  # Handles repo processing
│
│   └── utils/               # Common helpers
│       ├── logger.py
│       └── helpers.py
│
├── data/                    # Local storage
│   ├── repos/               # Cloned repos
│   └── index/               # Vector DB storage
│
├── ui/                      # Frontend
│   └── streamlit_app.py
│
├── requirements.txt
├── README.md
└── .env
```

---

## 🔄 Workflow (Step-by-Step)

### 1. Repository Ingestion

* Accepts GitHub URL or local path
* Clones repo into `data/repos/`
* Filters valid code files

---

### 2. Parsing

* Reads code files
* Converts each file into a single chunk (for stability)
* Avoids memory-heavy chunking logic

---

### 3. Embedding Generation

* Uses **TF-IDF vectorization**
* Converts code into numerical embeddings
* Avoids heavy ML dependencies (no PyTorch)

---

### 4. Vector Storage

* Stores embeddings using **FAISS**
* Stores metadata separately (file name, path, content)
* Saves:

  * `.faiss` index
  * `.json` metadata
  * `.npy` embeddings
  * `.pkl` vectorizer

---

### 5. Query Processing

* User enters query in UI
* Query is converted using the SAME vectorizer
* Cosine similarity used for retrieval

---

### 6. Retrieval

* Top-K relevant chunks are selected
* Context is trimmed to avoid token overflow

---

### 7. LLM Response Generation

* Prompt is constructed using retrieved context
* Sent to selected LLM provider
* Response returned to UI

---

## 🤖 Supported LLM Providers

| Provider | Type  | Notes                  |
| -------- | ----- | ---------------------- |
| Groq     | API   | Fast, free tier        |
| Gemini   | API   | Stable, good reasoning |
| OpenAI   | API   | Requires credits       |
| Ollama   | Local | Fully offline          |

---

## 🔐 Environment Variables (`.env`)

```env
LLM_PROVIDER=groq

GROQ_API_KEY=your_key
GEMINI_API_KEY=your_key
OPENAI_API_KEY=your_key

OLLAMA_MODEL=llama3:8b

EMBEDDING_MODEL=tfidf
```

---

## 🚀 How to Run

### 1. Create Environment

```bash
conda create -n ai-copilot-env python=3.10
conda activate ai-copilot-env
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Run Application

```bash
streamlit run ui/streamlit_app.py
```

---

## ⚠️ Challenges Solved

This project handles several real-world issues:

### 🧠 Memory Constraints

* Removed heavy models (transformers)
* Used TF-IDF instead

### 📦 Token Limits

* Limited context size
* Trimmed retrieved chunks

### 🔄 State Persistence

* Saved vectorizer alongside embeddings
* Ensured consistent query transformations

### ⚡ API Reliability

* Added retry logic
* Multi-provider fallback

---

## 💡 Design Decisions

### Why TF-IDF instead of embeddings?

* Lightweight
* No GPU required
* Faster for small/medium codebases

### Why not LangChain/LlamaIndex?

* Built manually to understand internals
* Easier debugging and control

---

## 📊 Current Limitations

* Basic chunking (file-level)
* No advanced reranking
* No semantic embeddings (yet)

---

## 🔮 Future Improvements

* 🔹 Smart chunking (function-level)
* 🔹 Hybrid embeddings (TF-IDF + semantic)
* 🔹 Streaming responses
* 🔹 Auto LLM fallback system
* 🔹 LangChain / LlamaIndex integration
* 🔹 Code visualization features

---

## 🧠 What This Project Demonstrates

* End-to-end RAG system design
* Vector databases and retrieval logic
* Handling LLM constraints (tokens, memory)
* Multi-LLM orchestration
* Real-world debugging and optimization

---

## 📌 Example Use Cases

* Understand unfamiliar codebases
* Debug large projects quickly
* Explain project architecture
* Find where specific logic exists

---

## 🙌 Final Note

This project goes beyond tutorials by focusing on:

* **system design**
* **debugging real issues**
* **building from scratch**

It’s not just a chatbot—it’s a **code intelligence system**.

---
