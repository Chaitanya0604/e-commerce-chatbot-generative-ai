# sql.py
# -----------------------------------------------------------------------------
# This file implements the "SQL route" — the second of the two intents the
# chatbot can handle (the first being FAQ, handled in faq.py).
#
# Big picture (Text-to-SQL pipeline), in four stages:
#   1. User asks a natural-language question about products/pricing.
#   2. LLM call #1: translate that question into a real SQL query, using a
#      prompt that describes the database's schema (table + columns).
#   3. Run that SQL query against the actual db.sqlite database, getting
#      back raw matching rows.
#   4. LLM call #2: turn those raw rows + the original question into a
#      clean, human-readable answer (product name, price, discount, rating,
#      link).
#
# Why two LLM calls instead of one?
#   - The LLM has no access to your live database; it must be given the data
#     explicitly.
#   - Databases are precise; LLMs are not. Filtering by exact price/brand is
#     a job for SQL, not for free-form text generation.
#   - So: LLM #1 = English -> SQL (translator), real DB lookup in the
#     middle, LLM #2 = data -> English (translator back).
# -----------------------------------------------------------------------------

from groq import Groq            # Groq client: lets us send chat messages to the LLaMA model hosted on Groq's fast inference platform.
import os                         # Read environment variables (API keys, model name) without hard-coding secrets in the file.
import re                         # Regular expressions — used to pull the SQL query out from between <SQL></SQL> tags in the LLM's response.
import sqlite3                    # Python's built-in module for opening and querying SQLite database files.
import pandas as pd               # Used here for its convenient read_sql_query(), which returns query results as a structured DataFrame.
from pathlib import Path          # Cross-platform way to build the path to db.sqlite, regardless of OS.
from dotenv import load_dotenv    # Loads secret values (Groq API key, model name) from a hidden .env file into environment variables.
from pandas import DataFrame      # Imported by name as well (mainly useful for type hints elsewhere); not strictly required alongside `import pandas as pd`.

load_dotenv()  # Reads .env and makes its contents available via os.environ / os.getenv().

GROQ_MODEL = os.getenv('GROQ_MODEL')  # e.g. "llama-3.3-70b-versatile" — read once and reused everywhere below.

db_path = db_path = Path(__file__).parent / "resources" / "db.sqlite"  # Full path to the SQLite file sitting next to this script (the same one explored via sqlite3 / DB Browser).

client_sql = Groq()  # Connection object used to actually send prompts to the LLM. Named client_sql (not just `client`) to stay distinct if more clients are ever added.

# -----------------------------------------------------------------------------
# SYSTEM PROMPT #1 — teaches the LLM the database schema so it can write
# accurate SQL. This is arguably the most important text in the whole file:
# the quality of generated SQL depends almost entirely on how well this is
# written.
# -----------------------------------------------------------------------------
sql_prompt = """You are an expert in understanding the database schema and generating SQL queries for a natural language question asked
pertaining to the data you have. The schema is provided in the schema tags. 
<schema> 
table: product 

fields: 
product_link - string (hyperlink to product)	
title - string (name of the product)	
brand - string (brand of the product)	
price - integer (price of the product in Indian Rupees)	
discount - float (discount on the product. 10 percent discount is represented as 0.1, 20 percent as 0.2, and such.)	
avg_rating - float (average rating of the product. Range 0-5, 5 is the highest.)	
total_ratings - integer (total number of ratings for the product)

</schema>
Make sure whenever you try to search for the brand name, the name can be in any case. 
So, make sure to use %LIKE% to find the brand in condition. Never use "ILIKE". 
Create a single SQL query for the question provided. 
The query should have all the fields in SELECT clause (i.e. SELECT *)

Just the SQL query is needed, nothing more. Always provide the SQL in between the <SQL></SQL> tags."""
# Notes on specific instructions above:
# - The <schema> block is what lets the LLM know the table is called `product`
#   and exactly which columns exist, their types, and what they mean.
# - "%LIKE%, never ILIKE" exists because real scraped data has mixed-case
#   brand names ("Nike"/"nike"/"NIKE"), and ILIKE is valid in Postgres but
#   NOT valid SQLite syntax — without this instruction the LLM previously
#   generated invalid queries.
# - "SELECT *" is forced so the second LLM call later has full context
#   (price, discount, rating, link) rather than just whatever columns it
#   guessed were relevant.
# - The <SQL></SQL> tag requirement gives us a predictable, regex-extractable
#   output format, since the LLM's raw response is just plain text.


