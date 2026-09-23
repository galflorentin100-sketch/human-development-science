from app.models import AgentDefinition
INITIAL_AGENTS=[
("ceo","CEO","strategy","board"),("coo","COO","operations","ceo"),("chief-scientist","Chief Scientist","science","ceo"),("cto","CTO","technology","ceo"),("cpo","CPO","product","ceo"),("cfo","CFO","finance","ceo"),("risk-officer","Risk Officer","risk","ceo"),("researcher","Researcher","research","chief-scientist"),("evidence-auditor","Evidence Auditor","evidence","chief-scientist"),("experiment-designer","Experiment Designer","experiments","chief-scientist"),("data-scientist","Data Scientist","measurement","chief-scientist"),("skeptic","Skeptic","critique","chief-scientist"),("research-synthesizer","Research Synthesizer","synthesis","chief-scientist"),("red-team","Red Team","adversarial-review","risk-officer"),("product-manager","Product Manager","product-delivery","cpo"),("engineer","Engineer","engineering","cto"),("qa","QA","quality","cto")]
ALIASES={"literature-search":"researcher","literature researcher":"researcher","evidence-review":"evidence-auditor","critical-review":"skeptic"}
def find_agent(query):
    q=query.strip().lower()
    q=ALIASES.get(q,q)
    for a,n,r,m in INITIAL_AGENTS:
        if q in (a,n.lower(),r.lower()): return AgentDefinition(a,n,r,m)
    raise KeyError(query)
def all_agents(): return [AgentDefinition(a,n,r,m) for a,n,r,m in INITIAL_AGENTS]
