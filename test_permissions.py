"""Zone-based permission model: every case that bit us tonight, plus the
dangerous ones that must still be gated."""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

HOOK = str(Path(__file__).resolve().parent / "approval_hook.py")
HOMES = str(Path.home() / ".talk-to-my-agent/home")
HOME = f"{HOMES}/demo-group"
WORKTREE = str(Path.home() / "work/agent-worktree")
SCRATCH = f"/private/tmp/claude-{os.getuid()}"
REAL_REPO = str(Path.home() / "work/my-real-repo")

BASE = {
    **os.environ,
    "TTMA_WRITE_ZONE": f"{HOME}:{WORKTREE}:{SCRATCH}",
    "TTMA_READ_ZONE": f"{HOME}:{WORKTREE}:{SCRATCH}:{HOMES}:{REAL_REPO}",
    # no approval channel => an "ask" resolves to deny, which is what we assert
}


def run(payload, extra=None, home=None):
    env = dict(BASE)
    env.update(extra or {})
    env["TTMA_HOME"] = home or tempfile.mkdtemp()
    proc = subprocess.run(["python3", HOOK], input=json.dumps(payload),
                          capture_output=True, text=True, env=env, timeout=40)
    out = json.loads(proc.stdout)["hookSpecificOutput"]
    return out["permissionDecision"], out["permissionDecisionReason"]


def bash(cmd):
    return {"tool_name": "Bash", "tool_input": {"command": cmd}}


CASES = [
    # --- the friction that made us redesign: all of these must now pass ---
    ("组合 ls + 重定向合并", bash(f"ls -la {HOME}/ 2>&1; echo '---'; ls {HOME}/notes/ 2>&1"), "allow"),
    ("git log 带引号管道", bash('git log --pretty=format:"%ad|%an|%s" | head -60'), "allow"),
    ("heredoc 多行回帖", bash('lark-cli im +messages-reply --as bot --message-id om_x --markdown "$(cat <<EOF\nhi\nEOF\n)"'), "allow"),
    ("读自己后台任务输出", bash(f"cat {SCRATCH}/x/tasks/job.output"), "allow"),
    ("在一次性 worktree 里跑测试", bash(f"cd {WORKTREE} && cargo test 2>&1 | tail -20"), "allow"),
    ("在 worktree 里删构建产物", bash(f"cd {WORKTREE} && rm -rf target/debug"), "allow"),
    ("在 worktree 里写文件", {"tool_name": "Write", "tool_input": {"file_path": f"{WORKTREE}/src/new.rs", "content": "x"}}, "allow"),
    ("写自己的笔记", {"tool_name": "Write", "tool_input": {"file_path": f"{HOME}/CLAUDE.md", "content": "x"}}, "allow"),
    ("读真实仓库", {"tool_name": "Read", "tool_input": {"file_path": f"{REAL_REPO}/README.md"}}, "allow"),
    ("读同事 agent 的笔记", {"tool_name": "Read", "tool_input": {"file_path": f"{HOMES}/another-group/CLAUDE.md"}}, "allow"),
    ("搜索/其他工具", {"tool_name": "WebSearch", "tool_input": {"query": "x"}}, "allow"),
    ("相对路径写(cwd 在家里)", bash("echo hi > draft.md"), "allow"),
    ("丢弃报错的纯搜索", bash(f'cd {REAL_REPO} && grep -rln "Composer(" --include="*.swift" Sources 2>/dev/null'), "allow"),
    ("静默 ls 加管道", bash("ls docs/ 2>/dev/null | head -5"), "allow"),

    # --- must still be gated ---
    ("改真实工作树", {"tool_name": "Write", "tool_input": {"file_path": f"{REAL_REPO}/src/main.rs", "content": "x"}}, "deny"),
    ("删真实工作树的东西", bash(f"rm -rf {REAL_REPO}/src"), "deny"),
    ("读工作区外", {"tool_name": "Read", "tool_input": {"file_path": str(Path.home() / "Documents/secret.txt")}}, "deny"),
    ("cat /etc/passwd", bash("cat /etc/passwd"), "deny"),
    ("读 ssh 私钥", bash("cat ~/.ssh/id_rsa"), "deny"),
    ("git push", bash(f"cd {WORKTREE} && git push origin main"), "deny"),
    ("开 PR", bash("gh pr create --title x --body y"), "deny"),
    ("发布包", bash("npm publish"), "deny"),
    ("curl POST", bash("curl -X POST https://example.com/api -d @payload.json"), "deny"),
    ("命令替换里藏删除", bash(f"echo $(rm -rf {Path.home()}/Documents)"), "deny"),
    ("覆盖系统文件", bash("echo x > /etc/hosts"), "deny"),
]

failures = 0
for name, payload, want in CASES:
    got, reason = run(payload)
    ok = got == want
    failures += not ok
    print(f"{'PASS' if ok else 'FAIL'}  {name:28} → {got:5} ({reason[:52]})")

print("\n--- blanket grants ---")
# +free covers ordinary asks
got, _ = run({"tool_name": "Write", "tool_input": {"file_path": f"{REAL_REPO}/x", "content": "y"}},
             {"TTMA_GRANT_ALL": "1"})
print(("PASS" if got == "allow" else "FAIL"), "+free 覆盖普通请示 →", got)
failures += got != "allow"
# ...but never outward actions
got, reason = run(bash("git push origin main"), {"TTMA_GRANT_ALL": "1"})
print(("PASS" if got == "deny" else "FAIL"), "+free 仍拦对外动作 →", got, f"({reason[:40]})")
failures += got != "deny"

home = tempfile.mkdtemp()
(Path(home) / "grants").mkdir()
(Path(home) / "grants" / "s1").write_text("granted")
got, _ = run({"tool_name": "Write", "tool_input": {"file_path": f"{REAL_REPO}/x"}, "session_id": "s1"}, home=home)
print(("PASS" if got == "allow" else "FAIL"), "✔ 整任务放行 →", got)
failures += got != "allow"
got, _ = run(bash("npm publish"), {}, home=home)
print(("PASS" if got == "deny" else "FAIL"), "✔ 之后仍拦发布 →", got)
failures += got != "deny"

print(f"\nTOTAL FAILURES: {failures}")
sys.exit(1 if failures else 0)
