# Stand-in brief: answer as Milo would

You are standing in for Optic Terminal's assistant, Milo, to evaluate a prompt change without a paid API call.
For each case file you are given (`out/<label>/<ID>.json`), read the JSON: `system` is the list of system-prompt
blocks (in order) and `messages` is the conversation; the last user message carries a CONTEXT block (the
terminal's data) followed by the reader's question.

Answer that last message exactly as the assistant described by those system blocks would: follow every
instruction in them (length, structure, tags like [[src KEY]], follow-up lines), use only the data in CONTEXT,
and do not use any tool, file or knowledge outside the JSON for facts about the market or the company (general
knowledge of how finance works is fine). If the system blocks tell you to cite web sources, note that web search
is OFF for this answer.

Write each answer, and nothing else, to `answers/<label>/<ID>.md`. Do not read any other case's answer, any other
label's files, or anything else in this folder. Reply "done" with the list of files written.
