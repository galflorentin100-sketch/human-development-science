"""Scientific completion gate for autonomous projects.

A project cannot be considered scientifically complete merely because its tasks finished.
The gate checks for unresolved evidence/claim issues and explicit validation work.
"""
class ScientificCompletionGate:
    def __init__(self,db):
        self.db=db

    def check(self,project_id):
        return self.evaluate(project_id)

    def evaluate(self,project_id):
        project=self.db.one("SELECT id,status,objective FROM projects WHERE id=?",(project_id,))
        if not project: raise ValueError("project not found")
        pending=self.db.one("SELECT COUNT(*) n FROM tasks WHERE project_id=? AND status IN ('PLANNED','ASSIGNED','RUNNING','REVIEW','BLOCKED')",(project_id,))
        unresolved=self.db.one("SELECT COUNT(*) n FROM claims WHERE project_id=? AND status='UNCERTAIN'",(project_id,))
        unreviewed=self.db.one("""SELECT COUNT(*) n FROM evidence e
            JOIN claims c ON c.id=e.claim_id
            WHERE c.project_id=? AND e.id NOT IN (SELECT evidence_id FROM evidence_reviews)""",(project_id,))
        knowledge_conflicts=self.db.one("""SELECT COUNT(*) n FROM claims c
            WHERE c.project_id=? AND c.status IN ('SUPPORTED','CONTRADICTED')
              AND EXISTS (
                  SELECT 1 FROM evidence e
                  WHERE e.claim_id=c.id
                    AND e.id IN (
                        SELECT er.evidence_id FROM evidence_reviews er
                        GROUP BY er.evidence_id
                        HAVING SUM(CASE WHEN er.verdict='VERIFIED' THEN 1 ELSE 0 END)>0
                           AND SUM(CASE WHEN er.verdict='REJECTED' THEN 1 ELSE 0 END)>0
                    )
              )""",(project_id,))
        stale_knowledge=self.db.one("""SELECT COUNT(*) n
            FROM knowledge_freshness kf
            JOIN (
                SELECT 'CLAIM' AS entity_type,id,project_id FROM claims
                UNION ALL SELECT 'INTERVENTION',id,project_id FROM interventions
                UNION ALL SELECT 'TRAINING_PROTOCOL',id,project_id FROM training_protocols
            ) e ON e.entity_type=kf.entity_type AND e.id=kf.entity_id
            WHERE e.project_id=? AND kf.status='REVIEW_REQUIRED'""",(project_id,))
        validation=self.db.one("""SELECT COUNT(*) n FROM (
            SELECT e.id
            FROM hds_experiments e
            JOIN hds_experiment_results r ON r.experiment_id=e.id
            WHERE e.project_id=? AND e.status='COMPLETED'
            UNION ALL
            SELECT s.id
            FROM research_syntheses s
            JOIN research_workspaces w ON w.id=s.workspace_id
            WHERE w.project_id=? AND s.status='ACCEPTED' AND w.status='REVIEWED'
        ) validated""",(project_id,project_id))
        blockers=[]
        if int(pending["n"])>0: blockers.append("tasks_pending")
        if int(unresolved["n"])>0: blockers.append("uncertain_claims")
        if int(unreviewed["n"])>0: blockers.append("unreviewed_evidence")
        if int(knowledge_conflicts["n"])>0: blockers.append("conflicted_knowledge_evidence")
        if int(stale_knowledge["n"])>0: blockers.append("stale_knowledge_requires_review")
        if int(validation["n"])==0: blockers.append("no_structured_scientific_validation")
        return {"project_id":project_id,"ready":not blockers,"blockers":blockers,
                "checks":{"pending_tasks":int(pending["n"]),"uncertain_claims":int(unresolved["n"]),"unreviewed_evidence":int(unreviewed["n"]),"completed_validation_work":int(validation["n"]),
                    "conflicted_knowledge_evidence":int(knowledge_conflicts["n"]),
                    "stale_knowledge_requires_review":int(stale_knowledge["n"])}}