# -----------------------------------------------------------------------------
# SYSTEM PROMPT #2 — teaches the LLM how to turn raw query results into a
# clean, natural-sounding answer (the reverse direction: data -> English).
# -----------------------------------------------------------------------------
comprehension_prompt = """You are an expert in understanding the context of the question and replying based on the data pertaining to the question provided. 
You will be provided with Question: and Data:. The data will be in the form of an array or a dataframe or dict. Reply based on only the data provided as Data for answering the question asked as Question.
Do not write anything like 'Based on the data' or any other technical words. Just a plain simple natural language response.
The Data would always be in context to the question asked. For example is the question is “What is the average rating?” and data is “4.3”, then answer should be “The average rating for the product is 4.3”.
So make sure the response is curated with the question and data. Make sure to note the column names to have some context, if needed, for your response.
There can also be cases where you are given an entire dataframe in the Data: field. Always remember that the data field contains the answer of the question asked. 
All you need to do is to always reply in the following format when asked about a product: 
Produt title, price in indian rupees, discount, and rating, and then product link. Take care that all the products are listed in list format, one line after the other. Not as a paragraph.
For example:
1. Campus Women Running Shoes: Rs. 1104 (35 percent off), Rating: 4.4 <link>
2. Campus Women Running Shoes: Rs. 1104 (35 percent off), Rating: 4.4 <link>
3. Campus Women Running Shoes: Rs. 1104 (35 percent off), Rating: 4.4 <link>

"""
# Notes:
# - "Reply based only on the data provided" is an anti-hallucination guardrail
#   (same idea as in faq.py): never let the LLM invent details not present
#   in the actual query results.
# - The worked example ("average rating" -> "4.3") is a one-shot example —
#   showing the desired input/output pattern is usually more effective than
#   describing the rule abstractly.
# - The numbered-list example locks in a consistent output format for
#   multi-product answers.


def generate_sql_query(question):
    """
    LLM call #1: English question -> SQL query (wrapped in <SQL></SQL> tags).
    """
    chat_completion = client_sql.chat.completions.create(
        messages=[
            {
                "role": "system",
                "content": sql_prompt,     # The schema-aware rules defined above.
            },
            {
                "role": "user",
                "content": question,       # The user's raw natural-language question.
            }
        ],
        model=os.environ['GROQ_MODEL'],
        temperature=0.2,    # Low temperature = precise, repeatable output. Creative SQL is usually broken SQL.
        max_tokens=1024     # Generous ceiling for a single SQL query; can be raised if queries get more complex.
    )

    return chat_completion.choices[0].message.content  # .choices[0] = the (only, by default) candidate response; .message.content = its text.



def run_query(query):
    """
    Executes a SQL query against the real db.sqlite database — but only
    after a critical safety check.
    """
    if query.strip().upper().startswith('SELECT'):
        # Safety check: only ever allow read-only SELECT queries to run.
        # .strip() removes stray whitespace, .upper() makes the check
        # case-insensitive (so "select", "Select", "SELECT" all pass).
        # This guarantees an LLM-generated query can never DELETE, UPDATE,
        # or DROP real data — it can only ever read it.
        with sqlite3.connect(db_path) as conn:   # `with` ensures the connection is automatically closed afterward, even on error.
            df = pd.read_sql_query(query, conn)  # Runs the query and returns results as a structured Pandas DataFrame (not raw tuples).
            return df
    # If the check fails (query doesn't start with SELECT), there's no
    # explicit return here -> Python implicitly returns None. The caller
    # (sql_chain) checks for this and reports a friendly error instead of
    # crashing or running something unsafe.


