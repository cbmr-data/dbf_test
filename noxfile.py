import nox

nox.options.sessions = [
    "style",
    "lints",
    "typing",
]


SOURCES = (
    "noxfile.py",
    "dbf_test",
    "typings",
)


class Requirements:
    NOX = "nox~=2023.4.22"
    PYRIGHT = "pyright==1.1.358"
    RUFF = "ruff==0.3.5"


@nox.session
def style(session: nox.Session) -> None:
    session.install(Requirements.RUFF)
    # Replaces `black --check`
    session.run("ruff", "format", "--check", *SOURCES)
    # Replaces `isort --check-only`
    session.run("ruff", "check", "--select", "I", *SOURCES)


@nox.session
def lints(session: nox.Session) -> None:
    session.install(Requirements.RUFF)
    session.run("ruff", "check", *SOURCES)


@nox.session()
def typing(session: nox.Session) -> None:
    session.install("-e", ".")
    session.install(Requirements.NOX)
    session.install(Requirements.PYRIGHT)
    session.run("pyright", *SOURCES)
