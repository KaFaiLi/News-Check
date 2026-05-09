from src.anti_blocking.block_detector import (
    BlockType,
    classify_exception,
    classify_response,
    classify_status,
    classify_text,
)


def test_2xx_is_not_a_block():
    c = classify_status(200)
    assert c.type is BlockType.NONE
    assert not c.retryable


def test_429_is_retryable_and_rotates_ua():
    c = classify_status(429)
    assert c.type is BlockType.RATE_LIMIT
    assert c.retryable
    assert c.rotate_user_agent


def test_403_is_retryable_and_rotates_ua():
    c = classify_status(403)
    assert c.type is BlockType.FORBIDDEN
    assert c.rotate_user_agent


def test_5xx_is_retryable_no_rotation():
    c = classify_status(503)
    assert c.type is BlockType.SERVER_ERROR
    assert c.retryable
    assert not c.rotate_user_agent


def test_404_is_not_retryable():
    c = classify_status(404)
    assert not c.retryable


def test_captcha_marker_classified_as_captcha():
    body = "<html>Please verify you are human and complete this CAPTCHA.</html>"
    c = classify_text(body)
    assert c.type is BlockType.CAPTCHA
    assert not c.retryable


def test_empty_body_classified_as_empty():
    c = classify_text("")
    assert c.type is BlockType.EMPTY_BODY
    assert c.retryable


def test_status_dominates_when_set():
    # A successful 200 with no captcha → NONE
    c = classify_response(200, "<html>Hello world</html>")
    assert c.type is BlockType.NONE

    # 429 always wins, regardless of body
    c = classify_response(429, "<html>Hello world</html>")
    assert c.type is BlockType.RATE_LIMIT


def test_classify_exception_timeout():
    class FakeTimeout(Exception):
        pass

    FakeTimeout.__name__ = "PlaywrightTimeoutError"
    c = classify_exception(FakeTimeout("nav timeout"))
    assert c.type is BlockType.TIMEOUT
    assert c.retryable
