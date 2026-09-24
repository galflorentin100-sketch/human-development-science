from datetime import datetime, timezone, timedelta
from app.database import Database
from app.workflow import ResearchCycle
from app.idempotency import IdempotencyService, IdempotencyConflict
from app.cost_controls import CostControl

def test_idempotency_reclaims_expired_lease(tmp_path):
    db=Database(str(tmp_path/"idem.db")); ResearchCycle(db)
    service=IdempotencyService(db)
    calls=[]
    assert service.run("k","actor","op",lambda:(calls.append(1) or {"ok":1}),lease_minutes=1)["ok"]==1
    assert len(calls)==1
    db.execute("UPDATE idempotency_keys SET status='IN_PROGRESS',response=?,lease_expires_at=? WHERE key=?",('{"status":"IN_PROGRESS"}',(datetime.now(timezone.utc)-timedelta(minutes=2)).isoformat(),"k"))
    result=service.run("k","actor","op",lambda:(calls.append(1) or {"ok":2}),lease_minutes=1)
    assert result=={"ok":2}
    assert len(calls)==2

def test_idempotency_active_lease_blocks_duplicate(tmp_path):
    db=Database(str(tmp_path/"idem_active.db")); ResearchCycle(db)
    service=IdempotencyService(db)
    db.execute("INSERT INTO idempotency_keys(key,actor,operation,response,created_at,expires_at,status,claim_token,lease_expires_at) VALUES (?,?,?,?,?,?,?,?,?)",
               ("k","actor","op",'{"status":"IN_PROGRESS"}',datetime.now(timezone.utc).isoformat(),(datetime.now(timezone.utc)+timedelta(hours=1)).isoformat(),"IN_PROGRESS","token",(datetime.now(timezone.utc)+timedelta(minutes=5)).isoformat()))
    try:
        service.run("k","actor","op",lambda:{"ok":1})
        assert False
    except IdempotencyConflict:
        pass

def test_stale_cost_reservation_is_released(tmp_path):
    db=Database(str(tmp_path/"cost.db")); ResearchCycle(db)
    costs=CostControl(db); budget=costs.set_budget(10)
    costs.reserve("corr",4,actor="agent")
    stale=(datetime.now(timezone.utc)-timedelta(hours=2)).isoformat()
    db.execute("UPDATE cost_events SET created_at=? WHERE correlation_id=?",(stale,"corr"))
    released=costs.release_stale_reservations(max_age_minutes=60)
    assert released==["corr"]
    assert db.one("SELECT status FROM cost_events WHERE correlation_id=?",("corr",))["status"]=="RELEASED"
    assert float(db.one("SELECT spent_amount FROM budgets WHERE id=?",(budget["id"],))["spent_amount"])==0.0
