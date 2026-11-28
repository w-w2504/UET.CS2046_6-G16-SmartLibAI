"""SPEC 15.2 deterministic TF-IDF and seed genre-union scores; no labels."""

from collections import Counter
import math

from ai_library.bm25_search import tokenize


def normalize(vector):
    norm = math.sqrt(math.fsum(v*v for v in vector.values()))
    if not math.isfinite(norm) or norm <= 1e-8:
        raise ValueError('TF-IDF zero/invalid vector or profile')
    return {term: weight/norm for term, weight in vector.items()}


class Tfidf:
    def __init__(self, texts):
        if not texts:
            raise ValueError('Empty TF-IDF corpus')
        counts = {bid: Counter(tokenize(text)) for bid, text in sorted(texts.items())}
        df = Counter(term for count in counts.values() for term in count)
        self.idf = {term: math.log((1+len(counts))/(1+n))+1 for term, n in df.items()}
        self.vectors = {bid: normalize({t: (1+math.log(n))*self.idf[t] for t,n in count.items()})
                        for bid,count in counts.items()}

    def score(self, seeds):
        if not 1 <= len(seeds) <= 3 or len(set(seeds)) != len(seeds):
            raise ValueError('Invalid TF-IDF seeds')
        profile = {}
        for bid in seeds:
            for term, weight in self.vectors[bid].items():
                profile.setdefault(term, []).append(weight/len(seeds))
        profile = normalize({term: math.fsum(weights) for term, weights in profile.items()})
        return {bid: math.fsum(weight*profile.get(term,0) for term,weight in vector.items())
                for bid,vector in self.vectors.items()}


def genre_scores(books, seeds):
    union = set().union(*(books[bid].genres for bid in seeds))
    return {bid: len(union.intersection(book.genres)) for bid,book in books.items()}
