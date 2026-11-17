"""Exam check script. Run it from the exam folder, the one that has the check and data folders in it.

    python check/run_checks.py start    at the start: checks that everything works
    python check/run_checks.py run      while you work: runs your program on data/sample.txt (or on a file you add)
    python check/run_checks.py C        end of part C: runs your program on the part C check files
    python check/run_checks.py D        end of part D: runs your program on the part D check file

If "python" is not recognized, write "py" instead of "python".

Teacher only, after the exam:
    python check/run_checks.py C --at <commit>    runs the code as it was in that commit
"""
import base64
import datetime
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import zlib
from pathlib import Path

PACKED = "eNqtVutOGkEYfZUNv780O7PsAv5tH8PErLq2jYoGIakxvgMXAakrUKq4+ELzOj1nBgrW5WLSf+zMnO/+ncNN4XNhz7spHH1Ljk5V/Kn+o47vQi25vKjVD47j6z1Phf5+tZbEx0nt4PuxVOPzROrXl4kcXlycytlFXOU7qSX1Rs3+3K8qX4mZmpYZmDvPpKaLHyO5qjeOk2pdTBOfv8yrycyLKF8CnwgtOLnDTUrMg3levp/AQGoePdPHdWZmogEqElQSnExM6sFmB28y+dpIrgB5wfkUsMwzM4vum5GHlxk+fkrkS8k6DQTXtAmXbcSLyJZuN9so+hKGtFEUuB6YMW3MzD2uV1JFMjhs0gZqASCeSuhLFAGqkHNrAX3B28GmOvmiFFF+KLDUwQ1QXRvY73xMKBEjVMiyB0iLgCYTWusElaGHSJCrjYq59lafv+uFCnwBRqPjbWvd9q+PADvrotK2bmVBsbouqiGcZDS56N8/IxKWiKgIvluoFBBPeDBDv+tJjNmtral0xca2rc6bG63gX9kZxQ/4HS8sTWzQzWUIm+2UK9vrtNkCKh3aOGBjjKshLbRw2V4txPsO+Zwe4jCqQxw+cGE6KNLONeDClbeO0vs9dWumQpk/HphX2h/iLnc2dCjF4EPThFUuw0dBvDmHHf4vDgsUh6rpqIGBbFtrtKfIOQ00S4ETTmmGt0NA53OdR2W6QlDA3qToDfyxuV3zmJ9x2ZEXMUXOwYQ99XDdNumGXhTZiSDkzRj9S11wZNn45GRDRoB5nkdsRLJ8cmTJHXqy3Pm88x4V7TIGJaZjkyHNZ4x+ObxvhsFJQ+EWvf2yVCmd12Dtf7jBmiJ1Z9d5vkYvayWKI6YpUVNk3V2UYIwiYUYlPmucV+P8zdPQKc3F6+Gq45grW1WZXFBEdwF3IHXhzSzhkW0WzrZSBRdJO3WaG3mw6S5N5PYcVY9stiG1tQtQy3Rcw1Gjv9g3jA6IIiSihg9pr2lVf7S+NKVFUUsyj3/o2CEzvZ0nymoiC0wx4dkrGzkiuXVXCSM3UYcOia6I7b/dvfvVLcpVYE0duF8Udcx/N2vXG8QjKtIEKYpHzyV5Z4eoa1XpeVcBcUqrqWZjy412LtrANLfIoFs9Tfbuu6iH9LImz7J7XCIhkbIf2c4ZqjNm+B+UjI2zv/Uflp1EVXYBpk52p+tDn8tH4fb2D1kZt4Q="
ROOT = Path(__file__).resolve().parent.parent
RUN_TIMEOUT = int(os.environ.get("EXAM_RUN_TIMEOUT", "60"))
BUILD_TIMEOUT = 300
COMMIT_MESSAGE = {"C": "before change", "D": "after change"}
LINE = "=" * 64

try:
    sys.stdout.reconfigure(errors="replace")
    sys.stderr.reconfigure(errors="replace")
except AttributeError:
    pass


def say(text=""):
    print(text, flush=True)


