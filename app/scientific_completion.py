"""Scientific completion gate for autonomous projects.

A project cannot be considered scientifically complete merely because its tasks finished.
The gate checks for unresolved evidence/claim issues and explicit validation work.
"""
class ScientificCompletionGate:
    def __init__(self,db):
        self.db=db

    def evaluate(self,project_id):
        project=self.db.one("SELECT id,status,objective FROM projects WHERE id=?",(project_id,))
        if not project: raise ValueError("project not found")
        pending=self.db.one("SELECT COUNT(*) n FROM tasks WHERE project_id=? AND status IN ('PLANNED','ASSIGNED','RUNNING','REVIEW','BLOCKED')",(project_id,))
        unresolved=self.db.one("SELECT COUNT(*) n FROM claims WHERE project_id=? AND status='UNCERTAIN'",(project_id,))
        unreviewed=self.db.one("""SELECT COUNT(*) n FROM evidence e
            JOIN claims c ON c.id=e.claim_id
            WHERE c.project_id=? AND e.id NOT IN (SELECT evidence_id FROM evidence_reviews)""",(project_id,))
        validation=self.db.one("""SELECT COUNT(*) n FROM tasks
            WHERE project_id=? AND (LOWER(title) LIKE '%validation%' OR LOWER(title) LIKE '%experiment%' OR LOWER(title) LIKE '%evidence%')
            AND status='COMPLETED'""",(project_id,))
        blockers=[]
        if int(pending["n"])>0: blockers.append("tasks_pending")
        if int(unresolved["n"])>0: blockers.append("uncertain_claims")
        if int(unreviewed["n"])>0: blockers.append("unreviewed_evidence")
        if int(validation["n"])==0: blockers.append("no_completed_validation_task")
        return {"project_id":project_id,"ready":not blockers,"blockers":blockers,
                "checks":{"pending_tasks":int(pending["n"]),"uncertain_claims":int(unresolved["n"]),"unreviewed_evidence":int(unreviewed["n"]),"completed_validation_tasks":int(validation["n"])}}
