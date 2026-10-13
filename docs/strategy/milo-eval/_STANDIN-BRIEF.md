# Stand-in brief: answer as Milo would

You are standing in for the production model behind Milo, the AI assistant in Optic Terminal, so we can
compare answers produced from two versions of its instructions. Fidelity matters more than quality:
answer exactly as an assistant that has been given the request would, no better and no worse.

For each case file you are assigned (`out/<label>/<ID>.json` under
<workdir>/milo-eval/):
1. Read it. `system` is a list of system-prompt blocks: treat their concatenation as your system prompt and
   follow it fully. `messages` is the conversation; the final user message contains a CONTEXT block (the
   terminal's data) followed by the reader's question. Earlier messages are prior turns.
2. Write ONLY the assistant's reply to the final user message, in the format that system prompt asks for
   (including any follow-up lines, action tags or source tags it asks for). No preamble, no notes to me.
3. Do not use web search or any tool except Read and Write. Web search is not enabled for these requests.
   Do not use knowledge of what today's real market data is; use only the CONTEXT and general knowledge,
   as the system prompt allows.
4. Save the reply to `out/<label>/responses/<ID>.md` (create the folder if needed).

Do not read any other case's files, the other label's folder, cases.py, or anything outside your assigned
files. Do not edit anything else. When done, reply with just the list of files you wrote.
