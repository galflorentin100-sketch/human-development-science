"""Dependency-aware impact propagation for HDS.

This engine is intentionally conservative: it discovers explicit database
relationships and reports potentially affected records. It never changes
scientific claims, protocols, or knowledge automatically.
"""
import json
from collections import deque
from app.models import now

class KnowledgeImpactEngine:
    ROOT_TABLES=("claims","evidence","research_findings","interventions","training_protocols")

    def __init__(self,db):
        self.db=db
        self._ensure()

    def _ensure(self):
        self.db.execute("""CREATE TABLE IF NOT EXISTS knowledge_impact_reviews (
            id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL,
            source_type TEXT NOT NULL,
            source_id TEXT NOT NULL,
            impact_type TEXT NOT NULL,
            affected_type TEXT NOT NULL,
            affected_id TEXT NOT NULL,
            reason TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'PROPOSED',
            created_at TEXT NOT NULL,
            UNIQUE(project_id,source_type,source_id,affected_type,affected_id)
        )""")

    def _tables(self):
        rows=self.db.all("SELECT name FROM sqlite_master WHERE type='table'")
        return {r["name"] for r in rows}

    def _columns(self,table):
        return {r["name"] for r in self.db.all(f"PRAGMA table_info({table})")}

    def _rows_with_ref(self,table,source_id):
        cols=self._columns(table)
        candidates={"id","claim_id","source_claim_id","evidence_id","evidence_ref",
                    "finding_id","intervention_id","protocol_id","project_id",
                    "source_id","research_finding_id"}
        usable=candidates & cols
        if not usable: return []
        clauses=[]; params=[]
        for c in usable:
            clauses.append(f'"{c}"=?'); params.append(str(source_id))
        return self.db.all(f'SELECT * FROM "{table}" WHERE '+" OR ".join(clauses),tuple(params))

    def propagate(self,project_id,source_type,source_id,reason="upstream scientific state changed"):
        if source_type not in self.ROOT_TABLES:
            raise ValueError("unsupported source_type")
        # Prefer the explicit knowledge graph. The legacy schema scanner remains
        # only as a fallback for root records that have not yet been materialized.
        from app.knowledge_graph import KnowledgeDependencyGraph
        graph=KnowledgeDependencyGraph(self.db)
        type_map={"claims":"CLAIM","evidence":"EVIDENCE","research_findings":"FINDING",
                  "interventions":"INTERVENTION","training_protocols":"TRAINING_PROTOCOL"}
        graph_type=type_map[source_type]
        trace=graph.impacted(project_id,graph_type,source_id)
        if trace["affected"]:
            impacts=[{"type":n["type"],"id":n["id"],"depth":None,"reason":reason} for n in trace["affected"]]
            for x in impacts:
                self.db.execute("""INSERT OR IGNORE INTO knowledge_impact_reviews
                    (id,project_id,source_type,source_id,impact_type,affected_type,
                     affected_id,reason,status,created_at)
                    VALUES (lower(hex(randomblob(16))),?,?,?,?,?,?,?,?,?)""",
                    (project_id,source_type,str(source_id),"GRAPH_DEPENDENCY",
                     x["type"],x["id"],reason,"PROPOSED",now()))
            return {"project_id":project_id,"source":{"type":source_type,"id":str(source_id)},
                    "affected_count":len(impacts),"affected":impacts,
                    "guardrail":"Potential impact only; human review is required before scientific state changes.",
                    "engine":"explicit_knowledge_graph"}
        tables=self._tables()
        queue=deque([(source_type,str(source_id),0)])
        seen={(source_type,str(source_id))}
        impacts=[]
        while queue:
            table,sid,depth=queue.popleft()
            for target in tables:
                if target.startswith("sqlite_") or target=="knowledge_impact_reviews":
                    continue
                for row in self._rows_with_ref(target,sid):
                    rid=row.get("id")
                    if not rid: continue
                    key=(target,str(rid))
                    if key in seen: continue
                    seen.add(key)
                    impact={
                        "type":target,"id":str(rid),"depth":depth+1,
                        "reason":reason,
                    }
                    impacts.append(impact)
                    if depth<4:
                        queue.append((target,str(rid),depth+1))
        for x in impacts:
            self.db.execute("""INSERT OR IGNORE INTO knowledge_impact_reviews
                (id,project_id,source_type,source_id,impact_type,affected_type,
                 affected_id,reason,status,created_at)
                VALUES (lower(hex(randomblob(16))),?,?,?,?,?,?,?,?,?)""",
                (project_id,source_type,str(source_id),"DEPENDENCY",x["type"],
                 x["id"],reason,"PROPOSED",now()))
        return {"project_id":project_id,"source":{"type":source_type,"id":str(source_id)},
                "affected_count":len(impacts),"affected":impacts,
                "guardrail":"Potential impact only; human review is required before scientific state changes."}

    def review(self, review_id, reviewer, decision, rationale):
        row=self.db.one("SELECT * FROM knowledge_impact_reviews WHERE id=?",(review_id,))
        if not row: raise ValueError("impact review not found")
        if row["status"]!="PROPOSED": raise ValueError("impact review is no longer pending")
        if not str(reviewer or "").strip() or not str(rationale or "").strip():
            raise ValueError("reviewer and rationale are required")
        decision=str(decision).upper()
        if decision not in {"ACCEPT","REJECT"}:
            raise ValueError("decision must be ACCEPT or REJECT")
        status="ACCEPTED" if decision=="ACCEPT" else "REJECTED"
        self.db.execute("UPDATE knowledge_impact_reviews SET status=? WHERE id=? AND status='PROPOSED'",(status,review_id))
        if decision=="ACCEPT":
            from app.research_queue import ResearchQueue
            ResearchQueue(self.db).propose(
                row["project_id"],
                question=f"Reassess knowledge affected by {row['source_type']}:{row['source_id']} ({row['affected_type']}:{row['affected_id']})",
                rationale="Founder-approved impact review identified a dependency that should be reassessed.",
                trigger_type="KNOWLEDGE_IMPACT_REVIEW",
                evidence_refs=(),
                priority="HIGH",
            )
        self.db.audit("scientific.impact_reviewed","knowledge_impact_review",review_id,reviewer,
                      {"decision":decision,"rationale":rationale},now(),None)
        return self.db.one("SELECT * FROM knowledge_impact_reviews WHERE id=?",(review_id,))

    def list(self,project_id,status=None):
        sql="SELECT * FROM knowledge_impact_reviews WHERE project_id=?"
        params=[project_id]
        if status:
            sql+=" AND status=?"; params.append(status)
        sql+=" ORDER BY created_at DESC"
        return self.db.all(sql,tuple(params))
