"""Simple password-based auth routes."""

from fasthtml.common import *
from starlette.responses import RedirectResponse
from pdf_utils.config import LOGIN_PASSWORD


def setup_routes(app, rt):

    @rt('/login')
    def get(sess):
        error = sess.pop('login_error', None)
        return (
            Title("Sign in — PDF Utils"),
            Main(
                Div(
                    H2("PDF Utils", cls="login-title"),
                    P("Enter your password to continue.", cls="login-sub"),
                    Form(
                        Div(
                            Input(
                                type="password", name="password",
                                placeholder="Password", autofocus=True,
                                cls="login-input",
                            ),
                            cls="login-field",
                        ),
                        P(error, cls="login-error") if error else None,
                        Button("Sign in", type="submit", cls="login-btn"),
                        method="post", action="/login",
                        cls="login-form",
                    ),
                    cls="login-card",
                ),
                cls="login-page",
            ),
        )

    @rt('/login')
    def post(password: str, sess):
        if password == LOGIN_PASSWORD:
            sess['authenticated'] = True
            return RedirectResponse('/', status_code=303)
        sess['login_error'] = 'Incorrect password. Try again.'
        return RedirectResponse('/login', status_code=303)

    @rt('/logout')
    def logout(sess):
        sess.clear()
        return RedirectResponse('/login', status_code=303)
