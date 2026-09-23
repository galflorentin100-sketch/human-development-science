from uuid import uuid4
import hashlib
from app.models import now
class EvidencePipeline:
    def __init__(self,db): self.db=db
    def register_source(self,title,url,authors="",year=None,source_type="PAPER"):
        sid=str(uuid4())
        self.db.execute("INSERT OR IGNORE INTO sources(id,title,url,authors,publication_year,source_type,verified_at,provenance_note) VALUES (?,?,?,?,?,?,?,?)",(sid,title,url,authors,year,source_type,now(),"Discovered source; content not verified until reviewed."))
        row=self.db.one("SELECT * FROM sources WHERE url=?",(url,))
        return row
    def ingest_text(self,source_id,text):
        digest=hashlib.sha256(text.encode("utf-8")).hexdigest()
        eid=str(uuid4())
        self.db.execute("INSERT INTO evidence_sources(id,source_id,state,content_hash,fetched_at,parsed_at,created_at) VALUES (?,?,?, ?,?,?,?)",(eid,source_id,"PARSED",digest,now(),now(),now()))
        return self.db.one("SELECT * FROM evidence_sources WHERE id=?",(eid,))
    def attach(self,claim_id,source_id,excerpt,stance="SUPPORTS",verified=False):
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
