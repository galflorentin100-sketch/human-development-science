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


class AnthropicMessagesProvider:
    """Minimal synchronous Anthropic Messages API adapter.

    External execution is opt-in via HDS_MODEL_PROVIDER=anthropic and requires
    an API key plus explicit token-rate configuration for spend preflight.
    """

    name="anthropic"

    def __init__(self, api_key=None, model=None, input_rate=None, output_rate=None, timeout=60.0):
        import os
        self.api_key=api_key or os.getenv("ANTHROPIC_API_KEY")
        self.model=model or os.getenv("HDS_ANTHROPIC_MODEL","claude-sonnet-5")
        self.input_rate=float(input_rate if input_rate is not None else os.getenv("HDS_INPUT_COST_PER_MILLION_TOKENS","0"))
        self.output_rate=float(output_rate if output_rate is not None else os.getenv("HDS_OUTPUT_COST_PER_MILLION_TOKENS","0"))
        self.timeout=float(timeout)
        if not self.api_key:
            raise RuntimeError("ANTHROPIC_API_KEY is required when HDS_MODEL_PROVIDER=anthropic")
        if self.input_rate < 0 or self.output_rate < 0:
            raise ValueError("model token rates must be non-negative")

    def _estimate_tokens(self, text):
        return max(1, (len(text.encode("utf-8")) + 3) // 4)

    def estimate_cost(self, request):
        if self.input_rate <= 0 or self.output_rate <= 0:
            raise RuntimeError("explicit HDS_INPUT_COST_PER_MILLION_TOKENS and HDS_OUTPUT_COST_PER_MILLION_TOKENS are required for external spend")
        input_tokens=self._estimate_tokens(request.prompt)
        max_output=4096
        return (input_tokens*self.input_rate + max_output*self.output_rate) / 1_000_000.0

    def complete(self, request):
        import httpx
        try:
            response=httpx.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": self.model,
                "max_tokens": 4096,
                "messages":[{"role":"user","content":request.prompt}],
            },
                timeout=self.timeout,
            )
        except httpx.TimeoutException as exc:
            raise TimeoutError("Anthropic request timed out") from exc
        except httpx.ConnectError as exc:
            raise ConnectionError("Anthropic connection failed") from exc
        if response.status_code >= 400:
            detail=response.text[:2000]
            if response.status_code in {408,429} or response.status_code >= 500:
                raise TimeoutError(f"Anthropic transient HTTP {response.status_code}: {detail}")
            raise RuntimeError(f"Anthropic HTTP {response.status_code}: {detail}")
        payload=response.json()
        text="".join(
            block.get("text","") for block in payload.get("content",[])
            if isinstance(block,dict) and block.get("type")=="text"
        )
        usage=payload.get("usage") or {}
        input_tokens=int(usage.get("input_tokens") or 0)
        output_tokens=int(usage.get("output_tokens") or 0)
        cost=(input_tokens*self.input_rate + output_tokens*self.output_rate)/1_000_000.0
        return ModelResponse(text,self.name,self.model,input_tokens,output_tokens,cost)


def configured_provider():
    import os
    provider=os.getenv("HDS_MODEL_PROVIDER","local").strip().lower()
    if provider=="local":
        return LocalProvider()
    if provider=="anthropic":
        return AnthropicMessagesProvider()
    raise ValueError(f"unsupported HDS_MODEL_PROVIDER: {provider}")
