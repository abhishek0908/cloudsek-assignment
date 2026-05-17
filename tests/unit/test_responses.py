from pydantic import BaseModel
from app.core.responses import success_response, error_response


def test_success_response_defaults():
    resp = success_response()
    body = resp.body.decode()

    assert resp.status_code == 200
    assert '"success":true' in body
    assert '"message":"Request successful"' in body


def test_success_response_with_dict_data():
    resp = success_response(message="done", data={"key": "val"}, status_code=201)
    body = resp.body.decode()

    assert resp.status_code == 201
    assert '"success":true' in body
    assert '"key":"val"' in body


def test_success_response_dumps_base_model():
    class Dummy(BaseModel):
        x: str

    resp = success_response(data=Dummy(x="hello"))
    body = resp.body.decode()

    assert '"x":"hello"' in body


def test_error_response_minimal():
    resp = error_response(error_code="NOT_FOUND", message="Missing")
    body = resp.body.decode()

    assert resp.status_code == 400
    assert '"success":false' in body
    assert '"code":"NOT_FOUND"' in body


def test_error_response_with_details():
    resp = error_response(
        error_code="VALIDATION_ERROR",
        message="Bad input",
        status_code=422,
        details=[{"field": "url", "msg": "required"}],
    )
    body = resp.body.decode()

    assert resp.status_code == 422
    assert '"field":"url"' in body
    assert '"msg":"required"' in body


def test_success_response_with_meta():
    resp = success_response(meta={"page": 1, "total": 10})
    body = resp.body.decode()

    assert '"meta"' in body
    assert '"page":1' in body
