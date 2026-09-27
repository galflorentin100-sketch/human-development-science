from app.observability import request_id

def test_request_id_is_stable_when_supplied():
    assert request_id("abc") == "abc"

def test_request_id_generates_value():
    value=request_id()
    assert isinstance(value,str) and len(value)>10
