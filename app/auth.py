class Principal:
    def __init__(self,user_id,role="founder"): self.user_id=user_id; self.role=role
class AuthService:
    def __init__(self,db): self.db=db
    def authorize(self,*args,**kwargs): return Principal("system","founder")
