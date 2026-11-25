"""SMTP delivery checks the server's certificate before sending the password."""


def test_smtp_starttls_verifies_the_certificate(monkeypatch):
    """STARTTLS without a context skips certificate checks, exposing the SMTP password."""
    import ssl

    from app.infrastructure.email import providers

    seen = {}

    class FakeSMTP:
        def __init__(self, host, port, timeout):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def starttls(self, context=None):
            seen["context"] = context

        def login(self, user, password):
            pass

        def send_message(self, message):
            pass

    monkeypatch.setattr(providers.smtplib, "SMTP", FakeSMTP)
    provider = providers.SmtpEmailProvider("smtp.example.com", 587, "a@example.com", "u", "p", use_tls=True)
    provider._send_sync(providers.OutgoingEmail(to="b@example.com", subject="s", text="t", html="<p>t</p>"))
    ctx = seen["context"]
    assert isinstance(ctx, ssl.SSLContext)
    assert ctx.verify_mode == ssl.CERT_REQUIRED and ctx.check_hostname
