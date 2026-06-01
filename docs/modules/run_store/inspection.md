# Run Store Module Inspection

## Inspect these paths

- `teaagent/run_store.py`
- `teaagent/cli/_handlers/_agent.py`
- `teaagent/cli/_handlers/chat_repl.py`
- `tests/*run*`

## Inspection questions

- Does every run start with a durable `run_started` event?
- Is task text present?
- Are observations/context present when needed for resume?
- Are approval states represented?
- Are corrupt files counted or warned?
- Can `agent show <run_id>` distinguish missing vs corrupt?

## Failure signatures

- Resume cannot find task.
- Recent run list omits known corrupt files with no warning.
- Review has changed files but no audit chain.
- Final answer refers to a run id that `agent show` cannot read.
