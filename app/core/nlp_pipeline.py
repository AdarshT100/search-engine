# Reusable text preprocessing pipeline: tokenisation, stopword removal, stemming.
import re
import nltk
from nltk.tokenize import word_tokenize
from nltk.corpus import stopwords

# Download required NLTK datasets (safe to call multiple times — skips if already present)
nltk.download("punkt", quiet=True)
nltk.download("punkt_tab", quiet=True)
nltk.download("stopwords", quiet=True)


class NLPPipeline:
    """
    Shared text preprocessing pipeline used for BOTH document ingestion
    and search query preprocessing. Using the same pipeline ensures that
    tokens in the index always match tokens produced from a query.

    Pipeline steps:
        1. Lowercase
        2. Remove punctuation / special characters (keep alphanumeric + spaces)
        3. Tokenise  (NLTK word_tokenize)
        4. Remove English stopwords  (NLTK stopwords list)

    Stemming is intentionally omitted — planned for v1.1.
    """

    def __init__(self):
        self._stop_words = set(stopwords.words("english"))

    def process(self, text: str) -> list[str]:
        """
        Process raw text and return a list of clean tokens.

        Args:
            text: Raw input string (document body or search query).

        Returns:
            List of preprocessed tokens ready for indexing or lookup.
        """
        if not text or not text.strip():
            return []

        # Step 1 — Lowercase
        text = text.lower()

        # Step 2 — Remove punctuation and special characters
        text = re.sub(r"[^a-z0-9\s]", "", text)

        # Step 3 — Tokenise
        tokens = word_tokenize(text)

        # Step 4 — Remove stopwords and empty strings
        tokens = [t for t in tokens if t and t not in self._stop_words]

        return tokens
