from uuid import uuid4
import hashlib
from app.models import now
class EvidencePipeline:
    def __init__(self,db): self.db=db
    def register_source(self,title,url,authors="",year=None,source_type="PAPER"):
        sid=str(uuid4())
        self.db.execute("INSERT OR IGNORE INTO sources(id,title,url,authors,publication_year,source_type,verified_at,provenance_note) VALUES (?,?,?,?,?,?,?,?)",(sid,title,url,authors,year,source_type,"","Discovered source; content not verified until reviewed."))
        row=self.db.one("SELECT * FROM sources WHERE url=?",(url,))
        return row
    def ingest_text(self,source_id,text):
        if not self.db.one("SELECT 1 FROM sources WHERE id=?",(source_id,)):
            raise ValueError("source not found")
        digest=hashlib.sha256(text.encode("utf-8")).hexdigest()
        existing=self.db.one("SELECT * FROM evidence_sources WHERE source_id=? AND content_hash=? ORDER BY created_at DESC LIMIT 1",(source_id,digest))
        if existing:
            return existing
        eid=str(uuid4())
        self.db.execute("INSERT INTO evidence_sources(id,source_id,state,content_hash,fetched_at,parsed_at,created_at) VALUES (?,?,?, ?,?,?,?)",(eid,source_id,"PARSED",digest,now(),now(),now()))
        return self.db.one("SELECT * FROM evidence_sources WHERE id=?",(eid,))
    def attach(self,claim_id,source_id,excerpt,stance="SUPPORTS",verified=False,actor="system"):
        if stance not in {"SUPPORTS","CONTRADICTS","NEUTRAL"}: raise ValueError("invalid evidence stance")
        source=self.db.one("SELECT * FROM sources WHERE id=?",(source_id,))
        claim=self.db.one("SELECT * FROM claims WHERE id=?",(claim_id,))
        if not source or not claim: raise ValueError("claim or source not found")
        if verified:
            raise ValueError("evidence verification is reviewer-controlled; attach as unverified and use review() to verify")
        if not self.db.one("SELECT 1 FROM evidence_sources WHERE source_id=? AND state='PARSED' ORDER BY parsed_at DESC LIMIT 1",(source_id,)):
            raise ValueError("cannot attach evidence before source content is parsed")
        eid=str(uuid4())
        excerpt_hash=hashlib.sha256(excerpt.encode("utf-8")).hexdigest()
        self.db.execute("INSERT INTO evidence(id,claim_id,source_id,stance,excerpt,verified,created_by,excerpt_hash,created_at) VALUES (?,?,?,?,?,?,?,?,?)",(eid,claim_id,source_id,stance,excerpt,int(verified),actor,excerpt_hash,now()))
        return self.db.one("SELECT * FROM evidence WHERE id=?",(eid,))
    def resolve(self,evidence_id):
        evidence=self.db.one("SELECT * FROM evidence WHERE id=?",(evidence_id,))
        if not evidence: raise ValueError("evidence not found")
        reviews=self.db.all("SELECT verdict FROM evidence_reviews WHERE evidence_id=?",(evidence_id,))
        verdicts={str(r["verdict"]).upper() for r in reviews}
        if "VERIFIED" in verdicts and "REJECTED" in verdicts: state="CONFLICTED"
        elif "VERIFIED" in verdicts: state="VERIFIED"
        elif "REJECTED" in verdicts: state="REJECTED"
        elif "UNCERTAIN" in verdicts: state="UNCERTAIN"
        else: state="UNREVIEWED"
        return {"evidence_id":evidence_id,"claim_id":evidence["claim_id"],"state":state,"review_count":len(reviews),
                "source_id":evidence["source_id"],"stance":evidence["stance"],"excerpt_hash":evidence["excerpt_hash"]}

    def claim_evidence_state(self,claim_id):
        rows=self.db.all("SELECT id FROM evidence WHERE claim_id=? ORDER BY created_at",(claim_id,))
        resolved=[self.resolve(r["id"]) for r in rows]
        return {"claim_id":claim_id,"evidence":resolved,
                "verified_support":sum(x["state"]=="VERIFIED" and x["stance"]=="SUPPORTS" for x in resolved),
                "verified_contradict":sum(x["state"]=="VERIFIED" and x["stance"]=="CONTRADICTS" for x in resolved),
                "conflicted":sum(x["state"]=="CONFLICTED" for x in resolved)}

    def review(self,evidence_id,reviewer,verdict,rationale):
        evidence=self.db.one("SELECT * FROM evidence WHERE id=?",(evidence_id,))
        if not evidence: raise ValueError("evidence not found")
        normalized=str(verdict).upper()
        if normalized not in {"VERIFIED","REJECTED","UNCERTAIN"}: raise ValueError("invalid evidence verdict")
        if not rationale or not str(rationale).strip(): raise ValueError("review rationale is required")
        if evidence.get("created_by") not in (None, "", "system") and reviewer == evidence["created_by"]:
            raise ValueError("reviewer must be independent from the evidence creator")
        if self.db.one("SELECT 1 FROM evidence_reviews WHERE evidence_id=? AND reviewer=?",(evidence_id,reviewer)):
            raise ValueError("reviewer has already reviewed this evidence")
        rid=str(uuid4())
        self.db.execute("INSERT INTO evidence_reviews(id,evidence_id,reviewer,verdict,rationale,created_at) VALUES (?,?,?,?,?,?)",(rid,evidence_id,reviewer,normalized,rationale,now()))
        resolved=self.resolve(evidence_id)
        self.db.execute("UPDATE evidence SET verified=? WHERE id=?",(1 if resolved["state"]=="VERIFIED" else 0,evidence_id))
        if resolved["state"]=="CONFLICTED":
            claim=self.db.one("SELECT status FROM claims WHERE id=?",(evidence["claim_id"],))
            if claim and claim["status"] in {"SUPPORTED","CONTRADICTED"}:
                ts=now()
                self.db.execute("UPDATE claims SET status='UNCERTAIN',review_required=1,updated_at=? WHERE id=?",(ts,evidence["claim_id"]))
                self.db.execute("INSERT INTO claim_state_transitions(id,claim_id,prior_status,new_status,actor,rationale,evidence_id,created_at) VALUES (?,?,?,?,?,?,?,?)",
                    (str(uuid4()),evidence["claim_id"],claim["status"],"UNCERTAIN",reviewer,"conflicting evidence review verdicts",evidence_id,ts))
        return self.db.one("SELECT * FROM evidence_reviews WHERE id=?",(rid,))

