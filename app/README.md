# 🛒 E-Commerce Chatbot using Generative AI

An intelligent shopping assistant that allows users to interact with an e-commerce platform using natural language.

Instead of navigating through filters and menus, users can simply ask questions like:

> 💬 *"Show me Nike shoes under ₹3000 with a rating above 4."*
> 💬 *"What is your return policy?"*
> 💬 *"Hi!"*

The chatbot automatically understands the user's intent and routes the request to the appropriate backend.

---

## ✨ Features

* 🔀 Semantic intent classification
* 📚 RAG-powered FAQ retrieval using ChromaDB
* 🛍️ LLM-powered Text-to-SQL product search
* 🗃️ SQLite product database
* 💬 Dedicated Small Talk pipeline
* 🎈 Interactive Streamlit chatbot interface
* 🧠 Conversation history using Streamlit Session State
* ⚡ Groq-hosted LLaMA for fast inference

---

## 📸 Demo

### Version 1 — Product Search

The chatbot understands natural language product queries and retrieves matching products from the SQLite database.

![Product Search Screenshot](app/resources/product-ss.png)

---

### Version 2 — Redesigned Chat Interface

An updated UI featuring a floating chatbot widget with dedicated FAQ, Product Search, and Small Talk routing for a more realistic shopping experience.

![Version 2 Screenshot](app/resources/product-ss-aesthetic.png)

---

## 🏗️ Architecture

![architecture diagram of the e-commerce chatbot](app/resources/architecture-diagram.png)

---

## 🧠 How It Works

Every user query first passes through a **Semantic Router**, which classifies its intent and routes it to the appropriate pipeline.

### 📚 FAQ Pipeline

* Loads FAQ data from CSV
* Creates embeddings using Sentence Transformers
* Stores embeddings in ChromaDB
* Retrieves the most relevant FAQs
* Uses LLaMA to generate a grounded response

### 🛍️ Product Search Pipeline

* Converts natural language into SQL using LLaMA
* Validates the generated SQL
* Executes the query on SQLite
* Retrieves matching products
* Converts database results into a conversational response

### 💬 Small Talk Pipeline

Simple greetings and casual conversations are handled by a dedicated `smalltalk.py` module without querying either ChromaDB or SQLite.

---

## 🚀 Example Queries

### FAQ

* What is your return policy?
* Is Cash on Delivery available?
* Can I exchange a damaged product?

### Product Search

* Show Nike shoes under ₹3000
* Top 3 women's shoes with rating above 4.5
* Puma shoes between ₹1000 and ₹2500

### Small Talk

* Hi
* Good Morning
* Thank you

---

## 🛠️ Tech Stack

| Technology            | Purpose               |
| --------------------- | --------------------- |
| Python                | Backend               |
| Streamlit             | Web Interface         |
| LLaMA 3.3 (Groq)      | LLM Inference         |
| Semantic Router       | Intent Classification |
| ChromaDB              | Vector Database       |
| Sentence Transformers | Text Embeddings       |
| SQLite                | Product Database      |
| Pandas                | Data Processing       |

---

## 📂 Project Structure

```text
.
├── app/
│   ├── main.py
│   ├── router.py
│   ├── faq.py
│   ├── sql.py
│   ├── smalltalk.py
│   ├── resources/
│   ├── requirements.txt
│   └── .env
│
├── web-scraping/
│   └── Product scraping scripts
│
└── README.md
```

---

## ⚙️ Setup & Installation

### 1. Clone the repository

```bash
git clone <repository-url>
cd <repository-name>
```

### 2. Install dependencies

```bash
pip install -r app/requirements.txt
```

### 3. Create a `.env` file inside the `app` folder

```text
GROQ_MODEL=llama-3.3-70b-versatile
GROQ_API_KEY=your_groq_api_key
```

### 4. Launch the application

```bash
streamlit run app/main.py
```

---

## 🏗️ End-to-End Workflow

```text
                User Query
                     │
                     ▼
             Semantic Router
          ┌──────────┼──────────┐
          │          │          │
          ▼          ▼          ▼
       FAQ Route  SQL Route  Small Talk
          │          │          │
          ▼          ▼          ▼
     ChromaDB     LLaMA      Response
       + LLM      → SQL
                    │
                    ▼
                 SQLite
                    │
                    ▼
             LLaMA Response
```

---

## 🎯 Future Improvements

* 🧠 Multi-turn conversation memory
* ❤️ Personalized product recommendations
* 📦 Order tracking
* 🛒 Shopping cart integration
* 🌍 Multi-language support
* 🔍 Hybrid keyword + semantic search

---

## 🤝 Contributing

Contributions, suggestions, and feedback are always welcome.

If you have ideas for improving the project, feel free to open an issue or submit a pull request.

---

⭐ If you found this project interesting, consider giving it a star!
