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

Build the replay data with `./.venv/bin/python scripts/build_replay_visualizer.py`, then open [the EEG visualizer](visualizations/eureka-replay.html). It displays an entire included or uploaded CSV at once, with selectable theta, alpha, and beta filtered traces.

## Muse live visualizer

Start a MuseLSL stream, then run `./scripts/muse-live`. The service discovers
the LSL `EEG` stream, uses its reported sample rate, and emits 125 ms updates
with elapsed seconds, alpha index, clean channels, artifact state, and
per-channel theta/alpha/beta bandpower. Open the standalone monitor at
`http://127.0.0.1:8765` or the connected Eureka app at
`http://127.0.0.1:8765/app/`. See [the Muse LSL setup guide](MUSE_LSL.md) for
the full sequence.
