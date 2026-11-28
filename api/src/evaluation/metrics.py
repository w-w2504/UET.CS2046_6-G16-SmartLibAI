"""Pure work-level pooled metrics. Unjudged is an error, never zero."""

import math


def precision_ndcg_at5(ranking, labels):
    if len(set(ranking)) != len(ranking):
        raise ValueError('Duplicate ranked work')
    if any(type(v) is not int or not 0 <= v <= 2 for v in labels.values()):
        raise ValueError('Relevance must be integer 0..2')
    if any(work not in labels for work in ranking):
        raise ValueError('Unjudged ranked work')
    gains = [labels[work] for work in ranking[:5]]
    def dcg(values):
        return math.fsum((2**v-1)/math.log2(rank+1) for rank,v in enumerate(values,1))
    ideal = dcg(sorted(labels.values(), reverse=True)[:5])
    return {'precision_at5': sum(v >= 1 for v in gains)/5,
            'ndcg_at5': dcg(gains)/ideal if ideal else 0.0,
            'no_relevant_in_pool': ideal == 0}
