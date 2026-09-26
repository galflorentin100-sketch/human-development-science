"""Explicit, auditable scientific knowledge graph.

The graph stores declared relationships only. It never infers efficacy from
graph connectivity.
"""
import json
from uuid import uuid4
from app.models import now

class KnowledgeDependencyGraph:
    def __init__(self,db):
        self.db=db
        self.db.execute("""CREATE TABLE IF NOT EXISTS knowledge_edges (
            id TEXT PRIMARY KEY, project_id TEXT NOT NULL, from_type TEXT NOT NULL,
            from_id TEXT NOT NULL, relation TEXT NOT NULL, to_type TEXT NOT NULL,
            to_id TEXT NOT NULL, provenance_refs TEXT NOT NULL DEFAULT '[]',
            status TEXT NOT NULL DEFAULT 'ACTIVE', created_by TEXT NOT NULL,
            created_at TEXT NOT NULL,
            UNIQUE(project_id,from_type,from_id,relation,to_type,to_id)
        )""")

    def add_edge(self,project_id,from_type,from_id,relation,to_type,to_id,provenance_refs=(),created_by="system"):
        if not self.db.one("SELECT 1 FROM projects WHERE id=?",(project_id,)): raise ValueError("project not found")
        allowed={"CLAIM":"claims","INTERVENTION":"interventions","TRAINING_PROTOCOL":"training_protocols","FINDING":"research_findings","QUESTION":"research_questions","EXPERIMENT":"hds_experiments"}
        ownership_queries={
            "CLAIM":"SELECT project_id FROM claims WHERE id=?",
            "INTERVENTION":"SELECT project_id FROM interventions WHERE id=?",
            "TRAINING_PROTOCOL":"SELECT project_id FROM training_protocols WHERE id=?",
            "FINDING":"SELECT project_id FROM research_findings WHERE id=?",
            "QUESTION":"SELECT project_id FROM research_questions WHERE id=?",
            "EXPERIMENT":"SELECT project_id FROM hds_experiments WHERE id=?",
            "EVIDENCE":"SELECT c.project_id FROM evidence e JOIN claims c ON c.id=e.claim_id WHERE e.id=?",
            "TRAINING_SESSION":"SELECT p.project_id FROM training_sessions s JOIN training_protocols p ON p.id=s.protocol_id WHERE s.id=?",
            "EXPERIMENT_RESULT":"SELECT e.project_id FROM hds_experiment_results r JOIN hds_experiments e ON e.id=r.experiment_id WHERE r.id=?",
            "PROJECT":"SELECT id AS project_id FROM projects WHERE id=?"
        }
        for typ,nid in ((from_type,from_id),(to_type,to_id)):
            query=ownership_queries.get(str(typ).upper())
            if query:
                row=self.db.one(query,(str(nid),))
                if not row: raise ValueError(f"{typ} node not found")
                if str(row["project_id"])!=str(project_id): raise ValueError(f"{typ} node belongs to another project")
        refs=[str(x) for x in provenance_refs]
        for ref in refs:
            ev=self.db.one("SELECT c.project_id FROM evidence e JOIN claims c ON c.id=e.claim_id WHERE e.id=?",(ref,))
            if ev and str(ev["project_id"])!=str(project_id): raise ValueError("provenance evidence belongs to another project")
        self.db.execute("""INSERT OR IGNORE INTO knowledge_edges
            (id,project_id,from_type,from_id,relation,to_type,to_id,provenance_refs,status,created_by,created_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (str(uuid4()),project_id,from_type,str(from_id),relation,to_type,str(to_id),
             json.dumps(refs,sort_keys=True),"ACTIVE",created_by,now()))
        return self.db.one("""SELECT * FROM knowledge_edges WHERE project_id=? AND from_type=? AND from_id=? AND relation=? AND to_type=? AND to_id=?""",
            (project_id,from_type,str(from_id),relation,to_type,str(to_id)))

    def build(self,project_id=None):
        nodes=[]; edges=[]
        tables=[("claims","CLAIM"),("interventions","INTERVENTION"),("training_protocols","TRAINING_PROTOCOL"),
                ("research_findings","FINDING"),("evidence","EVIDENCE"),("research_questions","QUESTION"),("hds_experiments","EXPERIMENT")]
        for table,typ in tables:
            try:
                columns=set(self.db.table_columns(table))
                where=" WHERE project_id=?" if project_id and "project_id" in columns else ""
                rows=self.db.all(f"SELECT * FROM {table}{where}",(project_id,) if where else ())
            except Exception:
                rows=[]
            for row in rows:
                nodes.append({"id":row["id"],"type":typ,"status":row.get("status")})
        if project_id:
            edges=self.db.all("SELECT * FROM knowledge_edges WHERE project_id=? AND status='ACTIVE' ORDER BY created_at",(project_id,))
        else:
            edges=self.db.all("SELECT * FROM knowledge_edges WHERE status='ACTIVE' ORDER BY created_at")
        # Add legacy explicit protocol relationships as read-only graph edges.
        protocols=self.db.all("SELECT * FROM training_protocols")
        for p in protocols:
            if project_id and p.get("project_id")!=project_id: continue
            if p.get("source_claim_id"): edges.append({"from_id":p["source_claim_id"],"to_id":p["id"],"relation":"GROUNDS","from_type":"CLAIM","to_type":"TRAINING_PROTOCOL"})
            if p.get("intervention_id"): edges.append({"from_id":p["intervention_id"],"to_id":p["id"],"relation":"IMPLEMENTS","from_type":"INTERVENTION","to_type":"TRAINING_PROTOCOL"})
        return {"nodes":nodes,"edges":edges,"policy":"graph is descriptive; it does not infer efficacy"}

    def sync_project(self, project_id, actor="system"):
        """Materialize only relationships represented by explicit domain references."""
        created=[]
        def edge(a,aid,rel,b,bid,refs=()):
            if aid and bid:
                before=self.db.one("SELECT id FROM knowledge_edges WHERE project_id=? AND from_type=? AND from_id=? AND relation=? AND to_type=? AND to_id=?",(project_id,a,str(aid),rel,b,str(bid)))
                row=self.add_edge(project_id,a,str(aid),rel,b,str(bid),refs,actor)
                if not before: created.append(row)
        # Source -> Evidence -> Claim is explicit in the evidence schema.
        for r in self.db.all("SELECT e.id evidence_id,e.claim_id,e.source_id FROM evidence e JOIN claims c ON c.id=e.claim_id WHERE c.project_id=?",(project_id,)):
            edge("SOURCE",r["source_id"],"HAS_EVIDENCE","EVIDENCE",r["evidence_id"])
            edge("EVIDENCE",r["evidence_id"],"SUPPORTS_OR_CONTRADICTS","CLAIM",r["claim_id"])
        # Claims / interventions -> training protocols are explicit foreign-key relationships.
        for r in self.db.all("SELECT id,source_claim_id,intervention_id FROM training_protocols WHERE project_id=?",(project_id,)):
            edge("CLAIM",r.get("source_claim_id"),"GROUNDS","TRAINING_PROTOCOL",r["id"])
            edge("INTERVENTION",r.get("intervention_id"),"IMPLEMENTED_BY","TRAINING_PROTOCOL",r["id"])
        # Protocol -> observed training sessions/outcomes is an explicit protocol_id reference.
        for r in self.db.all("SELECT id,protocol_id FROM training_sessions WHERE protocol_id IN (SELECT id FROM training_protocols WHERE project_id=?)",(project_id,)):
            edge("TRAINING_PROTOCOL",r["protocol_id"],"HAS_SESSION","TRAINING_SESSION",r["id"])
        # Research findings have machine-readable evidence refs. Resolve them only
        # through evidence joined to a claim in the same project; an ID alone is
        # insufficient because IDs may be supplied from another project.
        for r in self.db.all("SELECT id,evidence_refs FROM research_findings WHERE project_id=?",(project_id,)):
            try: refs=json.loads(r.get("evidence_refs") or "[]")
            except (TypeError,ValueError): refs=[]
            for ref in refs:
                if self.db.one("SELECT e.id FROM evidence e JOIN claims c ON c.id=e.claim_id WHERE e.id=? AND c.project_id=?",(str(ref),project_id)):
                    edge("EVIDENCE",str(ref),"SUPPORTS_FINDING","FINDING",r["id"],[str(ref)])
        for r in self.db.all("SELECT id,research_question,intervention FROM hds_experiments WHERE project_id=?",(project_id,)):
            edge("PROJECT",project_id,"HAS_EXPERIMENT","EXPERIMENT",r["id"])
            if self.db.one("SELECT id FROM research_questions WHERE id=? AND project_id=?",(r.get("research_question"),project_id)):
                edge("QUESTION",r["research_question"],"TESTED_BY","EXPERIMENT",r["id"])
            if self.db.one("SELECT id FROM interventions WHERE id=? AND project_id=?",(r.get("intervention"),project_id)):
                edge("INTERVENTION",r["intervention"],"TESTED_BY","EXPERIMENT",r["id"])
        for r in self.db.all("SELECT er.id,er.experiment_id FROM hds_experiment_results er JOIN hds_experiments e ON e.id=er.experiment_id WHERE e.project_id=?",(project_id,)):
            edge("EXPERIMENT",r["experiment_id"],"HAS_RESULT","EXPERIMENT_RESULT",r["id"])
        for r in self.db.all("SELECT er.id,er.experiment_id,er.evidence_refs FROM hds_experiment_results er JOIN hds_experiments e ON e.id=er.experiment_id WHERE e.project_id=?",(project_id,)):
            try: refs=json.loads(r.get("evidence_refs") or "[]")
            except (TypeError,ValueError): refs=[]
            for ref in refs:
                if self.db.one("SELECT e.id FROM evidence e JOIN claims c ON c.id=e.claim_id WHERE e.id=? AND c.project_id=?",(str(ref),project_id)):
                    edge("EVIDENCE",str(ref),"SUPPORTS_OR_INFORMS","EXPERIMENT_RESULT",r["id"],[str(ref)])
        for r in self.db.all("SELECT e.id,e.hypothesis FROM experiments e WHERE e.project_id=?",(project_id,)):
            edge("HYPOTHESIS",r.get("hypothesis"),"TESTED_BY","EXPERIMENT",r["id"])
        for r in self.db.all("SELECT er.id,er.experiment_id FROM experiment_results er JOIN experiments e ON e.id=er.experiment_id WHERE e.project_id=?",(project_id,)):
            edge("EXPERIMENT",r["experiment_id"],"HAS_RESULT","EXPERIMENT_RESULT",r["id"])
        return {"project_id":project_id,"created_edges":len(created),"edges":created,"policy":"only explicit, resolvable references are materialized"}

    def neighbors(self,project_id,node_type,node_id):
        return self.db.all("""SELECT * FROM knowledge_edges WHERE project_id=? AND status='ACTIVE'
            AND ((from_id=? AND from_type=?) OR (to_id=? AND to_type=?)) ORDER BY created_at DESC""",
            (project_id,str(node_id),node_type,str(node_id),node_type))

    def trace(self,project_id,node_type,node_id,max_depth=4):
        seen={(node_type,str(node_id))}; frontier=[(node_type,str(node_id),0)]; nodes=[]
        while frontier:
            typ,nid,depth=frontier.pop(0); nodes.append({"type":typ,"id":nid,"depth":depth})
            if depth>=max_depth: continue
            for e in self.neighbors(project_id,typ,nid):
                other=(e["to_type"],e["to_id"]) if e["from_type"]==typ and e["from_id"]==nid else (e["from_type"],e["from_id"])
                if other not in seen:
                    seen.add(other); frontier.append((other[0],other[1],depth+1))
        return {"root":{"type":node_type,"id":str(node_id)},"nodes":nodes,"node_count":len(nodes)}
    def impacted(self, project_id, node_type, node_id, max_depth=4):
        """Return downstream/upstream nodes reachable through declared edges."""
        trace = self.trace(project_id, node_type, node_id, max_depth)
        root = (node_type, str(node_id))
        return {"root": trace["root"],
                "affected": [n for n in trace["nodes"] if (n["type"], n["id"]) != root],
                "node_count": max(0, trace["node_count"] - 1),
                "policy": "dependency trace only; no causal or efficacy inference"}
