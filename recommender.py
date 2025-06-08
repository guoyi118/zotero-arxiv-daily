import numpy as np
from openai import OpenAI
import os
from paper import ArxivPaper
from datetime import datetime
from sentence_transformers import SentenceTransformer

def get_embeddings_batch(client, texts, batch_size=25):
    all_emb = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i:i+batch_size]
        resp = client.embeddings.create(
            model="text-embedding-v2",
            input=batch,
            dimensions=1024,
            encoding_format="float"
        ).data
        all_emb.extend(resp)
    return all_emb

def rerank_paper_v3(candidate: list[ArxivPaper], corpus: list[dict], api_key: str = None, base_url: str = None) -> list[ArxivPaper]:
    # OpenAI text-embedding-v3实现
    client = OpenAI(
        api_key=api_key or os.getenv("DASHSCOPE_API_KEY") or os.getenv("OPENAI_API_KEY"),
        base_url=base_url or os.getenv("DASHSCOPE_BASE_URL") or os.getenv("OPENAI_API_BASE") or "https://dashscope.aliyuncs.com/compatible-mode/v1"
    )
    corpus = sorted(corpus, key=lambda x: datetime.strptime(x['data']['dateAdded'], '%Y-%m-%dT%H:%M:%SZ'), reverse=True)
    time_decay_weight = 1 / (1 + np.log10(np.arange(len(corpus)) + 1))
    time_decay_weight = time_decay_weight / time_decay_weight.sum()
    corpus_texts = [paper['data']['abstractNote'] for paper in corpus]
    candidate_texts = [paper.summary for paper in candidate]
    corpus_emb = get_embeddings_batch(client, corpus_texts, batch_size=25)
    candidate_emb = get_embeddings_batch(client, candidate_texts, batch_size=25)
    corpus_feature = np.array([item.embedding for item in corpus_emb])
    candidate_feature = np.array([item.embedding for item in candidate_emb])
    corpus_feature = corpus_feature / np.linalg.norm(corpus_feature, axis=1, keepdims=True)
    candidate_feature = candidate_feature / np.linalg.norm(candidate_feature, axis=1, keepdims=True)
    sim = candidate_feature @ corpus_feature.T
    scores = (sim * time_decay_weight).sum(axis=1) * 10
    # 归一化到0~10
    min_score = np.min(scores)
    max_score = np.max(scores)
    if max_score > min_score:
        scores = (scores - min_score) / (max_score - min_score) * 10
    else:
        scores = np.zeros_like(scores)
    for s, c in zip(scores, candidate):
        c.score = float(s)
    candidate = sorted(candidate, key=lambda x: x.score, reverse=True)
    return candidate


def rerank_paper_st(candidate:list[ArxivPaper],corpus:list[dict],model:str='avsolatorio/GIST-small-Embedding-v0') -> list[ArxivPaper]:
    # sentence-transformer实现
    encoder = SentenceTransformer(model)
    #sort corpus by date, from newest to oldest
    corpus = sorted(corpus,key=lambda x: datetime.strptime(x['data']['dateAdded'], '%Y-%m-%dT%H:%M:%SZ'),reverse=True)
    time_decay_weight = 1 / (1 + np.log10(np.arange(len(corpus)) + 1))
    time_decay_weight = time_decay_weight / time_decay_weight.sum()
    corpus_feature = encoder.encode([paper['data']['abstractNote'] for paper in corpus])
    candidate_feature = encoder.encode([paper.summary for paper in candidate])
    sim = encoder.similarity(candidate_feature,corpus_feature) # [n_candidate, n_corpus]
    scores = (sim * time_decay_weight).sum(axis=1) * 10 # [n_candidate]
    # 归一化到0~10
    min_score = np.min(scores)
    max_score = np.max(scores)
    if max_score > min_score:
        scores = (scores - min_score) / (max_score - min_score) * 10
    else:
        scores = np.zeros_like(scores)
    for s,c in zip(scores,candidate):
        c.score = float(s)
    candidate = sorted(candidate,key=lambda x: x.score,reverse=True)
    return candidate