def child_env():
    env = dict(os.environ)
    env.update({"PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8", "DOTNET_CLI_TELEMETRY_OPTOUT": "1",
                "DOTNET_NOLOGO": "1", "DOTNET_SKIP_FIRST_TIME_EXPERIENCE": "1"})
    return env


def run(cmd, cwd, timeout, stdin_text=None):
    """Runs a command and never raises. Returns (exit code or None, stdout bytes, stderr bytes, timed out, ms)."""
    start = time.time()
    try:
        p = subprocess.run(cmd, cwd=str(cwd), capture_output=True, timeout=timeout, env=child_env(),
                           input=None if stdin_text is None else stdin_text.encode("utf-8"))
        return p.returncode, p.stdout, p.stderr, False, int((time.time() - start) * 1000)
    except subprocess.TimeoutExpired as e:
        return None, e.stdout or b"", e.stderr or b"", True, int((time.time() - start) * 1000)
    except OSError as e:
        return None, b"", str(e).encode("utf-8"), False, int((time.time() - start) * 1000)


def text(data):
    return data.decode("utf-8", errors="replace")


def tail(s, n=40):
    lines = s.strip().splitlines()
    return "\n".join(lines[-n:])


def detect_lang(root):
    if (root / "main.py").exists():
        return "python"
    if (root / "src" / "Main.java").exists():
        return "java"
    if (root / "app" / "app.csproj").exists():
        return "csharp"
    return None


# ---------- git ----------

def git(args, cwd=ROOT, timeout=60):
    code, out, err, _, _ = run(["git"] + args, cwd, timeout)
    return code, text(out).strip(), text(err).strip()


def git_available():
    return shutil.which("git") is not None and git(["--version"])[0] == 0


def ensure_repo():
    """Makes sure the exam folder is inside a git repository with a commit identity. Returns a list of notes."""
    notes = []
    if git(["rev-parse", "--show-toplevel"])[0] != 0:
        code, _, err = git(["init"])
        if code != 0:
            return ["could not create a git repository: " + err]
        notes.append("created a new git repository in this folder")
    for key, value in (("user.name", "student"), ("user.email", "student@exam.local")):
        if git(["config", key])[0] != 0:
            git(["config", key, value])
            notes.append("set git " + key + " for this folder")
    return notes


def commit_all(message):
    """Commits every change. Returns (commit hash or '', note)."""
    git(["add", "-A"])
    if git(["status", "--porcelain"])[1]:
        code, out, err = git(["commit", "-m", message])
        if code != 0:
            return "", "the commit failed: " + (err or out)
        return git(["rev-parse", "--short", "HEAD"])[1], 'saved your work in a commit: "' + message + '"'
    head = git(["rev-parse", "--short", "HEAD"])
    return (head[1] if head[0] == 0 else ""), "nothing new to commit"


def git_log():
    code, out, _ = git(["log", "--reverse", "--date=iso", "--format=%h|%ad|%s"])
    return out if code == 0 else ""


def git_numstat():
    code, out, _ = git(["log", "--reverse", "--format=commit|%h|%s", "--numstat"])
    return out if code == 0 else ""


# ---------- building and running the student's program ----------

def build(lang, root):
    """Compiles Java or C#. Returns None for Python, else {'ok': bool, 'output': str, 'ms': int}."""
    if lang == "python":
        return None
    if lang == "java":
        if shutil.which("javac") is None:
            return {"ok": False, "output": "javac was not found. Java (the JDK) is not installed, or it is not in PATH.", "ms": 0, "env": True}
        sources = sorted(str(p) for p in (root / "src").rglob("*.java"))
        (root / "out").mkdir(exist_ok=True)
        code, out, err, timed_out, ms = run(["javac", "-encoding", "UTF-8", "-d", str(root / "out")] + sources, root, BUILD_TIMEOUT)
    else:
        if shutil.which("dotnet") is None:
            return {"ok": False, "output": "dotnet was not found. The .NET SDK is not installed, or it is not in PATH.", "ms": 0, "env": True}
        code, out, err, timed_out, ms = run(["dotnet", "build", str(root / "app"), "-nologo", "-v", "q", "-clp:ErrorsOnly",
                                             "-o", str(root / "app" / "bin" / "exam")], root, BUILD_TIMEOUT)
    output = tail(text(out) + "\n" + text(err), 60)
    if timed_out:
        output = "the build did not finish within " + str(BUILD_TIMEOUT) + " seconds\n" + output
    return {"ok": code == 0, "output": output, "ms": ms}


