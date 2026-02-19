"""
Simple Meta Script CLI — starter interpreter (subset)
Supports: say, let, basic math, comments (#), python-style syntax.
Not production secure — use sandboxing for real execution.
"""

import argparse
import ast
import sys
import json
import re

# readline isn't available by default on Windows; import safely
try:
    import readline  # optional, improves REPL UX on UNIX-like systems
except Exception:
    readline = None

from metascript.agents import frontend_agent, backend_agent

GLOBAL_ENV = {}
# Toggle used by the CLI to enable/disable the agent-first handshake
AGENTS_ENABLED = True
# Autonomy flag: when true agents may exercise tool use and act without user prompts
# Default autonomy: true (system may act autonomously by default). Persisted config can override.
# The running process will load persisted config when available.
AUTONOMY_ENABLED = True


def _parse_agent_payload(raw: str):
    """Parse a payload written with either bracket display or curly JSON.
    Example accepted forms (both allowed):
      [ "intent": "explain", "code": "say \"Hi\"" ]
      {"intent": "explain", "code": "say \"Hi\""}
    The display form (square brackets) is converted to JSON-like braces.
    Returns a Python dict or raises ValueError on parse failure.
    """
    raw = raw.strip()
    if raw.startswith('[') and raw.endswith(']'):
        # convert outer brackets to braces so json.loads works
        raw = '{' + raw[1:-1] + '}'
    # Ensure keys are quoted (spec examples already quote keys)
    try:
        return json.loads(raw)
    except Exception:
        # tolerate unescaped backslashes (common on Windows paths in examples):
        if "\\" in raw:
            try:
                raw2 = raw.replace("\\", "\\\\")
                return json.loads(raw2)
            except Exception as e:
                raise ValueError(f"invalid agent payload after backslash-escape: {e}")
        raise ValueError("invalid agent payload")


def transform_ms_to_python(source: str) -> str:
    """Transpile Meta Script source to Python using the AST pipeline.

    Steps:
    1. Parse to AST
    2. Expand compile-time macros (hygienic + scoped)
    3. Transpile AST to Python (via `transpiler_py`)

    This ensures macros are honored for the Python target as well.
    """
    try:
        from metascript import parser, macros, transpiler_py
    except Exception:
        # fall back to the legacy line-based transpiler if AST path isn't available
        # (keeps CLI usable in minimal environments)
        lines = []
        for raw in source.splitlines():
            indent = raw[: len(raw) - len(raw.lstrip(" \t"))]
            line = raw.strip()
            if not line or line.startswith('#'):
                lines.append(raw)
                continue
            if line.startswith('say '):
                rest = line[4:]
                lines.append(indent + 'print(' + rest + ')')
                continue
            if line.startswith('let '):
                lines.append(indent + line[4:])
                continue
            lines.append(indent + line)
        return '\n'.join(lines)

    prog = parser.parse(source)
    prog = macros.expand_macros(prog)
    py = transpiler_py.transpile(prog)
    return py

def run_ms_source(source: str, env=None, run_with_agents: bool | None = None, run_autonomy: bool | None = None):
    """Run Meta Script source with an optional agent-first handshake.

    - If run_with_agents is None the global AGENTS_ENABLED is used.
    - If run_autonomy is None the global AUTONOMY_ENABLED is used.
    - The frontend agent provides a kid-friendly explanation (printed).
    - The backend agent validates/sandboxes and may reject execution.
    """
    env = {} if env is None else env
    if run_with_agents is None:
        run_with_agents = AGENTS_ENABLED
    if run_autonomy is None:
        run_autonomy = globals().get('AUTONOMY_ENABLED', False)

    if run_with_agents:
        try:
            fe = frontend_agent.handle_message({"type": "explain", "payload": {"code": source}})
            explanation = fe.get("payload", {}).get("explanation") if isinstance(fe, dict) else None
            if explanation:
                print(f"[frontend agent] {explanation}")
        except Exception:
            # agent errors do not block execution by default
            print("[frontend agent] (error producing explanation)")

        bv = backend_agent.validate_execution(source)
        if not bv.get("approved"):
            print(f"[backend agent] Execution rejected: {bv.get('reason')}")
            print("Tip: use `--no-agent` to bypass (unsafe)")
            return env

    # expose autonomy flag to the runtime environment so generated code can check it
    runtime_env = env
    runtime_env['AUTONOMY_ENABLED'] = bool(run_autonomy)

    py = transform_ms_to_python(source)
    # NOTE: executing code directly — replace with a secure sandbox for production
    exec(compile(py, '<metascript>', 'exec'), runtime_env)
    return runtime_env


def repl():
    print('Meta Script REPL — type "exit" or Ctrl-D to quit')
    buffer = []
    try:
        while True:
            line = input('ms> ')
            if line.strip() in ('exit', 'quit'):
                break
            if line.strip() == '':
                source = '\n'.join(buffer)
                if source.strip():
                    run_ms_source(source, GLOBAL_ENV)
                buffer = []
                continue
            buffer.append(line)
    except (EOFError, KeyboardInterrupt):
        print('\nbye')