def data_comprehension(question, context):
    """
    LLM call #2: raw data (+ original question) -> natural-language answer.
    """
    chat_completion = client_sql.chat.completions.create(
        messages=[
            {
                "role": "system",
                "content": comprehension_prompt,   # The "explain the data naturally" rules defined above.
            },
            {
                "role": "user",
                "content": f"QUESTION: {question}. DATA: {context}",  # Both the question and the query results, as plain text, in one message.
            }
        ],
        model=os.environ['GROQ_MODEL'],
        temperature=0.2,        # Kept low so the LLM sticks closely and faithfully to the actual data, rather than getting "creative".
        # max_tokens=1024       # Intentionally left commented out: a natural-language product list can run longer than a single SQL query would,
                                 # so we don't want to risk cutting off the response mid-sentence. Uncomment + raise if Groq ever errors on length.
    )

    return chat_completion.choices[0].message.content



def sql_chain(question):
    """
    The single entry point main.py calls for any question routed to 'sql'.
    Wires the whole pipeline together end to end, with error handling at
    every stage so a bad LLM response never crashes the app:

      1. Generate SQL from the question (LLM call #1).
      2. Extract the SQL out of the <SQL></SQL> tags via regex.
      3. Run it safely against the database (SELECT-only).
      4. Convert the resulting rows into a list of dicts.
      5. Generate a natural-language answer from those rows (LLM call #2).
    """
    sql_query = generate_sql_query(question)   # Step 1: ask the LLM to translate the question into SQL.

    pattern = "<SQL>(.*?)</SQL>"
    # <SQL> and </SQL> are matched literally; (.*?) is a capture group meaning
    # "match any characters, as few as possible, and remember what's matched".
    matches = re.findall(pattern, sql_query, re.DOTALL)
    # re.DOTALL makes `.` also match newline characters — essential because a
    # multi-line SQL query would otherwise get cut off at the first line break.

    if len(matches) == 0:
        # The LLM's response didn't contain the expected tags at all (e.g. it
        # couldn't make sense of a nonsense question). Fail gracefully.
        return "Sorry, LLM is not able to generate a query for your question"

    print(matches[0].strip())   # Debugging aid: print the exact SQL generated, visible in the terminal/logs.

    response = run_query(matches[0].strip())   # Step 3: execute the (SELECT-only) query against db.sqlite.
    if response is None:
        # Either the SELECT-only safety check failed, or some other SQL
        # error occurred. Fail gracefully instead of crashing.
        return "Sorry, there was a problem executing SQL query"

    context = response.to_dict(orient='records')
    # Step 4: convert the DataFrame into a list of dicts, e.g.
    # [{"title": "Nike Air...", "price": 4999, "avg_rating": 4.6, ...}, {...}]
    # — an easy format to drop straight into a text prompt.

    answer = data_comprehension(question, context)   # Step 5: LLM call #2 turns the raw records into a clean, human-readable answer.
    return answer


if __name__ == "__main__":
    # This block only runs when sql.py is executed directly (e.g.
    # `python sql.py`), NOT when main.py imports sql_chain from this module.
    # Alternate test questions are kept here, commented out, so it's quick
    # to swap between an easy case, a complex case, and a deliberately
    # broken case without retyping anything:

    # question = "All shoes with rating higher than 4.5 and total number of reviews greater than 500"
    # sql_query = generate_sql_query(question)
    # print(sql_query)
    question = "Show top 3 shoes in descending order of rating"
    # question = "Show me 3 running shoes for woman"
    # question = "sfsdfsddsfsf"   # Deliberately nonsense input — exercises the "Sorry, LLM is not able to generate a query" fallback.
    answer = sql_chain(question)
    print(answer)