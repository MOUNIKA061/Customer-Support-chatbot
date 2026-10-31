import re
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


def clean_tweet_text(text):
    """
    Remove Twitter handles (@username), URLs (https://...), and agent initials
    (^GS, ^WT) so TF-IDF term weights reflect support topics instead of noise.
    """
    t = re.sub(r"@\w+", " ", str(text))
    t = re.sub(r"https?://\S+", " ", t)
    t = re.sub(r"\^[A-Za-z]+", " ", t)
    return re.sub(r"\s+", " ", t).strip()


# Load Amazon historical support conversations
df = pd.read_csv("amazon_sample_200.csv")

# Replace missing text with empty strings
df["customer_text"] = df["customer_text"].fillna("")
df["amazon_text"] = df["amazon_text"].fillna("")

# Clean texts and combine customer inquiry + agent guidance
cleaned_customer = df["customer_text"].apply(clean_tweet_text)
cleaned_amazon = df["amazon_text"].apply(clean_tweet_text)
search_corpus = cleaned_customer + " " + cleaned_amazon

# Create TF-IDF representation of customer support conversations
vectorizer = TfidfVectorizer(
    lowercase=True,
    stop_words="english"
)
conversation_vectors = vectorizer.fit_transform(search_corpus)

# Dedicated response vectorizer to measure topical support guidance relevance
response_vectorizer = TfidfVectorizer(
    lowercase=True,
    stop_words="english"
)
response_vectors = response_vectorizer.fit_transform(cleaned_amazon)


def retrieve_similar_cases(query, top_k=3):
    """
    Find the most similar historical Amazon customer messages.

    Returns the top_k conversations with:
    - customer message
    - Amazon's historical response
    - similarity score
    - response_similarity score (measuring support guidance topical match)
    """
    cleaned_query = clean_tweet_text(query)
    query_vector = vectorizer.transform([cleaned_query])
    query_resp_vector = response_vectorizer.transform([cleaned_query])

    similarities = cosine_similarity(
        query_vector,
        conversation_vectors
    )[0]
    resp_similarities = cosine_similarity(
        query_resp_vector,
        response_vectors
    )[0]

    top_indices = similarities.argsort()[::-1][:top_k]

    results = []

    for index in top_indices:
        results.append({
            "customer_text": df.iloc[index]["customer_text"],
            "amazon_text": df.iloc[index]["amazon_text"],
            "similarity": float(similarities[index]),
            "response_similarity": float(resp_similarities[index])
        })

    return results


def check_evidence_quality(query, cases, threshold=0.18, min_response_sim=0.05):
    """
    Explicit evidence quality check. A similarity score alone does not
    prove that a case answers the question (e.g. an accidental noun match in
    customer text does not mean the support response offers guidance).

    Distribution across verified test queries:
    - Order status: sim=0.358, resp_sim=0.197
    - Tracking: sim=0.305, resp_sim=0.417
    - Delayed order: sim=0.336, resp_sim=0.276
    - Damaged item: sim=0.198, resp_sim=0.237
    - Out-of-domain flight/pet queries: resp_sim=0.000

    Returns:
        (is_sufficient: bool, max_similarity: float, reason: str)
    """
    if not cases:
        return False, 0.0, "No historical cases were retrieved."

    max_sim = max((c.get("similarity", 0.0) for c in cases), default=0.0)
    max_resp_sim = max((c.get("response_similarity", 0.0) for c in cases), default=0.0)

    if max_sim < threshold:
        return (
            False,
            max_sim,
            f"Top similarity {max_sim:.3f} is below evidence threshold {threshold:.2f}."
        )

    if max_resp_sim < min_response_sim:
        return (
            False,
            max_sim,
            f"Retrieved cases do not contain relevant support guidance (response similarity {max_resp_sim:.3f} < {min_response_sim:.2f})."
        )

    return (
        True,
        max_sim,
        f"Sufficient evidence relevance ({max_sim:.3f} >= {threshold:.2f}, response relevance {max_resp_sim:.3f})."
    )


# Simple test
if __name__ == "__main__":

    query = "My package is late and has not arrived yet."

    results = retrieve_similar_cases(query)

    print("=" * 70)
    print("QUERY")
    print("=" * 70)
    print(query)

    print("\n" + "=" * 70)
    print("SIMILAR HISTORICAL CASES")
    print("=" * 70)

    for i, result in enumerate(results, start=1):

        print(f"\n--- Case {i} ---")

        print("Customer:")
        print(result["customer_text"])

        print("\nAmazon response:")
        print(result["amazon_text"])

        print(f"\nSimilarity: {result['similarity']:.3f}")