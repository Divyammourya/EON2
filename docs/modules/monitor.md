# Monitor Module

The Monitor module observes execution outcomes and ambient computer state.

## Responsibilities

- Summarize execution results after EON performs a plan.
- Produce ambient signals for things EON notices without a prompt.
- Keep awareness sources small and independent.

## Ambient Awareness

Ambient awareness currently supports:

- Upcoming calendar events.
- Newly completed files in the Downloads folder.
- Visible Windows apps that appear to be not responding.

The monitor only detects signals. Proactive decides when and how to speak them.

Calendar awareness only runs when Google credentials are already cached, so ambient checks do not open an OAuth browser on their own.
