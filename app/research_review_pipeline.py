from app.tasks import TaskEngine

class ResearchReviewPipeline:
    def __init__(self, db):
        self.db=db
        self.tasks=TaskEngine(db)
