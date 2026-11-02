<!-- Saved verbatim from the owner's chat message of 2026-10-29. Do not edit; record interpretations in ../DECISIONS.md. -->

PHASE 07 — MILO STREAMING PERFORMANCE AND CONVERSATION UX REBUILD
Read all previous phase reports.
Milo is a core part of Optic's product identity.
Current investor-demo feedback indicates that Milo's response rendering feels laggy compared with leading conversational AI applications.
Your objective is to deliver smooth, reliable, genuinely incremental AI responses and intuitive conversation management.
Do not merely add animations to hide slow behavior.
Investigate the underlying pipeline.
1. End-to-end latency investigation
Trace a message through:

1. User submission.
2. Frontend request creation.
3. Backend routing.
4. Authentication and session checks.
5. Context construction.
6. Tool execution, when required.
7. Model provider invocation.
8. First response event.
9. Streaming transport.
10. Frontend chunk processing.
11. State updates.
12. Markdown rendering.
13. Auto-scroll.
14. Response completion.

Measure available metrics such as:

* Time to first visible response.
* Time to first model token.
* Total response duration.
* Streaming event frequency.
* Client rendering overhead.
* Excessive component re-renders.
* Tool execution delays.

Use actual measurements.
Do not fabricate benchmarks.
2. Streaming architecture
Determine whether the current backend supports genuine token or text-delta streaming.
If supported, implement reliable incremental streaming.
Investigate whether SSE, fetch streaming, WebSockets, or the existing transport is appropriate.
Do not replace a working architecture without justification.
Requirements:

* Text begins displaying as soon as valid streamed content arrives.
* Chunks appear in order.
* Unicode and Markdown are handled correctly.
* Client state is updated efficiently.
* Rendering does not block input.
* The user can scroll while streaming.
* Streams terminate correctly.
* Network failures produce useful feedback.
* Aborted requests do not continue mutating the UI.

Do not fake streaming by holding completed responses and revealing them character by character.
3. Smooth rendering
Eliminate:

* Text appearing in huge irregular blocks unnecessarily.
* Flickering.
* Repeated paragraph re-rendering.
* Jumpy markdown formatting.
* Entire messages disappearing and reappearing.
* Scroll snapping.
* Excessive typing delays.
* Main-thread blocking.
* Duplicate responses.
* Stuck thinking states.

Use appropriate rendering optimization and bounded update batching.
Preserve fast access to actual streamed content.
4. Thinking and tool-execution states
Create subtle, truthful states such as:

* Processing your question.
* Looking up market data.
* Reviewing available information.
* Generating response.

Only display an activity label when the corresponding activity is actually taking place.
Do not expose hidden model reasoning.
Do not fabricate tool use.
Use restrained animation.
5. New Chat control
Add an obvious New Chat button.
Required behavior:

* Starts a distinct conversation.
* Clears active chat messages from the visible new conversation.
* Starts a clean conversation context.
* Does not accidentally preserve the previous chat's conversational instructions.
* Does not delete saved conversation history.
* Avoids duplicate chat creation when clicked repeatedly.

6. Close Chat control
Add an X button to close or minimize Milo.
Required behavior:

* Closes the Milo panel.
* Does not unexpectedly delete history.
* Does not corrupt the current conversation.
* Restores appropriate state when reopened.
* Handles an in-progress stream predictably.

Distinguish close, new chat, and delete actions.
7. Conversation persistence
Inspect whether saved conversation history is already supported.
If supported:

* Ensure conversations are associated with the correct authenticated user.
* Prevent cross-user access.
* Support correct history retrieval.
* Handle missing or deleted conversations.
* Maintain accurate conversation IDs.
* Avoid mixing messages across sessions.

If persistence is not supported, document the required architecture and implement safe local behavior without inventing a production database solution.
8. Composer audit
Test:

* Enter to submit.
* Shift+Enter for newline, where appropriate.
* Empty submission.
* Large messages.
* Paste behavior.
* Rapid submissions.
* Disabled state.
* Duplicate submission prevention.
* Network failure.
* Retry.
* Stop generating, where supported.
* Keyboard focus.
* Mobile layout.

9. Scroll behavior
While streaming, auto-scroll only when the user is at or near the bottom of the conversation.
If the user scrolls upward, do not repeatedly force the view downward.
Provide an unobtrusive way to return to the latest response.
10. Knowledge-level integration
Milo must honor the preference established in Phase 05.
Changing knowledge level affects subsequent responses.
It must not alter stored market facts or invalidate existing conversation records.
11. Tests
Create reproducible tests for:

* Successful streaming.
* Stream cancellation.
* Network interruption.
* Partial responses.
* Tool call delays.
* Multiple consecutive chats.
* New Chat.
* Close Chat.
* Reopen Chat.
* Conversation restoration.
* User isolation.
* Rapid submissions.
* Long responses.
* Markdown.
* Mobile layout.
* Scroll control.

Collect before-and-after performance measurements where possible.
Completion gate
Streaming is genuinely incremental.
Visible output is smooth.
Milo remains responsive.
New Chat works.
Close Chat works.
Conversation state is consistent.
No critical regressions remain.
Report actual latency measurements and tests performed.
