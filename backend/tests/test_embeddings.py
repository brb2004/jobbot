from uuid import uuid4

from app.db.models_db import Job, Resume
from app.services import embedding_services as embeddings


class FakeEmbedder:
    def __init__(self):
        self.embedded = []

    async def embed(self, texts: list[str]) -> list[list[float]]:
        self.embedded += texts
        return [[float(len(t)), 1.0] for t in texts]


async def test_each_unique_term_is_embedded_once(session):
    session.add_all([
        Job(title="A", requirements=["Python", "Docker"]),
        Job(title="B", requirements=["python", "Go"]),
        Resume(user_id=uuid4(), skills=["Docker", "Prometheus"]),
    ])
    await session.commit()
    emb = FakeEmbedder()

    first = await embeddings.embed_new_terms(session, emb)
    second = await embeddings.embed_new_terms(session, emb)

    assert (first, second) == (4, 0)
    assert sorted(emb.embedded) == ["docker", "go", "prometheus", "python"]


async def test_vectors_for_returns_cached_vectors(session):
    session.add(Job(title="A", requirements=["Python"]))
    await session.commit()
    await embeddings.embed_new_terms(session, FakeEmbedder())

    vecs = await embeddings.vectors_for(session, ["Python", "Unknown"])

    assert vecs == {"python": [6.0, 1.0]}
