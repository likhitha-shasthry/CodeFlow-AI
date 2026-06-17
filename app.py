import ast
import contextlib
import io
import itertools
import re
import textwrap
import time
import traceback
from typing import Any

import streamlit as st


st.set_page_config(
    page_title="CodeFlow AI",
    page_icon="CF",
    layout="wide",
    initial_sidebar_state="expanded",
)


CUSTOM_CSS = """
<style>
    :root {
        --bg: #f6efe5;
        --panel: rgba(255, 250, 244, 0.94);
        --panel-strong: #fffaf3;
        --ink: #1b1a17;
        --muted: #5d554c;
        --accent: #d55d3f;
        --accent-2: #1f6b5d;
        --danger: #8b2f2f;
        --line: rgba(27, 26, 23, 0.08);
        --shadow: 0 24px 60px rgba(76, 45, 22, 0.12);
    }

    .stApp {
        background:
            radial-gradient(circle at top left, rgba(213, 93, 63, 0.15), transparent 32%),
            radial-gradient(circle at top right, rgba(31, 107, 93, 0.18), transparent 28%),
            linear-gradient(180deg, #fbf5ec 0%, var(--bg) 48%, #efe2d1 100%);
        color: var(--ink);
    }

    .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
        max-width: 1200px;
    }

    .hero-title {
        font-size: 2.7rem;
        font-weight: 800;
        margin-bottom: 1rem;
    }

    .section-card {
        background: var(--panel);
        border: 1px solid var(--line);
        border-radius: 22px;
        padding: 1rem 1.1rem;
        box-shadow: var(--shadow);
    }

    .step-card {
        background: var(--panel-strong);
        border-left: 5px solid var(--accent);
        border-radius: 16px;
        padding: 1rem;
        margin-bottom: 0.85rem;
        box-shadow: 0 12px 30px rgba(76, 45, 22, 0.08);
    }

    .step-card.error {
        border-left-color: var(--danger);
    }

    .step-title {
        font-weight: 700;
        margin-bottom: 0.35rem;
    }

    .step-copy {
        color: var(--ink);
        line-height: 1.65;
    }

    .muted {
        color: var(--muted);
    }

    .pill {
        display: inline-block;
        padding: 0.28rem 0.62rem;
        margin-right: 0.45rem;
        border-radius: 999px;
        font-size: 0.8rem;
        font-weight: 700;
        color: #fff;
    }

    .pill-warm { background: var(--accent); }
    .pill-cool { background: var(--accent-2); }
    .pill-dark { background: #39322b; }
    .pill-danger { background: var(--danger); }

    .callout {
        background: rgba(213, 93, 63, 0.08);
        border: 1px solid rgba(213, 93, 63, 0.16);
        border-radius: 16px;
        padding: 1rem;
    }

    .agent-grid {
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: 0.8rem;
    }

    .agent-card {
        background: var(--panel-strong);
        border: 1px solid var(--line);
        border-radius: 18px;
        padding: 0.95rem;
    }

    .agent-card strong {
        display: block;
        margin-bottom: 0.35rem;
    }

    .table-card {
        background: var(--panel);
        border: 1px solid var(--line);
        border-radius: 20px;
        padding: 1rem;
        box-shadow: var(--shadow);
    }

    .code-panel {
        background: #1f1d1a;
        color: #f7f0e8;
        border-radius: 22px;
        padding: 1rem;
        box-shadow: var(--shadow);
    }

    .code-line {
        font-family: "Consolas", "Courier New", monospace;
        white-space: pre-wrap;
        padding: 0.35rem 0.55rem;
        border-radius: 12px;
        margin-bottom: 0.2rem;
        transition: all 0.25s ease;
    }

    .code-line.active {
        background: rgba(213, 93, 63, 0.28);
        border-left: 4px solid #ffb38e;
        transform: translateX(2px);
    }

    .memory-card {
        background: var(--panel);
        border: 1px solid var(--line);
        border-radius: 18px;
        padding: 0.9rem 1rem;
        margin-bottom: 0.7rem;
        box-shadow: var(--shadow);
        transition: transform 0.2s ease, background 0.2s ease;
    }

    .memory-name {
        color: var(--muted);
        font-size: 0.82rem;
        text-transform: uppercase;
        letter-spacing: 0.06em;
    }

    .memory-value {
        font-family: "Consolas", "Courier New", monospace;
        font-size: 1.1rem;
        font-weight: 700;
        margin-top: 0.25rem;
    }

    .status-card {
        background: linear-gradient(135deg, rgba(255,250,244,0.98), rgba(250,239,228,0.95));
        border: 1px solid var(--line);
        border-radius: 20px;
        padding: 1rem;
        box-shadow: var(--shadow);
    }

    .control-hint {
        color: var(--muted);
        font-size: 0.92rem;
    }
</style>
"""