def main():
    global AGENTS_ENABLED
    parser = argparse.ArgumentParser(prog='metascript')
    parser.add_argument('--no-agent', dest='no_agent', action='store_true', help='Bypass agent-first handshake (unsafe)')
    parser.add_argument('--autonomy', dest='autonomy', action='store_true', help='Allow agents to act autonomously (use with caution)')
    sub = parser.add_subparsers(dest='cmd')
    runp = sub.add_parser('run')
    runp.add_argument('file')
    sub.add_parser('repl')

    # compile: show compiled output or expanded macros
    compilep = sub.add_parser('compile')
    compilep.add_argument('file')
    compilep.add_argument('--expand-macros', dest='expand_macros', action='store_true', help='Print macro-expanded Meta Script source')
    compilep.add_argument('--to-python', dest='to_python', action='store_true', help='Emit transpiled Python code (after macro expansion)')

    config = sub.add_parser('config')
    cfg_sub = config.add_subparsers(dest='cfg_cmd')
    cfg_set = cfg_sub.add_parser('set')
    cfg_set.add_argument('key')
    cfg_set.add_argument('value')
    cfg_get = cfg_sub.add_parser('get')
    cfg_get.add_argument('key')

    probe = sub.add_parser('probe')
    probe.add_argument('--save', dest='save', action='store_true', help='Persist discovered model URL to metascript_config.json')
    probe.add_argument('--start', dest='start', action='store_true', help='Start a local vLLM server if none is running (requires vllm installed)')

    autotune = sub.add_parser('autotune')
    autotune.add_argument('--save', dest='save', action='store_true', help='Persist selected model adapter')
    autotune.add_argument('--enable-autonomy', dest='enable_autonomy', action='store_true', help='Enable autonomy if autotune succeeds')
    autotune.add_argument('--runs', dest='runs', type=int, default=2, help='Number of sample runs per adapter')
    args = parser.parse_args()

    AGENTS_ENABLED = not getattr(args, 'no_agent', False)
    # autonomy flag set explicitly by user; requires agents enabled
    globals()['AUTONOMY_ENABLED'] = bool(getattr(args, 'autonomy', False)) and AGENTS_ENABLED

    if args.cmd == 'run':
        with open(args.file, 'r', encoding='utf-8') as f:
            src = f.read()
        run_ms_source(src, GLOBAL_ENV, run_autonomy=globals().get('AUTONOMY_ENABLED', False))

    elif args.cmd == 'config':
        # config set/get persisted metascript_config.json values
        try:
            from metascript.agents.discovery import load_config, save_config
        except Exception:
            print('config support not available')
            return
        if args.cfg_cmd == 'set':
            cfg = load_config()
            cfg[args.key] = args.value
            save_config(cfg)
            print(f"Saved {args.key}")
        elif args.cfg_cmd == 'get':
            cfg = load_config()
            print(cfg.get(args.key))
        else:
            print('config commands: set <key> <value> | get <key>')

    elif args.cmd == 'probe':
        # probe local hosts for a vllm-like server
        try:
            from metascript.agents.discovery import probe_vllm_hosts, configure_vllm, start_vllm_if_missing
        except Exception:
            print('discovery support not available')
            return
        url = probe_vllm_hosts()
        if not url:
            # optionally start vllm if requested
            if getattr(args, 'start', False):
                url = start_vllm_if_missing()
            if not url:
                print('No local vllm-like model detected')
                return
        print('Detected local model at:', url)
        if getattr(args, 'save', False):
            configure_vllm(url, persist=True)
            print('Saved to metascript_config.json')

    elif args.cmd == 'autotune':
        try:
            from metascript.agents.frontend_agent import run_autotune
            from metascript.agents.discovery import load_config, save_config
        except Exception:
            print('autotune support not available')
            return
        selected, results = run_autotune(runs=args.runs, persist=bool(getattr(args, 'save', False)))
        print(f"Selected adapter: {selected.__class__.__name__}")
        if getattr(args, 'enable_autonomy', False):
            cfg = load_config()
            cfg['autonomy_enabled'] = True
            save_config(cfg)
            print('Autonomy enabled and persisted')

    elif args.cmd == 'compile':
        try:
            from metascript import parser, macros, unparse, transpiler_py
        except Exception:
            print('compile support not available')
            return
        with open(args.file, 'r', encoding='utf-8') as f:
            src = f.read()
        prog = parser.parse(src)
        expanded = macros.expand_macros(prog)
        if getattr(args, 'expand_macros', False):
            print(unparse.unparse(expanded))
            return
        if getattr(args, 'to_python', False):
            print(transpiler_py.transpile(expanded))
            return
        # default: print expanded MS source
        print(unparse.unparse(expanded))

    else:
        repl()


if __name__ == '__main__':
    main()