def program(lang, root, input_path):
    if lang == "python":
        return [sys.executable, str(root / "main.py"), str(input_path)]
    if lang == "java":
        return ["java", "-Dfile.encoding=UTF-8", "-cp", str(root / "out"), "Main", str(input_path)]
    return ["dotnet", str(root / "app" / "bin" / "exam" / "app.dll"), str(input_path)]


def run_one(lang, root, name, path):
    code, out, err, timed_out, ms = run(program(lang, root, path), root, RUN_TIMEOUT)
    stdout = text(out)
    return {"file": name, "exit": code, "timed_out": timed_out, "ms": ms, "stdout": stdout,
            "stderr_tail": tail(text(err)), "decode_problem": "�" in stdout}


def describe(r):
    if r["timed_out"]:
        return "STOPPED: still running after " + str(RUN_TIMEOUT) + " seconds"
    if r["exit"] is None:
        return "COULD NOT START: " + (r["stderr_tail"] or "unknown reason")
    if r["exit"] != 0:
        last = r["stderr_tail"].splitlines()[-1] if r["stderr_tail"] else "no error message"
        return "CRASHED (exit code " + str(r["exit"]) + "). Last error line: " + last
    n = len([x for x in r["stdout"].splitlines() if x.strip()])
    return "finished, printed " + str(n) + " lines"


CODE_SUFFIXES = {".py", ".java", ".cs"}
SKIP_DIRS = {".git", "check", "data", "out", "bin", "obj", "__pycache__", ".idea", ".vs", ".vscode"}


# what the outline looks for; only names and lengths are recorded, never the code itself
PY_CLASS = re.compile(r"^\s*class\s+(\w+)")
PY_DEF = re.compile(r"^(\s*)(?:async\s+)?def\s+(\w+)")
CURLY_CLASS = re.compile(r"\b(?:class|interface|enum|record)\s+(\w+)")
CURLY_METHOD = re.compile(r"^\s*(?:(?:public|private|protected|internal|static|final|override|virtual|abstract|async|sealed|synchronized|default)\s+)*"
                          r"([\w<>\[\],.?]+)\s+(\w+)\s*\([^;]*$")
NOT_METHODS = {"if", "for", "foreach", "while", "switch", "catch", "return", "new", "else", "using", "lock", "throw"}
TYPE_WORD = re.compile(r"[\"'](?:student|teacher|guest|alumna)[\"']", re.IGNORECASE)
TYPE_TEST = re.compile(r"\b(?:if|elif|case|switch|when)\b|==|\.equals\s*\(|Equals\s*\(", re.IGNORECASE)


def outline(text, suffix):
    """Classes, functions with their length, and how many lines test the reader type, so the teacher sees the design at a glance."""
    lines = text.splitlines()
    classes, funcs = [], []
    if suffix == ".py":
        starts = []
        for i, line in enumerate(lines):
            m = PY_CLASS.match(line)
            if m:
                classes.append(m.group(1))
            m = PY_DEF.match(line)
            if m:
                starts.append((i, len(m.group(1)), m.group(2)))
        for k, (i, indent, name) in enumerate(starts):
            end = len(lines)
            for j in range(i + 1, len(lines)):
                stripped = lines[j].strip()
                if stripped and not stripped.startswith("#") and len(lines[j]) - len(lines[j].lstrip()) <= indent:
                    end = j
                    break
            funcs.append({"name": name, "lines": end - i})
    else:
        for i, line in enumerate(lines):
            for m in CURLY_CLASS.finditer(line):
                classes.append(m.group(1))
            m = CURLY_METHOD.match(line)
            if not m or m.group(1) in NOT_METHODS or m.group(2) in NOT_METHODS or CURLY_CLASS.search(line):
                continue
            # the method ends where its braces close
            depth, opened, end = 0, False, len(lines)
            for j in range(i, len(lines)):
                depth += lines[j].count("{") - lines[j].count("}")
                opened = opened or "{" in lines[j]
                if opened and depth <= 0:
                    end = j + 1
                    break
            funcs.append({"name": m.group(2), "lines": end - i})
    type_ifs = sum(1 for line in lines if TYPE_WORD.search(line) and TYPE_TEST.search(line))
    return {"classes": classes, "functions": funcs, "type_ifs": type_ifs}


