from dataclasses import dataclass
from typing import Protocol
@dataclass(frozen=True)
class ModelRequest: task:str; prompt:str; safety_profile:str="local-safe"; request_id:str=""
@dataclass(frozen=True)
class ModelResponse: content:str; provider:str; model:str; input_tokens:int=0; output_tokens:int=0; estimated_cost:float=0.0
class ModelProvider(Protocol):
    def complete(self,request:ModelRequest)->ModelResponse: ...
class LocalProvider:
    def complete(self,request):
        return ModelResponse("LOCAL_PROVIDER: no external model configured. Treat this output as unverified.", "local","none")
class ProviderRouter:
    def __init__(self,providers=None): self.providers=providers or {"local":LocalProvider()}
    def complete(self,request): return next(iter(self.providers.values())).complete(request)
class ObservableProvider:
    def __init__(self,provider,db): self.provider=provider; self.db=db
    def complete(self,request):
        r=self.provider.complete(request)
        return r