def inject_styles() -> None:
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


def format_value(value: Any) -> str:
    allowed = (int, float, str, bool, list, tuple, dict, set, type(None))
    if isinstance(value, allowed):
        rendered = repr(value)
        return rendered if len(rendered) <= 120 else rendered[:117] + "..."
    return f"<{type(value).__name__}>"


def collect_visible_locals(frame_locals: dict[str, Any]) -> dict[str, str]:
    visible: dict[str, str] = {}
    for key, value in frame_locals.items():
        if key.startswith("__"):
            continue
        visible[key] = format_value(value)
    return visible


def detect_assignment_targets(code_line: str) -> list[str]:
    if "=" not in code_line or "==" in code_line or code_line.strip().startswith(("if ", "while ")):
        return []
    left = code_line.split("=", 1)[0]
    pieces = [piece.strip() for piece in left.split(",")]
    valid_names = []
    for piece in pieces:
        if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", piece):
            valid_names.append(piece)
    return valid_names


def explain_code_line(code_line: str) -> str:
    stripped = code_line.strip()
    if not stripped:
        return "This line is blank, so it does not change the program state."
    if stripped.startswith("for "):
        return "This line starts a loop, so Python will repeat the block for each value in the sequence."
    if stripped.startswith("while "):
        return "This line starts a loop that will keep running while the condition stays true."
    if stripped.startswith("if "):
        return "This line checks a condition and decides whether the indented block should run."
    if stripped.startswith("elif "):
        return "This line checks another condition after a previous branch was skipped."
    if stripped.startswith("else"):
        return "This branch runs only when the earlier condition checks did not match."
    if stripped.startswith("def "):
        return "This line defines a function. Python stores the function so it can be called later."
    if stripped.startswith("return "):
        return "This line sends a value back from the current function and ends that function call."
    if stripped.startswith("print("):
        return "This line sends output to the console."
    if stripped.startswith("import ") or stripped.startswith("from "):
        return "This line loads code from another module so the program can use it."
    if "=" in stripped and "==" not in stripped:
        return "This line computes a value and stores it in one or more variables."
    return "This line continues the program logic and may update the current state."


def describe_state_change(previous: dict[str, str], current: dict[str, str], code_line: str) -> str:
    targets = detect_assignment_targets(code_line)
    changes = []

    for name, value in current.items():
        if name not in previous:
            changes.append(f"`{name}` appears with value {value}.")
        elif previous[name] != value:
            changes.append(f"`{name}` changes from {previous[name]} to {value}.")

    removed = [name for name in previous if name not in current]
    for name in removed:
        changes.append(f"`{name}` is no longer visible in this scope.")

    if changes:
        return " ".join(changes)

    if targets:
        joined = ", ".join(f"`{name}`" for name in targets)
        return f"The tracked variables stay the same at this checkpoint, but this line is working with {joined}."

    if current:
        snapshot = ", ".join(f"`{key}` = {value}" for key, value in current.items())
        return f"The visible state at this point is {snapshot}."

    return "No user-defined variables are visible yet at this point in execution."


def build_story(steps: list[dict[str, Any]], status: str, error: dict[str, Any] | None) -> list[dict[str, Any]]:
    story: list[dict[str, Any]] = []
    previous_locals: dict[str, str] = {}

    for index, step in enumerate(steps, start=1):
        code_line = step["code"]
        current_locals = step["locals"]
        explanation = explain_code_line(code_line)
        state_note = describe_state_change(previous_locals, current_locals, code_line)
        card_kind = "error" if error and step["line"] == error.get("line") and status == "runtime_error" else "normal"
        story.append(
            {
                "step_number": index,
                "line": step["line"],
                "code": code_line,
                "summary": explanation,
                "state_note": state_note,
                "locals": current_locals,
                "kind": card_kind,
            }
        )
        previous_locals = current_locals

    return story


