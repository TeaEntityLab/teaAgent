# macOS Shortcuts / Raycast

- **Raycast script:** [raycast-daily.sh](./raycast-daily.sh) runs `teaagent daily` and opens the journal.
- **Shortcuts:** Run Shell Script action with:
  `cd "$SHORTCUT_INPUT_DIR" && teaagent daily "stand-up" --write-journal`
- Set `TEAAGENT_PROVIDER` in the shortcut environment if you skip `teaagent init`.
