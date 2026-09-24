from dataclasses import dataclass
from typing import Protocol
from time import perf_counter,sleep
from random import uniform
from uuid import uuid4
import json
from app.models import now
@dataclass(frozen=True)
class ModelRequest: task:str; prompt:str; safety_profile:str="local-safe"; request_id:str=""
@dataclass(frozen=True)
class ModelResponse: content:str; provider:str; model:str; input_tokens:int=0; output_tokens:int=0; estimated_cost:float=0.0
class ModelProvider(Protocol):
    def complete(self,request:ModelRequest)->ModelResponse: ...
    def estimate_cost(self,request:ModelRequest)->float: ...
class LocalProvider:
    def estimate_cost(self,request): return 0.0
    def complete(self,request): return ModelResponse("LOCAL_PROVIDER: no external model configured. Treat this output as unverified.","local","none")
class ProviderRouter:
    TRANSIENT_ERRORS=(TimeoutError, ConnectionError)
    def __init__(self,providers=None,retries=2):
        self.providers=providers or {"local":LocalProvider()}
        if not self.providers: raise ValueError("at least one provider is required")
        if retries < 0: raise ValueError("retries must be non-negative")
        self.retries=int(retries)
    def complete(self,request):
        last=None
        for provider_name, provider in self.providers.items():
            attempts=self.retries+1
            for attempt in range(attempts):
                try:
                    return provider.complete(request)
                except self.TRANSIENT_ERRORS as exc:
                    last=exc
                    if attempt < self.retries:
                        delay=min(2.0,0.1*(2**attempt))+uniform(0.0,0.05)
                        sleep(delay)
                except Exception:
                    raise
        if last is not None:
            raise last
        raise RuntimeError("all model providers failed")
class ObservableProvider:
    def __init__(self,provider,db): self.provider=provider; self.db=db
    def preflight(self,request):
        provider_name=getattr(self.provider,"name",self.provider.__class__.__name__).lower()
        if provider_name in {"local","localprovider"}: return 0.0
        estimator=getattr(self.provider,"estimate_cost",None)
        if estimator is None: raise RuntimeError("external provider must implement estimate_cost; spend is blocked by default")
        return float(estimator(request))

    def complete(self,request):
        started=perf_counter(); correlation=request.request_id or str(uuid4()); error=None
        try:
            r=self.provider.complete(request); status="COMPLETED"
        except Exception as exc:
            r=ModelResponse("",getattr(self.provider,"name","unknown"),"unknown"); status="FAILED"; error=str(exc)
        finally:
            latency=int((perf_counter()-started)*1000)
            self.db.execute("INSERT INTO model_calls(id,correlation_id,provider,model,purpose,input_metadata,output_metadata,input_tokens,output_tokens,estimated_cost,latency_ms,retry_count,status,error,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(str(uuid4()),correlation,r.provider,r.model,request.task,"{}",json.dumps({"safety_profile":request.safety_profile}),r.input_tokens,r.output_tokens,r.estimated_cost,latency,0,status,error,now()))
        if error: raise RuntimeError(error)
        return r
