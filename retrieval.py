import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


# Load Amazon historical support conversations
df = pd.read_csv("amazon_sample_200.csv")

# Replace missing text with empty strings
df["customer_text"] = df["customer_text"].fillna("")


# Create TF-IDF representation of customer messages
vectorizer = TfidfVectorizer(
    lowercase=True,
    stop_words="english"
)

customer_vectors = vectorizer.fit_transform(df["customer_text"])


def retrieve_similar_cases(query, top_k=3):
    """
    Find the most similar historical Amazon customer messages.

    Returns the top_k conversations with:
    - customer message
    - Amazon's historical response
    - similarity score
    """

    query_vector = vectorizer.transform([query])

    similarities = cosine_similarity(
        query_vector,
        customer_vectors
    )[0]

    top_indices = similarities.argsort()[::-1][:top_k]

    results = []

    for index in top_indices:
        results.append({
            "customer_text": df.iloc[index]["customer_text"],
            "amazon_text": df.iloc[index]["amazon_text"],
            "similarity": float(similarities[index])
        })

    return results


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