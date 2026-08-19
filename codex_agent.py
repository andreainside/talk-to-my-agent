#!/usr/bin/env python3
"""Codex backend: one persistent `codex app-server` per group.

Same shape as the Claude backend — a colleague per room, with a continuous
thread and its own home — but spoken over JSON-RPC instead of a message stream.

Two things differ from Claude, and both are honest wins or honest costs:

* Containment is a real OS sandbox (`workspace-write` limited to the write
  zone, network off). Escalation beyond it comes back to us as an approval
  request, which we route through the same policy the Claude backend uses, so
  both backends ask the owner the same questions.
* A message sent while a turn is running (`turn/steer`) joins that turn, but
  Codex answers at its next reasoning boundary — during a blocking foreground
  command it will not reply until the command finishes. Claude backgrounds long
  commands and answers immediately; Codex does not promise that.
"""

import json
import os
import subprocess
import threading
import time
from pathlib import Path


class CodexAgent:
    """One group's Codex colleague. Mirrors the Claude agent's interface."""

    backend = "codex"

    def __init__(self, cfg, state, chat_id, name, home, gate, briefing):
        self.cfg = cfg
        self.state = state
        self.chat_id = chat_id
        self.name = name
        self.home = home
        self.gate = gate                # (tool_name, tool_input) -> bool
        self.briefing = briefing
        self.lock = threading.Lock()
        self.proc = None
        self.thread_id = (state.get("sessions") or {}).get(chat_id)
        self.turn_id = None
        self.busy_since = None
        self.last_request = ""
        self.cost = (state.get("costs") or {}).get(chat_id, 0.0)
        self._next_id = 1
        self._pending = {}              # request id -> (event, result box)

    # -- json-rpc plumbing -------------------------------------------------

    def _write(self, payload):
        with self.lock:
            self.proc.stdin.write(json.dumps(payload) + "\n")
            self.proc.stdin.flush()

    def _request(self, method, params, timeout=120):
        request_id = self._next_id
        self._next_id += 1
        done, box = threading.Event(), {}
        self._pending[request_id] = (done, box)
        self._write({"id": request_id, "method": method, "params": params})
        if not done.wait(timeout):
            self._pending.pop(request_id, None)
            raise TimeoutError(f"{method} timed out")
        return box.get("result")

    def _notify(self, method, params=None):
        self._write({"method": method, "params": params or {}})

    def _respond(self, request_id, result):
        self._write({"id": request_id, "result": result})

    # -- lifecycle ---------------------------------------------------------

    def start(self):
        env = dict(os.environ)
        env.update(self.cfg.get("_agent_env", {}))
        self.proc = subprocess.Popen(
            ["codex", "app-server", "--stdio"],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            text=True, bufsize=1, cwd=self.home, env=env,
        )
        threading.Thread(target=self._read_loop, args=(self.proc,), daemon=True).start()
        self._request("initialize", {
            "clientInfo": {"name": "talk-to-my-agent", "title": "talk-to-my-agent", "version": "0.5"},
        })
        self._notify("initialized")

        workdir = Path(self.cfg["workdir"]).expanduser()
        notes = self.home / "AGENTS.md"
        instructions = self.briefing
        if notes.exists():
            # Codex loads AGENTS.md from cwd; the agent works in the repo, so its
            # own notes (kept in its home, outside git) ride in as instructions.
            instructions = notes.read_text() + "\n\n---\n\n" + self.briefing
        opened = {
            "cwd": str(workdir if workdir.is_dir() else self.home),
            "sandbox": "workspace-write",
            "approvalPolicy": "on-request",
            "developerInstructions": instructions,
        }
        if self.cfg.get("model"):
            opened["model"] = self.cfg["model"]
        if self.thread_id:
            try:
                self._request("thread/resume", {"threadId": self.thread_id, **opened})
                return
            except Exception:  # noqa: BLE001 - a lost thread is a new hire, not a crash
                self.thread_id = None
        result = self._request("thread/start", opened) or {}
        thread = result.get("thread") or result
        self.thread_id = thread.get("id") or thread.get("threadId")
        if self.thread_id:
            self.state.setdefault("sessions", {})[self.chat_id] = self.thread_id

    def ensure_running(self):
        if self.proc is None or self.proc.poll() is not None:
            self.start()

    def restart(self, forget=False):
        if self.proc and self.proc.poll() is None:
            self.proc.kill()
        self.proc = None
        self.turn_id = None
        if forget:
            self.thread_id = None
            (self.state.setdefault("sessions", {})).pop(self.chat_id, None)

    # -- speaking ----------------------------------------------------------

    def send(self, text):
        """Idle → a new turn. Busy → steer into the running one."""
        try:
            self.ensure_running()
            payload = {"threadId": self.thread_id, "input": [{"type": "text", "text": text}]}
            if self.turn_id:
                try:
                    self._request("turn/steer", {**payload, "expectedTurnId": self.turn_id})
                    return True
                except Exception:  # noqa: BLE001 - turn ended between check and send
                    self.turn_id = None
            sandbox = {
                "type": "workspaceWrite",
                "writableRoots": self.cfg.get("_write_zone", []),
                "networkAccess": False,   # network escalates → our policy sees it
            }
            self._request("turn/start", {**payload, "sandboxPolicy": sandbox})
            return True
        except Exception:  # noqa: BLE001
            return False

    # -- incoming ----------------------------------------------------------

    def _read_loop(self, proc):
        for line in proc.stdout:
            line = line.strip()
            if not line:
                continue
            try:
                message = json.loads(line)
            except ValueError:
                continue
            if "result" in message or "error" in message:
                pending = self._pending.pop(message.get("id"), None)
                if pending:
                    done, box = pending
                    box["result"] = message.get("result")
                    box["error"] = message.get("error")
                    done.set()
                continue
            method = message.get("method") or ""
            params = message.get("params") or {}
            if message.get("id") is not None:
                threading.Thread(target=self._serve, args=(message["id"], method, params),
                                 daemon=True).start()
                continue
            self._on_notification(method, params)

    def _on_notification(self, method, params):
        if method == "turn/started":
            self.turn_id = (params.get("turn") or params).get("id") or params.get("turnId")
            self.busy_since = self.busy_since or time.time()
        elif method == "turn/completed":
            self.turn_id = None
            self.busy_since = None
            grants = Path(os.environ.get("TTMA_HOME", Path.home() / ".talk-to-my-agent")) / "grants"
            try:
                (grants / (self.thread_id or "")).unlink()  # ✔ is per task, not per lifetime
            except OSError:
                pass
            usage = params.get("usage") or {}
            cost = usage.get("totalCostUsd") or usage.get("total_cost_usd")
            if isinstance(cost, (int, float)):
                self.cost += cost
                self.state.setdefault("costs", {})[self.chat_id] = round(self.cost, 4)

    def _serve(self, request_id, method, params):
        """Server→client requests. Approvals go through the shared policy so both
        backends ask the owner the same questions, in the same words."""
        if method in ("item/commandExecution/requestApproval", "execCommandApproval"):
            command = params.get("command")
            if isinstance(command, list):
                command = " ".join(str(part) for part in command)
            allowed = self.gate("Bash", {
                "command": command or "",
                "description": params.get("reason") or "",
            })
            self._respond(request_id, {"decision": "accept" if allowed else "decline"})
        elif method in ("item/fileChange/requestApproval", "applyPatchApproval"):
            changes = params.get("changes") or params.get("fileChanges") or {}
            target = next(iter(changes), "") if isinstance(changes, dict) else ""
            allowed = self.gate("Write", {
                "file_path": str(target),
                "description": params.get("reason") or "修改文件",
            })
            self._respond(request_id, {"decision": "accept" if allowed else "decline"})
        elif method == "item/permissions/requestApproval":
            allowed = self.gate("Permissions", {
                "description": params.get("reason") or "扩大权限",
                "detail": json.dumps(params, ensure_ascii=False)[:300],
            })
            self._respond(request_id, {"decision": "accept" if allowed else "decline"})
        else:
            # Unknown server request: answer something harmless rather than hang.
            self._respond(request_id, {})
