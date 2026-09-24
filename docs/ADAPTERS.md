# Agent adapters

Adapters translate a task description into a command-argument array that the recorder can execute. They build commands; they never execute them, and they never interpolate into a shell.

## Interface

```python
class CommandAdapter(Protocol):
    name: str
    def build(self, task: str, repo: Path) -> AdapterCommand: ...
```

`AdapterCommand` carries the adapter name, the `argv` tuple, the original task string, and the resolved repository path.

## The two supported shapes

Most local coding-agent CLIs accept a task in one of two ways, so RunLedger ships one adapter per shape:

| Adapter | CLI shape | Example |
|---|---|---|
| `PromptArgumentAdapter` | task as a final argument | `agent --yes "fix the bug"` |
| `PromptFileAdapter` | task as a file path flag | `agent --prompt-file task.md` |

Both are configured with an executable and optional fixed arguments; the prompt-file adapter also takes the prompt flag name. Configure them for the CLIs you actually use — the adapters stay generic so RunLedger endorses no specific tool.

## Validation rules

`validate_adapter_command` rejects:

- an empty adapter name, empty argv, or empty repo;
- shell metacharacters (`; & | < > \` $ ( )`) in the executable or fixed arguments — the task payload itself is always passed as data, never parsed.

`PromptFileAdapter` additionally requires the prompt path to be relative and free of `..` components, so a task cannot escape the run boundary.

## Conformance

`conformance_check(adapter, task, repo)` verifies that `build` is deterministic, that metadata matches the request, and that validation passes. The milestone test suite additionally records commands built by both adapters and asserts they produce the **same event contract**: identical event types in identical order with identical payload key sets. Two adapters that disagree on the event vocabulary cannot both claim conformance.

## Boundary

Adapters do not evaluate prompts, judge agent quality, or inspect model reasoning. They turn a task into an observable `argv`; everything after that — execution, capture, redaction, verification — belongs to the recorder and the contract checker.
