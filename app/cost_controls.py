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

    def record(self, correlation_id, amount, provider, model, purpose, actor="system", company_id="hds", metadata=None):
        if not correlation_id: raise ValueError("correlation_id is required")
        if not isinstance(amount, (int, float)): raise ValueError("amount must be numeric")
        if amount < 0: raise ValueError("amount cannot be negative")
        budget=self.active_budget(company_id)
        if not budget: raise BudgetRequired("no active budget")
        with self.db.transaction() as con:
            cur=con.execute("SELECT * FROM cost_events WHERE correlation_id=?",(correlation_id,))
            existing=cur.fetchone()
            if existing:
                return self._row_dict(cur,existing)
            cur=con.execute("SELECT * FROM budgets WHERE id=? AND status='ACTIVE'",(budget["id"],))
            row=cur.fetchone()
            if row is None: raise BudgetRequired("active budget disappeared before cost recording")
            row_dict=self._row_dict(cur,row)
            remaining=float(row_dict["limit_amount"])-float(row_dict["spent_amount"])
            if amount > remaining: raise BudgetExceeded("cost would exceed budget")
            event_id=str(uuid4())
            con.execute("INSERT INTO cost_events(id,budget_id,correlation_id,actor,provider,model,purpose,amount,currency,status,metadata,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                        (event_id,row["id"],correlation_id,actor,provider,model,purpose,amount,row["currency"],"RECORDED",json.dumps(metadata or {}),now()))
            con.execute("UPDATE budgets SET spent_amount=spent_amount+?,updated_at=? WHERE id=?",(amount,now(),row_dict["id"]))
            cur=con.execute("SELECT * FROM cost_events WHERE id=?",(event_id,))
            return self._row_dict(cur,cur.fetchone())

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
