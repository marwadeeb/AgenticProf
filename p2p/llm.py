"""Subprocess entry point: execute the generated JavaScript inside QuickJS and print a JSON report.
Runs in its own process so runaway code can be killed by a timeout without affecting the agent."""
import json
import sys


def _emit(obj) -> None:
    data = obj if isinstance(obj, str) else json.dumps(obj)
    sys.stdout.buffer.write(data.encode("utf-8"))
    sys.stdout.flush()


def main() -> int:
    with open(sys.argv[1], encoding="utf-8") as fh:
        data = json.load(fh)
    try:
        import quickjs
    except Exception as exc:  # engine not installed on this platform
        _emit({"engine": None, "error": "quickjs not importable: " + str(exc)})
        return 0
    ctx = quickjs.Context()
    for setter, val in (("set_time_limit", int(data.get("time_limit", 20))),
                        ("set_memory_limit", 512 * 1024 * 1024),
                        ("set_max_stack_size", 8 * 1024 * 1024)):
        try:
            getattr(ctx, setter)(val)
        except Exception:
            pass
    try:
        ctx.eval(data["lib"])
        ctx.eval(data["harness"])
    except Exception as exc:
        _emit({"engine": "quickjs", "run_error": "internal library failed to load: " + str(exc)})
        return 0
    try:
        ctx.eval(data["wrapped"])
    except Exception as exc:
        _emit({"engine": "quickjs", "load_error": str(exc)})
        return 0
    try:
        out = ctx.eval("__hRun(" + json.dumps(json.dumps(data["cfg"])) + ")")
    except Exception as exc:
        _emit({"engine": "quickjs", "run_error": str(exc)})
        return 0
    _emit(out if isinstance(out, str) else {"engine": "quickjs", "run_error": "checker returned a non-string"})
    return 0


if __name__ == "__main__":
    sys.exit(main())
