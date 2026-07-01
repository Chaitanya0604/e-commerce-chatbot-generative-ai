# =============================================================================
# faq.py - FAQ Handler for E-Commerce Chatbot
# =============================================================================
# PURPOSE:
#   This file handles everything related to Frequently Asked Questions (FAQs).
#   It:
#     1. Reads FAQ data from a CSV file
#     2. Stores it in ChromaDB (a vector database) for smart searching
#     3. When a user asks a question, finds the most relevant FAQ answers
#     4. Passes those answers to an LLM (Groq/LLaMA) to generate a clean response
# =============================================================================

import os  # Built-in Python module to read environment variables (like API keys)

import chromadb  # ChromaDB: a vector database used to store and search text by meaning
from chromadb.utils import embedding_functions  # Helper to convert text into numerical vectors
from groq import Groq  # Groq: a fast AI API provider that runs LLaMA models
import pandas  # Pandas: used to read CSV files into a table (DataFrame)
from dotenv import load_dotenv  # Loads secret keys from a .env file into environment variables

# -----------------------------------------------------------------------------
# LOAD ENVIRONMENT VARIABLES
# -----------------------------------------------------------------------------
# .env file contains secret API keys like GROQ_API_KEY and GROQ_MODEL
# load_dotenv() reads that file and makes those values available via os.environ
# This keeps secrets OUT of your code (good practice)
load_dotenv()


# -----------------------------------------------------------------------------
# EMBEDDING FUNCTION SETUP
# -----------------------------------------------------------------------------
# What is an "embedding"?
#   Text can't be compared mathematically. Embeddings convert text into a list
#   of numbers (a "vector") that captures the meaning of the text.
#   Example: "How do I return a product?" and "What's the refund policy?"
#   look different as words but have SIMILAR embeddings because they mean the same thing.
#
# We use a pre-trained model called 'all-MiniLM-L6-v2' from sentence-transformers.
# It's a small, fast model that creates good quality embeddings for similarity matching.
ef = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name='sentence-transformers/all-MiniLM-L6-v2'
        )

# -----------------------------------------------------------------------------
# CLIENT SETUP
# -----------------------------------------------------------------------------
# ChromaDB client: Think of this as your connection to the vector database.
# chromadb.Client() creates an IN-MEMORY database (data is lost when program stops).
# For permanent storage, you'd use chromadb.PersistentClient(path="some/folder")
chroma_client = chromadb.Client()

# Groq client: Your connection to the Groq AI API.
# It automatically reads GROQ_API_KEY from environment variables (set by load_dotenv)
groq_client = Groq()

# Name for our ChromaDB collection (like a table name in a regular database)
collection_name_faq = 'faqs'


