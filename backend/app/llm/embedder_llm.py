from openai import AsyncOpenAI


class LLMEmbedder:
    def __init__(self, client: AsyncOpenAI, model: str):
        self.client = client
        self.model = model

    async def embed(self, texts: list[str]) -> list[list[float]]:
        resp = await self.client.embeddings.create(model=self.model, input=texts)
        return [d.embedding for d in sorted(resp.data, key=lambda d: d.index)]
