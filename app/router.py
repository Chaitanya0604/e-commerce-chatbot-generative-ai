# =============================================================================
# router.py
# -----------------------------------------------------------------------------
# PURPOSE OF THIS FILE:
# When a user types a question into the chatbot, we need to know which part
# of the system should handle it:
#   - Is it an FAQ-style question?        -> handled by faq.py (ChromaDB search)
#   - Is it a product/pricing question?   -> handled by a SQL-generation file
#
# This file builds a "router" that looks at a new question, compares it (by
# MEANING, not exact words) against a few example questions we provide for
# each category, and tells us which category it belongs to: 'faq' or 'sql'.
#
# It does NOT answer the question itself. It just decides where the question
# should go next, like a traffic signal directing cars down the right road.
# =============================================================================


# -----------------------------------------------------------------------------
# IMPORTS — the tools we bring in from the semantic_router library
# -----------------------------------------------------------------------------

# Route   -> a class used to define one category (e.g. "faq") along with a
#            list of example sentences (utterances) that represent it.
# RouteLayer -> a class that takes a collection of Route objects and turns
#            them into a working classifier we can call with a new question.
from semantic_router import Route
from semantic_router.routers import SemanticRouter  

# HuggingFaceEncoder -> the component that converts text into an embedding
# (a list of numbers that captures the MEANING of the sentence). We use the
# free, open-source Hugging Face encoder instead of a paid API (like OpenAI
# or Cohere encoders, which semantic_router also supports) so this project
# runs without needing a paid account.
from semantic_router.encoders import HuggingFaceEncoder


# -----------------------------------------------------------------------------
# STEP 1: Set up the encoder (the "translator" from text to numbers)
# -----------------------------------------------------------------------------
# We tell it exactly which pre-trained model to use:
# "sentence-transformers/all-MiniLM-L6-v2"
#
# This is the SAME model used in faq.py for ChromaDB's embedding function.
# It is small (~80 MB), fast, free, and runs fine on a normal laptop without
# a GPU. A heavier model (all-mpnet-base-v2, ~420 MB) could give slightly
# better accuracy, but may be too slow/heavy depending on your hardware.
encoder = HuggingFaceEncoder(
    name="sentence-transformers/all-MiniLM-L6-v2"
)


# -----------------------------------------------------------------------------
# STEP 2: Define the FAQ route
# -----------------------------------------------------------------------------
# name='faq'      -> this exact string is what gets returned later when a
#                    new question matches this category.
# utterances=[...] -> example FAQ-style questions, copied from our FAQ sheet.
#                    These are NOT keyword rules — they are reference examples
#                    that the encoder converts into embeddings, so that any
#                    new question can be compared against them by meaning.
faq = Route(
    name='faq',
    utterances=[
        "What is the return policy of the products?",
        "Do I get discount with the HDFC credit card?",
        "How can I track my order?",
        "What payment methods are accepted?",
        "How long does it take to process a refund?",
    ],
    score_threshold=0.3   
)


# -----------------------------------------------------------------------------
# STEP 3: Define the SQL route (product / pricing questions)
# -----------------------------------------------------------------------------
# name='sql'  -> called "sql" (not "product") because a match here means the
#                question will eventually be turned into a SQL query that
#                runs against the SQLite product database.
# utterances=[...] -> realistic shopper questions covering discounts, price
#                ranges, sizes, brands, and sales — collected from the
#                business team so they reflect real customer phrasing.
sql = Route(
    name='sql',
    utterances=[
        "I want to buy nike shoes that have 50% discount.",
        "Are there any shoes under Rs. 3000?",
        "Do you have formal shoes in size 9?",
        "Are there any Puma shoes on sale?",
        "What is the price of puma running shoes?",
    ],
    score_threshold=0.3   
)

smalltalk = Route(
    name='small-talk',
    utterances=[
        "hi",
        "hello",
        "hey there",
        "how are you?",
        "what's your name?",
        "what can you do?",
        "good morning",
        "thanks, bye",
        "how is the weather today?",
        "what is your purpose?",
    ],
    score_threshold=0.3
)


# -----------------------------------------------------------------------------
# STEP 4: Build the router layer
# -----------------------------------------------------------------------------
# routes=[faq, sql] -> the list of categories the router can choose between.
#                      More routes (e.g. a "greeting" route) can be added
#                      later simply by defining them and adding them here.
# encoder=encoder    -> tells RouteLayer which model to use to convert both
#                      the stored utterances and any new question into
#                      embeddings, so they can be compared on equal footing.
#
# As soon as this line runs, every utterance from every route is encoded
# into embeddings and stored in memory. This is why classifying a NEW
# question later is fast — only that one new sentence needs to be encoded.
router = SemanticRouter(routes=[faq, sql, smalltalk], encoder=encoder, auto_sync="local")


# -----------------------------------------------------------------------------
# STEP 5: Test the router (only runs when this file is executed directly)
# -----------------------------------------------------------------------------
# if __name__ == "__main__":
#     Every Python file has a hidden variable called __name__.
#     - If you run this file directly (e.g. `python router.py`), Python sets
#       __name__ to "__main__", so the code inside this block DOES run.
#     - If another file instead does `from router import router`, __name__
#       is set to "router", so this block is SKIPPED.
#     This lets router.py work both as a standalone test script AND as a
#     safe, reusable module that the future chatbot UI can import without
#     accidentally re-running these test prints every time.
if __name__ == "__main__":

    # router("...") -> calling the RouteLayer object like a function.
    # Internally this encodes the new question and compares it against every
    # route's stored utterances to find the closest match.
    #
    # .name -> reads the matched route's name back out as a plain string,
    # either 'faq' or 'sql' (matching the names we set in Steps 2 and 3).
    #
    # Expected result: "faq" — this question is semantically close to our
    # FAQ utterances about returns, refunds, and policies.
    print(router("What is your policy on defective product?").name)

    # Expected result: "sql" — this question is semantically close to our
    # SQL/product utterances about brands, prices, and product browsing.
    #
    # Note: real-world questions won't always be this clean. With only 5
    # example utterances per route and a lightweight encoder, you may
    # occasionally see incorrect matches, or even None if a question doesn't
    # clearly resemble either route. If that happens, the usual fix is to
    # add more representative utterances to the affected route.
    print(router("Pink Puma shoes in price range 5000 to 1000").name)