def code_files(root):
    """The student's code files, their line counts and outline, so the teacher can see how the code is split and designed."""
    files = []
    for path in sorted(root.rglob("*")):
        rel = path.relative_to(root)
        if path.is_file() and path.suffix in CODE_SUFFIXES and not (set(rel.parts[:-1]) & SKIP_DIRS):
            entry = {"path": rel.as_posix(), "lines": None}
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
                entry["lines"] = len(text.splitlines())
                entry.update(outline(text, path.suffix))
            except (OSError, re.error):
                pass
            files.append(entry)
    return files


def check_files(mode):
    data = json.loads(zlib.decompress(base64.b64decode(PACKED)).decode("utf-8"))
    return data[mode]


# ---------- modes ----------

def mode_start(lang):
    say(LINE)
    say("Exam setup check")
    say("Folder: " + str(ROOT))
    say(LINE)
    problems = []

    def ok(msg):
        say("[OK]      " + msg)

    def bad(msg):
        problems.append(msg)
        say("[PROBLEM] " + msg)

    if lang is None:
        bad("this is not an exam folder: main.py, src/Main.java or app/app.csproj is missing")
    else:
        ok("language: " + {"python": "Python", "java": "Java", "csharp": "C#"}[lang])
    if sys.version_info < (3, 7):
        bad("Python " + sys.version.split()[0] + " is too old. Python 3.7 or newer is needed")
    else:
        ok("Python " + sys.version.split()[0])
    if not git_available():
        bad("git was not found. git is not installed, or it is not in PATH")
    else:
        for note in ensure_repo():
            ok(note)
        _, note = commit_all("start")
        ok("git: " + note)
    if lang is not None:
        b = build(lang, ROOT)
        if b is not None:
            if b["ok"]:
                ok("the program compiles")
            else:
                bad("the program does not compile:\n" + b["output"])
        if b is None or b["ok"]:
            sample = ROOT / "data" / "sample.txt"
            r = run_one(lang, ROOT, "sample.txt", sample)
            if r["exit"] == 0 and not r["timed_out"]:
                ok("the program runs on data/sample.txt")
            else:
                bad("the program does not run on data/sample.txt: " + describe(r) + "\n" + r["stderr_tail"])
    say(LINE)
    if problems:
        say("NOT READY. Raise your hand and show this window to the proctor.")
    else:
        say("READY. Everything works. Go back to the booklet.")
    say(LINE)
    return 1 if problems else 0


