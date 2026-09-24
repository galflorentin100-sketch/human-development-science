from __future__ import annotations
import json
from uuid import uuid4
from app.models import now

class BudgetExceeded(Exception):
    pass

class BudgetRequired(Exception):
    pass

class CostControl:
    def __init__(self, db):
        self.db = db

    @staticmethod
    def _row_dict(cursor,row):
        if row is None: return None
        if hasattr(row,"keys"): return dict(row)
        return dict(zip([d.name for d in cursor.description],row))

    def active_budget(self, company_id="hds"):
        return self.db.one("SELECT * FROM budgets WHERE company_id=? AND status='ACTIVE' ORDER BY created_at DESC LIMIT 1",(company_id,))

    def authorize(self, estimated_cost, company_id="hds"):
        if not isinstance(estimated_cost, (int, float)):
            raise ValueError("estimated_cost must be numeric")
        if estimated_cost < 0:
            raise ValueError("estimated_cost cannot be negative")
        budget=self.active_budget(company_id)
        if not budget:
            raise BudgetRequired("model/API spend is blocked until an active budget exists")
        remaining=float(budget["limit_amount"])-float(budget["spent_amount"])
        if estimated_cost > remaining:
            raise BudgetExceeded("requested spend exceeds remaining budget")
        return {"budget_id":budget["id"],"remaining":remaining}

    def reserve(self, correlation_id, amount, provider="unknown", model="unknown", purpose="reserved", actor="system", company_id="hds", metadata=None):
        if not correlation_id: raise ValueError("correlation_id is required")
        if not isinstance(amount,(int,float)) or amount < 0: raise ValueError("amount must be a nonnegative number")
        if amount == 0: return None
        with self.db.transaction() as con:
            cur=con.execute("SELECT * FROM cost_events WHERE correlation_id=?",(correlation_id,))
            existing=cur.fetchone()
            if existing: return self._row_dict(cur,existing)
            budget=self.db.one("SELECT * FROM budgets WHERE company_id=? AND status='ACTIVE' ORDER BY created_at DESC LIMIT 1",(company_id,))
            if not budget: raise BudgetRequired("no active budget")
            cur=con.execute("SELECT * FROM budgets WHERE id=? AND status='ACTIVE'",(budget["id"],))
            row=cur.fetchone()
            if row is None: raise BudgetRequired("active budget disappeared")
            b=self._row_dict(cur,row)
            event_id=str(uuid4()); ts=now()
            updated=con.execute("UPDATE budgets SET spent_amount=spent_amount+?,updated_at=? WHERE id=? AND status='ACTIVE' AND spent_amount+?<=limit_amount",(amount,ts,b["id"],amount))
            if getattr(updated,"rowcount",1)!=1: raise BudgetExceeded("reservation exceeds remaining budget")
            con.execute("INSERT INTO cost_events(id,budget_id,correlation_id,actor,provider,model,purpose,amount,currency,status,metadata,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",(event_id,b["id"],correlation_id,actor,provider,model,purpose,amount,b["currency"],"RESERVED",json.dumps(metadata or {}),ts))
            cur=con.execute("SELECT * FROM cost_events WHERE id=?",(event_id,))
            return self._row_dict(cur,cur.fetchone())

    def settle(self, correlation_id, actual_amount, provider, model, purpose, actor="system", company_id="hds", metadata=None):
        if not correlation_id: raise ValueError("correlation_id is required")
        if not isinstance(actual_amount,(int,float)) or actual_amount < 0: raise ValueError("actual_amount must be a nonnegative number")
        with self.db.transaction() as con:
            cur=con.execute("SELECT * FROM cost_events WHERE correlation_id=?",(correlation_id,))
            row=cur.fetchone()
            if row is None: return self.record(correlation_id,actual_amount,provider,model,purpose,actor,company_id,metadata)
            r=self._row_dict(cur,row)
            if r["status"]!="RESERVED": return r
            delta=float(actual_amount)-float(r["amount"])
            if delta>0:
                updated=con.execute("UPDATE budgets SET spent_amount=spent_amount+?,updated_at=? WHERE id=? AND status='ACTIVE' AND spent_amount+?<=limit_amount",(delta,now(),r["budget_id"],delta))
                if getattr(updated,"rowcount",1)!=1: raise BudgetExceeded("actual cost exceeds remaining budget")
            elif delta<0:
                con.execute("UPDATE budgets SET spent_amount=MAX(0,spent_amount+?),updated_at=? WHERE id=? AND status='ACTIVE'",(delta,now(),r["budget_id"]))
            con.execute("UPDATE cost_events SET amount=?,provider=?,model=?,purpose=?,status='RECORDED',metadata=? WHERE id=? AND status='RESERVED'",(actual_amount,provider,model,purpose,json.dumps(metadata or {}),r["id"]))
            cur=con.execute("SELECT * FROM cost_events WHERE id=?",(r["id"],))
            return self._row_dict(cur,cur.fetchone())

    def release(self, correlation_id, company_id="hds"):
        if not correlation_id: raise ValueError("correlation_id is required")
        with self.db.transaction() as con:
            cur=con.execute("SELECT * FROM cost_events WHERE correlation_id=?",(correlation_id,))
            row=cur.fetchone()
            if row is None: return None
            r=self._row_dict(cur,row)
            if r["status"]!="RESERVED": return r
            con.execute("UPDATE budgets SET spent_amount=MAX(0,spent_amount-?),updated_at=? WHERE id=? AND status='ACTIVE'",(r["amount"],now(),r["budget_id"]))
            con.execute("UPDATE cost_events SET status='RELEASED',metadata=? WHERE id=? AND status='RESERVED'",(json.dumps({"released":True}),r["id"]))
            return self.db.one("SELECT * FROM cost_events WHERE id=?",(r["id"],))

    def set_budget(self, limit_amount, company_id="hds", currency="USD", period="LIFETIME"):
        if limit_amount < 0: raise ValueError("limit_amount cannot be negative")
        existing=self.active_budget(company_id)
        if existing:
            self.db.execute("UPDATE budgets SET limit_amount=?,updated_at=? WHERE id=?",(limit_amount,now(),existing["id"]))
            return self.db.one("SELECT * FROM budgets WHERE id=?",(existing["id"],))
        budget_id=str(uuid4())
        self.db.execute("INSERT INTO budgets(id,company_id,limit_amount,spent_amount,currency,period,status,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?)",
                         (budget_id,company_id,limit_amount,0,currency,period,"ACTIVE",now(),now()))
        return self.db.one("SELECT * FROM budgets WHERE id=?",(budget_id,))