# =============================================================================
# FUNCTION 1: ingest_faq_data
# =============================================================================
def ingest_faq_data(path):
    """
    Reads FAQ data from a CSV file and stores it in ChromaDB.

    Why store in ChromaDB instead of just reading the CSV every time?
    - ChromaDB stores embeddings (numerical vectors) of all questions
    - This allows SEMANTIC SEARCH: finding questions by MEANING, not just keywords
    - Example: User asks "can I get my money back?" → finds "What is the refund policy?"
      even though the words are completely different

    Args:
        path: File path to the CSV file containing FAQ question-answer pairs
    """

    # CHECK IF COLLECTION ALREADY EXISTS
    # We don't want to re-insert all the data every time the program runs.
    # chroma_client.list_collections() returns all existing collections.
    # We loop through them and collect their names into a list using list comprehension.
    # If our collection name is NOT in that list, we create it.
    if collection_name_faq not in [c.name for c in chroma_client.list_collections()]:

        print("Ingesting FAQ data into Chromadb...")

        # CREATE A NEW COLLECTION
        # A "collection" in ChromaDB is like a table in a database.
        # We give it:
        #   - name: a unique identifier for this collection
        #   - embedding_function: tells ChromaDB HOW to convert text to vectors
        collection = chroma_client.create_collection(
            name=collection_name_faq,
            embedding_function=ef  # Uses the MiniLM model we defined above
        )

        # READ CSV FILE INTO A PANDAS DATAFRAME
        # pandas.read_csv() reads the CSV and creates a table-like object (DataFrame)
        # The CSV has two columns: 'question' and 'answer'
        df = pandas.read_csv(path)

        # EXTRACT QUESTIONS AS A LIST
        # df['question'] selects the 'question' column
        # .to_list() converts it from a Pandas Series to a plain Python list
        # These become our "documents" — what ChromaDB will generate embeddings for
        # IMPORTANT: We only embed QUESTIONS (not answers) because when a user
        # asks something, we want to match it against existing QUESTIONS
        docs = df['question'].to_list()

        # STORE ANSWERS IN METADATA
        # Metadata is extra info attached to each document.
        # We store answers here so when a question matches, we can retrieve its answer.
        # Format must be a list of dictionaries: [{'answer': '...'}, {'answer': '...'}, ...]
        # List comprehension creates this structure for every answer in the CSV
        metadata = [{'answer': ans} for ans in df['answer'].to_list()]

        # CREATE UNIQUE IDs FOR EACH DOCUMENT
        # ChromaDB requires every document to have a unique ID (like a primary key)
        # We generate: ['id_0', 'id_1', 'id_2', ...] using list comprehension
        ids = [f"id_{i}" for i in range(len(docs))]

        # ADD EVERYTHING TO CHROMADB
        # This is where ChromaDB:
        #   1. Takes each question from 'docs'
        #   2. Runs it through the embedding function (MiniLM model)
        #   3. Stores the question text + its vector + metadata + id together
        collection.add(
            documents=docs,      # The FAQ questions (will be embedded)
            metadatas=metadata,  # The corresponding answers (stored as-is)
            ids=ids              # Unique identifier for each entry
        )
        print(f"FAQ Data successfully ingested into Chroma collection: {collection_name_faq}")

    else:
        # Collection already exists — skip ingestion to avoid duplicates
        print(f"Collection: {collection_name_faq} already exist")


# =============================================================================
# FUNCTION 2: get_relevant_qa
# =============================================================================
def get_relevant_qa(query):
    """
    Searches ChromaDB for the most relevant FAQ questions matching the user's query.

    HOW SEMANTIC SEARCH WORKS HERE:
    1. The user's query is converted to an embedding (vector) using the same MiniLM model
    2. ChromaDB compares this vector against all stored question vectors
    3. It returns the closest matches (by mathematical distance between vectors)
    4. "Closest" = most similar in MEANING, not necessarily same words

    Args:
        query: The user's question as a string

    Returns:
        ChromaDB result object containing matched questions, their answers (in metadata),
        and similarity distances
    """

    # GET THE EXISTING COLLECTION
    # We already ingested data, so we just fetch the existing collection
    # We must provide the same embedding_function so ChromaDB knows how to
    # convert the query to a vector for comparison
    collection = chroma_client.get_collection(
        name=collection_name_faq,
        embedding_function=ef  # Must be same model used during ingestion!
    )

    # PERFORM SEMANTIC SEARCH
    # query_texts: list of queries (we only have one here, but it supports multiple)
    # n_results: how many top matches to return (we want top 2)
    # ChromaDB will embed the query and find the 2 most similar questions
    result = collection.query(
        query_texts=[query],
        n_results=2  # Return top 2 most relevant FAQ matches
    )

    return result


