from app.policy import approval_path

def test_high_value_long_contract_requires_cfo_and_legal():
    roles=[step["role"] for step in approval_path(600_000_000,12)]
    assert roles == ["Budget Owner","Procurement Manager","Finance Manager","CFO","Legal"]
