"""Small, bounded rate limiter.

This is a safety backstop, not a distributed production limiter. Deployments with
multiple API replicas should enforce the same policy at the gateway/Redis layer.
"""
from collections import deque
from threading import Lock
from time import monotonic

class RateLimiter:
    def __init__(self, limit=120, window_seconds=60):
        self.limit=limit; self.window_seconds=window_seconds
        self._events={}; self._lock=Lock()

    def allow(self,key,limit=None):
        limit=limit or self.limit
        now=monotonic()
        with self._lock:
            q=self._events.setdefault(key,deque())
            cutoff=now-self.window_seconds
            while q and q[0] <= cutoff: q.popleft()
            if len(q)>=limit: return False
            q.append(now)
            if len(self._events)>10000:
                self._events={k:v for k,v in self._events.items() if v and v[-1]>cutoff}
            return True
