import asyncio
from typing import AsyncGenerator, List, Dict

class Agent:
    def __init__(self, system_prompt: str = "You are a helpful AI assistant."):
        self.system_prompt = system_prompt
        self.history: List[Dict[str, str]] = [
            {"role": "system", "content": system_prompt}
        ]

    async def stream(self, prompt: str) -> AsyncGenerator[str, None]:
        from voodoo.telemetry import telemetry_store
        self.history.append({"role": "user", "content": prompt})
        
        # In a real scenario, this would connect to OpenAI/Anthropic etc.
        # For this standalone framework, we'll simulate a streaming response
        # or use an actual API if configured.
        
        # Simulating a stream of tokens:
        words = f"This is an AI response to: '{prompt}'. In a real app, this streams from an LLM. Here are some more tokens to simulate streaming.".split(" ")
        
        telemetry_store.record_agent_tokens(len(prompt.split()) + len(words))
        
        full_response = ""
        for word in words:
            await asyncio.sleep(0.1)  # Simulate network latency
            token = word + " "
            full_response += token
            yield token
            
        self.history.append({"role": "assistant", "content": full_response.strip()})
        
    async def run(self, prompt: str) -> str:
        response = ""
        async for chunk in self.stream(prompt):
            response += chunk
        return response
