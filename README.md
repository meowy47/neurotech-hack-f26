# Eureka

Eureka is an EEG-informed creative-reset coach. In a short live session, it compares two open-mode activities with a user's calm baseline and gives a practical recommendation for the next time they feel creatively stuck.

## MVP experience

```text
Open Eureka
  → 30-second calm baseline
  → 90-second open-mode meditation / mental imagery
  → 90-second free drawing
  → comparison screen
  → “Drawing was your stronger creative-reset activity today.”
  → next-time recommendation
```

The MVP adapts at the end of the session: it compares the two activities and recommends the stronger creative reset for that user today. It does not claim to measure creativity directly, induce hypnagogia, or guarantee breakthroughs.

See [the MVP specification](EUREKA_MVP.md) for product scope, UX copy, measurement guardrails, recommendation logic, and demo plan. The simulation-first and real-Muse validation protocol is in [DATA_COLLECTION_PLAN.md](DATA_COLLECTION_PLAN.md). Repository working guidance is in [AGENTS.md](AGENTS.md).

## Replay visualizer

Build the replay data with `./.venv/bin/python scripts/build_replay_visualizer.py`, then open [the replay visualizer](visualizations/eureka-replay.html). It streams the simulated session in one-second chunks at eight UI updates per second. Its live trace, alpha-response index, comparison, overlay, and recommendation all use the shared processing in `scripts/eeg_scoring.py`.