def detect_goal(code: str, steps: list[dict[str, Any]], error: dict[str, Any] | None) -> str:
    lowered = code.lower()
    if error:
        return "Explain the failure point and why execution cannot continue."
    if "for " in lowered or "while " in lowered:
        return "Help the learner follow repeated state changes across iterations."
    if "def " in lowered:
        return "Show how control moves through functions and returns values."
    if any("if " in line["code"] for line in steps):
        return "Show how conditions guide the execution path."
    return "Explain how values move through the program from start to finish."


def choose_visualization_mode(code: str, steps: list[dict[str, Any]], error: dict[str, Any] | None) -> str:
    loop_lines = sum(1 for step in steps if step["code"].strip().startswith(("for ", "while ")))
    has_function = "def " in code
    has_condition = any(step["code"].strip().startswith(("if ", "elif ", "else")) for step in steps)

    if error:
        return "Error Focus View"
    if loop_lines >= 2 or len(steps) >= 6:
        return "State Table View"
    if has_function:
        return "Function Story View"
    if has_condition:
        return "Decision Path View"
    return "Timeline View"


def summarize_utility_choice(mode: str) -> str:
    reasons = {
        "Error Focus View": "Utility-based reasoning prioritizes the failing region because that gives the learner the most useful insight quickly.",
        "State Table View": "Utility-based reasoning chooses a compact table here because repeated steps are easier to understand when state changes are grouped.",
        "Function Story View": "Utility-based reasoning keeps the walkthrough narrative-focused so function definition, call, and return flow are easier to follow.",
        "Decision Path View": "Utility-based reasoning emphasizes the chosen branch so the learner sees why one path ran and the others did not.",
        "Timeline View": "Utility-based reasoning keeps the default timeline because a simple sequential story is the clearest explanation.",
    }
    return reasons[mode]


def build_agent_profile(code: str, steps: list[dict[str, Any]], error: dict[str, Any] | None) -> dict[str, str]:
    visible_variables = sorted({name for step in steps for name in step["locals"]})
    tracked = ", ".join(f"`{name}`" for name in visible_variables[:6]) or "no user variables yet"
    goal = detect_goal(code, steps, error)
    visualization = choose_visualization_mode(code, steps, error)

    return {
        "reflex": (
            "Simple reflex rules detect patterns such as loops, assignments, conditions, prints, and errors "
            "to decide the immediate explanation for each line."
        ),
        "model": (
            f"Model-based behavior remembers the current program state across steps. Right now the explainer is tracking {tracked}."
        ),
        "goal": goal,
        "utility": summarize_utility_choice(visualization),
        "visualization": visualization,
    }


def build_state_rows(story: list[dict[str, Any]]) -> list[dict[str, str]]:
    all_keys = []
    for item in story:
        for key in item["locals"]:
            if key not in all_keys:
                all_keys.append(key)

    rows = []
    for item in story:
        row = {
            "Step": str(item["step_number"]),
            "Line": str(item["line"]),
            "Code": item["code"],
        }
        for key in all_keys:
            row[key] = item["locals"].get(key, "-")
        rows.append(row)
    return rows


def build_input_provider() -> tuple[callable, list[dict[str, str]]]:
    assumed_values = itertools.cycle(["3", "5", "7", "2", "9", "hello"])
    consumed_inputs: list[dict[str, str]] = []

    def fake_input(prompt: str = "") -> str:
        value = next(assumed_values)
        consumed_inputs.append(
            {
                "prompt": prompt.strip() or "input()",
                "value": value,
            }
        )
        return value

    return fake_input, consumed_inputs


def reset_playback_state(story_length: int) -> None:
    st.session_state.current_step = 0
    st.session_state.story_length = story_length
    st.session_state.is_playing = False


def sync_playback_state(story_length: int) -> None:
    if "current_step" not in st.session_state:
        st.session_state.current_step = 0
    if "story_length" not in st.session_state or st.session_state.story_length != story_length:
        st.session_state.current_step = 0
        st.session_state.story_length = story_length
        st.session_state.is_playing = False
    if "is_playing" not in st.session_state:
        st.session_state.is_playing = False

    if story_length <= 0:
        st.session_state.current_step = 0
    else:
        st.session_state.current_step = max(0, min(st.session_state.current_step, story_length - 1))


