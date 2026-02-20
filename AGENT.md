# Agent Guidelines

This document defines the development conventions and best practices for this repository. Follow these instructions precisely when writing, reviewing, or modifying code.

---

## Environment Setup

- **Virtual environment:** Always activate with `source tube/bin/activate`. Do not use `.venv` directly — it contains Zvec, which only runs inside the Linux Docker container.
- **Dependency installation:** Always ask the user to install new dependencies. Do not run `uv pip install` autonomously, as Zvec will cause it to fail on the host machine.
- **Zvec on macOS:** Zvec does not install on Darwin x86_64. Before running any Zvec-dependent tests, verify the Docker container is active:
  ```bash
  docker ps | grep 'jovial_keldysh'
  ```
  If active, run tests via `make docker-test` instead of locally.

---

## Code Quality Checks

Always run the following before considering any task complete — including after small changes:

```bash
ruff format ./
ruff check ./
pytest -vv
```

Never skip `pytest -vv`. If tests fail, fix the issue before moving on.

---

## Python Best Practices

- **Top-level imports only.** All imports belong at the top of the file. Inline imports inside functions are permitted only for deferred loading of expensive or optional dependencies (e.g. inside an `async` handler to avoid circular imports).
- **Prefer `pathlib.Path` over `os.path`** for all filesystem operations — it is more readable and composable.
- **Use type annotations on all function signatures,** including return types. Rely on `Optional[X]` or `X | None` for nullable values and avoid bare `Any` where possible.
- **Keep functions small and single-purpose.** If a function needs a long docstring to explain what it does, consider whether it should be split.
- **Avoid mutable default arguments.** Never use `def f(items=[])` — use `def f(items=None)` and assign the default inside the body.
- **Use dataclasses or Pydantic models** for structured data instead of plain dicts. This makes intent clear and enables validation.
- **Guard module-level side effects** with `if __name__ == "__main__":` to prevent unintended execution on import.
- **Prefer `asyncio.gather` over sequential `await`** when running independent coroutines — it is faster and expresses parallelism clearly.
- **Use `__repr__` on all domain classes.** It makes debugging and logging significantly easier. Only add `__str__` if there is a distinct user-facing representation.
- **Scope semaphores and shared concurrency primitives** as narrowly as possible — guard only the I/O call itself, not the surrounding logic.
- **Prefer structured logging over print statements.** Use `logging.getLogger(__name__)` in every module and configure handlers once at the application entry point.
- **Avoid bare `except` clauses.** Always catch a specific exception type. Use `except Exception as e` at minimum, and log or re-raise with context.
- **Lines of Code.** Keep the code in newly created files within 300 lines of code. If there must be more code, use a new adjacent file, and group logically related files.