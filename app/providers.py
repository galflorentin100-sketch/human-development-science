from dataclasses import dataclass
from typing import Protocol
from time import perf_counter,sleep
from uuid import uuid4
import json
from app.models import now
@dataclass(frozen=True)
class ModelRequest: task:str; prompt:str; safety_profile:str="local-safe"; request_id:str=""
@dataclass(frozen=True)
class ModelResponse: content:str; provider:str; model:str; input_tokens:int=0; output_tokens:int=0; estimated_cost:float=0.0
class ModelProvider(Protocol):
    def complete(self,request:ModelRequest)->ModelResponse: ...
class LocalProvider:
    def complete(self,request): return ModelResponse("LOCAL_PROVIDER: no external model configured. Treat this output as unverified.","local","none")
class ProviderRouter:
    def __init__(self,providers=None,retries=2): self.providers=providers or {"local":LocalProvider()}; self.retries=retries
    def complete(self,request):
        last=None
        for attempt in range(self.retries+1):
            try: return next(iter(self.providers.values())).complete(request)
            except Exception as exc:
                last=exc
                if attempt<self.retries: sleep(0.05*(attempt+1))
        raise last
class ObservableProvider:
    def __init__(self,provider,db): self.provider=provider; self.db=db
    def complete(self,request):
        started=perf_counter(); correlation=request.request_id or str(uuid4()); error=None
        try:
            r=self.provider.complete(request); status="COMPLETED"
        except Exception as exc:
            r=ModelResponse("",getattr(self.provider,"name","unknown"),"unknown"); status="FAILED"; error=str(exc); raise
        finally:
            latency=int((perf_counter()-started)*1000)
            self.db.execute("INSERT INTO model_calls(id,correlation_id,provider,model,purpose,input_metadata,output_metadata,input_tokens,output_tokens,estimated_cost,latency_ms,retry_count,status,error,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(str(uuid4()),correlation,r.provider,r.model,request.task,"{}",json.dumps({"safety_profile":request.safety_profile}),r.input_tokens,r.output_tokens,r.estimated_cost,latency,0,status,error,now()))
        return r