def render_code_panel(code: str, current_line: int | None) -> None:
    st.markdown("### Code Execution Panel")
    lines = code.splitlines() or [""]
    rendered_lines = []
    for idx, line in enumerate(lines, start=1):
        active_class = " active" if current_line == idx else ""
        pointer = ">> " if current_line == idx else "   "
        safe_line = line.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        rendered_lines.append(
            f'<div class="code-line{active_class}">{pointer}{idx:>2}  {safe_line}</div>'
        )

    st.markdown(
        '<div class="code-panel">' + "".join(rendered_lines) + "</div>",
        unsafe_allow_html=True,
    )


def render_memory_panel(step: dict[str, Any] | None) -> None:
    st.markdown("### Memory Panel")
    locals_state = step["locals"] if step else {}
    if not locals_state:
        st.info("No visible variables yet for this step.")
        return

    for key, value in locals_state.items():
        st.markdown(
            f"""
            <div class="memory-card">
                <div class="memory-name">{key}</div>
                <div class="memory-value">{value}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def loop_progress(story: list[dict[str, Any]], step: dict[str, Any]) -> tuple[float, str] | None:
    current_line = step["line"]
    code_line = step["code"].strip()
    if not code_line.startswith(("for ", "while ")):
        return None

    matching_steps = [item for item in story if item["line"] == current_line]
    current_iteration = sum(1 for item in matching_steps if item["step_number"] <= step["step_number"])
    total_iterations = len(matching_steps)
    if total_iterations <= 0:
        return None

    return current_iteration / total_iterations, f"Loop iteration {current_iteration}/{total_iterations}"


def render_status_panel(result: dict[str, Any], step: dict[str, Any] | None) -> None:
    st.markdown("### Execution Status")
    if result["status"] == "syntax_error":
        error = result["error"]
        st.markdown(
            f"""
            <div class="status-card">
                <strong>Parsing stopped before execution.</strong><br><br>
                Syntax error at line {error['line']}, column {error['offset']}: {error['message']}
            </div>
            """,
            unsafe_allow_html=True,
        )
        return

    if not step:
        st.info("No execution step is available.")
        return

    st.markdown(
        f"""
        <div class="status-card">
            <strong>Currently executing line {step['line']}</strong><br><br>
            {step['summary']}<br><br>
            <span class="control-hint">{step['state_note']}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    progress_info = loop_progress(result["story"], step)
    if progress_info:
        progress_value, label = progress_info
        st.progress(progress_value, text=label)


def analyze_code(code: str) -> dict[str, Any]:
    code = textwrap.dedent(code).strip("\n")
    lines = code.splitlines()

    if not code.strip():
        return {
            "status": "empty",
            "steps": [],
            "story": [],
            "output": "",
            "error": None,
            "code": code,
        }

    try:
        ast.parse(code)
    except SyntaxError as exc:
        error_line = exc.lineno or 1
        error = {
            "type": "SyntaxError",
            "message": exc.msg,
            "line": error_line,
            "offset": exc.offset or 1,
            "source": exc.text.rstrip("\n") if exc.text else (lines[error_line - 1] if lines else ""),
            "reason": (
                "Python could not understand the program structure, so execution never began. "
                "That means there are no earlier runtime steps to explain."
            ),
        }
        return {
            "status": "syntax_error",
            "steps": [],
            "story": [],
            "agent_profile": build_agent_profile(code, [], error),
            "output": "",
            "error": error,
            "code": code,
        }

    steps: list[dict[str, Any]] = []
    last_record: dict[str, Any] | None = None
    fake_input, consumed_inputs = build_input_provider()

    def trace_lines(frame, event, arg):
        nonlocal last_record
        if frame.f_code.co_filename != "<user_code>":
            return trace_lines

        if event == "line":
            record = {
                "line": frame.f_lineno,
                "code": lines[frame.f_lineno - 1].rstrip() if 0 < frame.f_lineno <= len(lines) else "",
                "locals": collect_visible_locals(frame.f_locals),
            }
            if last_record != record:
                steps.append(record)
                last_record = record
        return trace_lines

    stdout_buffer = io.StringIO()
    user_globals: dict[str, Any] = {"__name__": "__main__", "input": fake_input}

    try:
        compiled = compile(code, "<user_code>", "exec")
        with contextlib.redirect_stdout(stdout_buffer):
            import sys

            old_trace = sys.gettrace()
            sys.settrace(trace_lines)
            try:
                exec(compiled, user_globals, user_globals)
            finally:
                sys.settrace(old_trace)
    except Exception as exc:
        tb_summary = traceback.extract_tb(exc.__traceback__)
        relevant_frame = None
        for frame in reversed(tb_summary):
            if frame.filename == "<user_code>":
                relevant_frame = frame
                break

        error_line = relevant_frame.lineno if relevant_frame else None
        if error_line and (not steps or steps[-1]["line"] != error_line):
            steps.append(
                {
                    "line": error_line,
                    "code": lines[error_line - 1].rstrip() if 0 < error_line <= len(lines) else "",
                    "locals": steps[-1]["locals"] if steps else {},
                }
            )

        error = {
            "type": type(exc).__name__,
            "message": str(exc),
            "line": error_line,
            "reason": (
                f"Execution stops here because Python raised {type(exc).__name__}. "
                "The remaining lines depend on this line finishing successfully, so they cannot run."
            ),
        }
        story = build_story(steps, "runtime_error", error)
        return {
            "status": "runtime_error",
            "steps": steps,
            "story": story,
            "agent_profile": build_agent_profile(code, steps, error),
            "assumed_inputs": consumed_inputs,
            "output": stdout_buffer.getvalue(),
            "error": error,
            "code": code,
        }

    story = build_story(steps, "success", None)
    return {
        "status": "success",
        "steps": steps,
        "story": story,
        "agent_profile": build_agent_profile(code, steps, None),
        "assumed_inputs": consumed_inputs,
        "output": stdout_buffer.getvalue(),
        "error": None,
        "code": code,
    }


def render_hero() -> None:
    st.markdown(
        """
        <div class="hero-title">CodeFlow AI</div>
        """,
        unsafe_allow_html=True,
    )


def render_overview(result: dict[str, Any]) -> None:
    status = result["status"]
    error = result["error"]

    st.markdown("### Overview")
    if status == "empty":
        st.info("Paste Python code and click Explain Code to generate the walkthrough.")
    elif status == "success":
        st.success("The code ran successfully and the full execution story is available below.")
    elif status == "syntax_error":
        st.error(
            f"Syntax error at line {error['line']}, column {error['offset']}: {error['message']}"
        )
    else:
        st.warning(
            f"Execution reached line {error['line']} and then stopped with {error['type']}: {error['message']}"
        )


def render_story(result: dict[str, Any]) -> None:
    status = result["status"]
    story = result["story"]
    error = result["error"]

    if status == "syntax_error":
        left, right = st.columns([1.7, 1], gap="large")
        with left:
            st.markdown("### Execution Story")
            st.markdown(
                f"""
                <div class="step-card error">
                    <div class="step-title">Parsing stopped before execution</div>
                    <div class="step-copy">
                        Python found a syntax problem on line {error['line']}, so it could not start the program.<br><br>
                        <code>{error['source']}</code><br><br>
                        {error['reason']}
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        with right:
            st.markdown("### Result Panel")
            st.markdown(
                f"""
                <div class="section-card">
                    <span class="pill pill-danger">Syntax Error</span>
                    <p><strong>{error['type']}</strong>: {error['message']}</p>
                    <p class="muted">Line {error['line']}, column {error['offset']}</p>
                </div>
                """,
                unsafe_allow_html=True,
            )
            st.markdown("### Submitted Code")
            st.code(result["code"] or "# Empty input", language="python")
        return

    sync_playback_state(len(story))

    if not story:
        st.info("There were no traceable line events for this code.")
        return

    current_step = story[st.session_state.current_step]

    top_left, top_right = st.columns([1.55, 1], gap="large")
    with top_left:
        render_code_panel(result["code"], current_step["line"])
    with top_right:
        render_memory_panel(current_step)

    bottom_left, bottom_right = st.columns([1.55, 1], gap="large")
    with bottom_left:
        render_status_panel(result, current_step)
        st.markdown("### Step Explanation")
        card_class = "step-card error" if current_step["kind"] == "error" else "step-card"
        st.markdown(
            f"""
            <div class="{card_class}">
                <div class="step-title">Step {current_step['step_number']} of {len(story)}</div>
                <div><code>{current_step['code']}</code></div>
                <div class="step-copy" style="margin-top:0.55rem;">{current_step['summary']}</div>
                <div class="step-copy muted" style="margin-top:0.45rem;">{current_step['state_note']}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        control_prev, control_play, control_next, control_reset = st.columns(4)
        with control_prev:
            if st.button("Prev", use_container_width=True, disabled=st.session_state.current_step == 0):
                st.session_state.is_playing = False
                st.session_state.current_step = max(0, st.session_state.current_step - 1)
                st.rerun()
        with control_play:
            play_label = "Pause" if st.session_state.is_playing else "Play"
            if st.button(play_label, use_container_width=True):
                st.session_state.is_playing = not st.session_state.is_playing
                st.rerun()
        with control_next:
            if st.button("Next", use_container_width=True, disabled=st.session_state.current_step >= len(story) - 1):
                st.session_state.is_playing = False
                st.session_state.current_step = min(len(story) - 1, st.session_state.current_step + 1)
                st.rerun()
        with control_reset:
            if st.button("Reset", use_container_width=True):
                reset_playback_state(len(story))
                st.session_state.is_playing = False
                st.rerun()

        st.caption(f"Step {st.session_state.current_step + 1} of {len(story)}")

        if status == "runtime_error" and current_step["kind"] == "error":
            st.markdown(
                f"""
                <div class="callout">
                    <strong>Why execution stops here</strong><br><br>
                    {error['reason']}
                </div>
                """,
                unsafe_allow_html=True,
            )

    with bottom_right:
        st.markdown("### Result Panel")
        if status == "success":
            st.markdown(
                """
                <div class="section-card">
                    <span class="pill pill-cool">Complete Run</span>
                    <p>The program reached the end without an exception.</p>
                </div>
                """,
                unsafe_allow_html=True,
            )
        elif status == "runtime_error":
            st.markdown(
                f"""
                <div class="section-card">
                    <span class="pill pill-dark">Runtime Error</span>
                    <p><strong>{error['type']}</strong>: {error['message']}</p>
                    <p class="muted">Execution stopped at line {error['line']}.</p>
                </div>
                """,
                unsafe_allow_html=True,
            )

        st.markdown("### Console Output")
        st.code(result["output"] or "No stdout output produced.", language="text")

        assumed_inputs = result.get("assumed_inputs", [])
        if assumed_inputs:
            st.markdown("### Assumed Inputs")
            for item in assumed_inputs:
                st.markdown(
                    f"- `{item['prompt']}` -> `{item['value']}`"
                )

        if result["agent_profile"]["visualization"] == "State Table View":
            st.markdown("### State Table")
            st.dataframe(build_state_rows(story), use_container_width=True, hide_index=True)

        st.markdown("### Submitted Code")
        st.code(result["code"] or "# Empty input", language="python")

    if st.session_state.is_playing and st.session_state.current_step < len(story) - 1:
        time.sleep(0.9)
        st.session_state.current_step += 1
        st.rerun()
    elif st.session_state.is_playing and st.session_state.current_step >= len(story) - 1:
        st.session_state.is_playing = False


def sidebar() -> str:
    with st.sidebar:
        st.markdown("## How to use")
        st.caption("Paste Python code only. This app explains execution, not general chat prompts.")
        st.markdown("## Starter snippets")
        starter = st.selectbox(
            "Choose an example",
            [
                "Blank",
                "Loop walkthrough",
                "Function walkthrough",
                "Runtime error",
                "Syntax error",
            ],
        )

    starter_map = {
        "Blank": "",
        "Loop walkthrough": "total = 0\nfor i in range(1, 4):\n    total += i\nprint(total)",
        "Function walkthrough": (
            "def add(a, b):\n"
            "    result = a + b\n"
            "    return result\n\n"
            "sum_value = add(3, 4)\n"
            "print(sum_value)"
        ),
        "Runtime error": "numbers = [4, 8, 15]\nprint(numbers[5])",
        "Syntax error": "for i in range(3)\n    print(i)",
    }
    return starter_map[starter]


def main() -> None:
    inject_styles()
    render_hero()
    starter = sidebar()

    st.markdown("### Explain This Code")
    user_input = st.text_area(
        "Paste Python code",
        value=starter,
        height=320,
        placeholder="Paste Python code here",
    )

    if "last_result" not in st.session_state:
        st.session_state.last_result = None

    explain = st.button("Explain Code", use_container_width=True)
    if explain:
        st.session_state.last_result = analyze_code(user_input)

    if st.session_state.last_result is None:
        st.info("Pick a starter or paste your own Python code, then click Explain Code.")
        return

    result = st.session_state.last_result
    render_overview(result)
    render_story(result)


if __name__ == "__main__":
    main()
