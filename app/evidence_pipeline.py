from uuid import uuid4
import hashlib
from app.models import now
class EvidencePipeline:
    def __init__(self,db): self.db=db
    def register_source(self,title,url,authors="",year=None,source_type="PAPER"):
        sid=str(uuid4())
        self.db.execute("INSERT OR IGNORE INTO sources(id,title,url,authors,publication_year,source_type,verified_at,provenance_note) VALUES (?,?,?,?,?,?,?,?)",(sid,title,url,authors,year,source_type,None,"Discovered source; content not verified until reviewed."))
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
    def attach(self,claim_id,source_id,excerpt,stance="SUPPORTS",verified=False):
        if stance not in {"SUPPORTS","CONTRADICTS","NEUTRAL"}: raise ValueError("invalid evidence stance")
        source=self.db.one("SELECT * FROM sources WHERE id=?",(source_id,))
        claim=self.db.one("SELECT * FROM claims WHERE id=?",(claim_id,))
        if not source or not claim: raise ValueError("claim or source not found")
        if verified and not self.db.one("SELECT 1 FROM evidence_sources WHERE source_id=? AND state='PARSED' ORDER BY parsed_at DESC LIMIT 1",(source_id,)):
            raise ValueError("cannot mark evidence verified before source content is parsed")
        eid=str(uuid4())
        self.db.execute("INSERT INTO evidence(id,claim_id,source_id,stance,excerpt,verified,created_at) VALUES (?,?,?,?,?,?,?)",(eid,claim_id,source_id,stance,excerpt,int(verified),now()))
        return self.db.one("SELECT * FROM evidence WHERE id=?",(eid,))
    def review(self,evidence_id,reviewer,verdict,rationale):
        evidence=self.db.one("SELECT * FROM evidence WHERE id=?",(evidence_id,))
        if not evidence: raise ValueError("evidence not found")
        normalized=str(verdict).upper()
        if normalized not in {"VERIFIED","REJECTED","UNCERTAIN"}:
            raise ValueError("invalid evidence verdict")
        if not rationale or not str(rationale).strip():
            raise ValueError("review rationale is required")
        rid=str(uuid4())
        self.db.execute("INSERT INTO evidence_reviews(id,evidence_id,reviewer,verdict,rationale,created_at) VALUES (?,?,?,?,?,?)",(rid,evidence_id,reviewer,normalized,rationale,now()))
        verified=1 if normalized=="VERIFIED" else 0
        self.db.execute("UPDATE evidence SET verified=? WHERE id=?",(verified,evidence_id))
        return self.db.one("SELECT * FROM evidence_reviews WHERE id=?",(rid,))