def mode_check(mode, lang, at=None):
    files = check_files(mode)
    say(LINE)
    say("Exam check, part " + mode + ("  (teacher run on commit " + at + ")" if at else ""))
    say("Folder: " + str(ROOT))
    say(LINE)
    if lang is None:
        say("This is not an exam folder: main.py, src/Main.java or app/app.csproj is missing.")
        say("Run this command from the exam folder, the one that has the check and data folders in it.")
        return 1

    has_git = git_available()
    git_info = {"available": has_git, "commit": "", "note": "", "log": "", "numstat": ""}
    work_root, worktree = ROOT, None
    if has_git and at:
        worktree = Path(tempfile.mkdtemp(prefix="exam-at-"))
        code, _, err = git(["worktree", "add", "--detach", str(worktree), at])
        if code != 0:
            say("Could not check out commit " + at + ": " + err)
            return 1
        work_root = worktree / ROOT.relative_to(Path(git(["rev-parse", "--show-toplevel"])[1]).resolve())
        git_info["commit"] = at
    elif has_git:
        for note in ensure_repo():
            say("git: " + note)
        git_info["commit"], git_info["note"] = commit_all(COMMIT_MESSAGE[mode])
        say("git: " + git_info["note"])
    else:
        say("git was not found, so your work was not saved in a commit. Tell the proctor after the check.")

    result = {"kind": "placement-results", "version": 1, "mode": mode, "lang": lang,
              "created": datetime.datetime.now().isoformat(timespec="seconds"), "created_epoch": int(time.time() * 1000),
              "at": at, "build": None, "runs": [], "sample_run": None, "warnings": []}
    try:
        b = build(lang, work_root)
        result["build"] = b
        if b is not None and not b["ok"]:
            result["warnings"].append("build_failed")
            say("")
            say("Your program does not compile, so it did not run on any check file.")
            say("The errors:")
            say(b["output"])
            say("")
            say("Raise your hand and show this window to the proctor.")
        else:
            tmp = Path(tempfile.mkdtemp(prefix="exam-check-"))
            written = []
            try:
                for name, content in files.items():
                    path = tmp / name
                    path.write_text(content, encoding="utf-8", newline="\n")
                    written.append(path)
                    r = run_one(lang, work_root, name, path)
                    result["runs"].append(r)
                    say(name + ": " + describe(r))
                result["sample_run"] = run_one(lang, work_root, "sample.txt", work_root / "data" / "sample.txt")
            finally:
                for path in written:
                    path.unlink()
                tmp.rmdir()
            outs = [r["stdout"].strip() for r in result["runs"] if r["exit"] == 0 and r["stdout"].strip()]
            sample_out = (result["sample_run"] or {}).get("stdout", "").strip()
            same = len(outs) >= 2 and len(set(outs)) == 1
            like_sample = bool(outs) and sample_out and all(o == sample_out for o in outs)
            if same or like_sample:
                result["warnings"].append("same_output")
                say("")
                say("WARNING: your program printed the same report for different files.")
                say("It probably reads a fixed file instead of the file it gets as an argument.")
                say("Raise your hand and show this window to the proctor before you upload the file.")
            if result["runs"] and all(r["exit"] != 0 or r["timed_out"] for r in result["runs"]):
                result["warnings"].append("no_run")
                say("")
                say("Your program did not finish on any check file. Raise your hand and show this window to the proctor.")
    finally:
        if worktree is not None:
            git(["worktree", "remove", "--force", str(worktree)])

    result["files"] = code_files(work_root)
    if has_git:
        git_info["log"] = git_log()
        git_info["numstat"] = git_numstat()
    result["git"] = git_info

    name = "results_" + mode + ("_at_" + at if at else "") + ".json"
    out_path = ROOT / name
    if out_path.exists():
        out_path.replace(ROOT / (name[:-5] + "." + time.strftime("%H%M%S") + ".json"))
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    say("")
    say(LINE)
    say("DONE. Your results file is:")
    say("    " + str(out_path))
    say("Go back to the booklet, and upload this file.")
    say(LINE)
    return 0


def mode_run(lang, files):
    """Builds the program if needed, and runs it on one input file, with its output straight in this window."""
    if lang is None:
        say("Run this command from the exam folder, the one that has the check and data folders in it.")
        return 1
    path = Path(files[0]).resolve() if files else ROOT / "data" / "sample.txt"
    b = build(lang, ROOT)
    if b is not None and not b["ok"]:
        say("Your program does not compile:")
        say(b["output"])
        return 1
    try:
        return subprocess.call(program(lang, ROOT, path), cwd=str(ROOT), env=child_env())
    except OSError as e:
        say("Could not start your program: " + str(e))
        return 1


def main(argv):
    args = [a for a in argv if not a.startswith("--")]
    at = None
    if "--at" in argv:
        i = argv.index("--at")
        at = argv[i + 1] if i + 1 < len(argv) else None
        args = [a for a in args if a != at]
    mode = args[0].upper() if args else ""
    lang = detect_lang(ROOT)
    if mode == "START":
        return mode_start(lang)
    if mode in ("C", "D"):
        return mode_check(mode, lang, at)
    if mode == "RUN":
        return mode_run(lang, args[1:])
    say(__doc__)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