# =============================================================================
# FUNCTION 3: generate_answer
# =============================================================================
def generate_answer(query, context):
    """
    Uses the Groq LLM (LLaMA model) to generate a clean, human-readable answer.

    WHY DO WE NEED THIS?
    The raw answers from ChromaDB might be choppy or disconnected.
    Example context: "Contact our support team." + "You can return within 30 days."
    The LLM combines these into: "If you have a defective product, please contact our
    support team. You may also return it within 30 days for a full refund."

    Args:
        query: The original user question
        context: The raw FAQ answers retrieved from ChromaDB (combined into one string)

    Returns:
        A polished, human-readable answer string from the LLM
    """

    # BUILD THE PROMPT
    # A "prompt" is the instruction we send to the LLM.
    # Key instructions we give the LLM:
    #   1. Answer ONLY from the provided context (prevents hallucination)
    #   2. If answer not in context, say "I don't know" (prevents making things up)
    # We use Python f-string to insert the actual context and query values
    prompt = f'''Given the following context and question, generate answer based on this context only.
    If the answer is not found in the context, kindly state "I don't know". Don't try to make up an answer.
    
    CONTEXT: {context}
    
    QUESTION: {query}
    '''

    # CALL THE GROQ API (LLaMA MODEL)
    # groq_client.chat.completions.create() sends our prompt to the LLM
    # Parameters:
    #   - model: which LLM to use (read from .env, e.g. "llama-3.3-70b-versatile")
    #   - messages: a list of message objects with 'role' and 'content'
    #     - role='user' means this is the human's message (vs 'assistant' or 'system')
    #     - content is the actual text of our prompt
    completion = groq_client.chat.completions.create(
        model=os.environ['GROQ_MODEL'],  # LLaMA model name from .env file
        messages=[
            {
                'role': 'user',      # We are sending this as a user message
                'content': prompt    # The full prompt with context and question
            }
        ]
    )

    # EXTRACT THE RESPONSE TEXT
    # The API returns a complex object. We navigate:
    #   completion.choices     → list of possible responses (usually just 1)
    #   [0]                    → take the first (and usually only) choice
    #   .message               → the message object
    #   .content               → the actual text string of the response
    return completion.choices[0].message.content


# =============================================================================
# FUNCTION 4: faq_chain (Main Pipeline)
# =============================================================================
def faq_chain(query):
    """
    The main pipeline that connects all the pieces together.
    This is called the "chain" because it chains multiple steps:

    User Query
        ↓
    [Step 1] get_relevant_qa() → Search ChromaDB for matching FAQs
        ↓
    [Step 2] Extract answers from metadata → Build context string
        ↓
    [Step 3] generate_answer() → LLM generates clean response
        ↓
    Final Answer

    Args:
        query: The user's question string

    Returns:
        A clean, human-readable answer string
    """

    # STEP 1: SEARCH CHROMADB FOR RELEVANT Q&A
    result = get_relevant_qa(query)

    # STEP 2: EXTRACT AND COMBINE ANSWERS INTO A CONTEXT STRING
    # result['metadatas'] is a 2D list: [[{answer: '...'}, {answer: '...'}]]
    # result['metadatas'][0] gives us the first (and only) query's results
    # We loop through each result dictionary and get the 'answer' value
    # "".join(...) combines all answers into one long string
    context = "".join([r.get('answer') for r in result['metadatas'][0]])
    print("Context:", context)  # Debug print to see what context was retrieved

    # STEP 3: GENERATE CLEAN ANSWER USING LLM
    answer = generate_answer(query, context)

    return answer


# =============================================================================
# MAIN EXECUTION (runs only when this file is executed directly)
# =============================================================================
if __name__ == '__main__':
    # Define path to the FAQ CSV file
    # (Note: 'faqs_path' should be defined before this line in production,
    #  e.g., faqs_path = Path(__file__).parent / 'resources' / 'faq_data.csv')
    ingest_faq_data(faqs_path)

    # Test queries to verify the system works
    query = "what's your policy on defective products?"
    query = "Do you take cash as a payment option?"  # This overwrites the previous query

    # Run the full FAQ pipeline and print the result
    answer = faq_chain(query)
    print("Answer:", answer)