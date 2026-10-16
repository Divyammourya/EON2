# EON terminal layer — integrated patch

This patch adds command execution to the existing CodingWorkspace architecture.

Flow:

Intent
→ CodingCommandParser
→ Planner
→ PlanExecutor
→ CodingAgent.run_command()
→ CommandRunner
→ subprocess (shell=False)
→ ExecutionContext["run_command"]

Features:
- project-root working directory
- no shell invocation
- stdout/stderr capture
- exit-code reporting
- timeout
- output truncation
- basic accidental-destructive-command checks
- parser/planner/workspace integration
- integration tests

Important:
CommandRunner is not a security sandbox. Do not use it to execute untrusted
commands on the host without adding an OS/container sandbox later.
