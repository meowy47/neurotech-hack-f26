# Eureka — repository context

## Product in one sentence

Eureka is an EEG-informed creative-reset coach. It guides a user through two short open-mode activities, compares each activity with the user's calm baseline, and recommends the stronger reset for the next time they feel creatively stuck.

## Final MVP scope

The MVP is one brief, session-level experiment:

```text
Open Eureka
  → 30-second calm baseline
  → 90-second open-mode meditation / mental imagery
  → 90-second free drawing
  → comparison screen
  → personalized next-time recommendation
```

- Adaptation occurs **after** both activities: the comparison selects a recommendation. Do not change an activity mid-session.
- Keep the activity set to mental imagery/open monitoring and free drawing. Do not add focus mode, walking, unusual-uses prompts, a cue bandit, or an activity library unless the owner expands scope.
- Typed input is the only text-entry method if a label or reflection is needed. Do not add voice capture, transcription, or spoken idea capture.
- The session should remain under five minutes and have a clear inconclusive state.

## Product boundaries

- Do **not** say Eureka measures, diagnoses, or improves creativity.
- The only exploratory signal in this MVP is 8–12 Hz alpha power associated with divergent thinking—not a creativity score, a universal “creative brainwave,” or a medical measurement.
- A result is “stronger creative-reset response today” or “early evidence for this session,” not proof of a durable personal preference.
- Do not claim the app induces hypnagogia, causes insight, or guarantees an aha moment. Hypnagogia may be used only as a relatable opening story.
- Treat the app as a wellness/productivity prototype, never as medical, clinical, diagnostic, or therapeutic software.

## Core user outcome

Users open Eureka when they feel mentally narrow or creatively stuck. A completed session should leave them with:

1. A simple comparison of the two exercises against their own baseline.
2. One clear creative-reset recommendation for the next time they feel stuck.
3. An honest inconclusive result when the signals are too similar or noisy.

Prioritize a practical next action over raw neuroscience visualizations.

## Experience principles

- Keep the participant UI calm, sparse, and encouraging. Show one instruction at a time.
- Use a simple countdown and signal-quality indicator during the baseline; do not label it a creativity score.
- Make the meditation/imagery activity still and quiet; this is the cleaner active comparison window.
- Present the drawing prompt without judgment: “Fill the space with lines, shapes, or fragments. Do not erase or judge it.”
- Never characterize a low or shifting signal as failure. Use neutral language such as “Your signals were too similar to pick a clear winner today.”
- On the result screen, prefer an intuitive two-column comparison over raw frequency charts.
- Always label results as an exploratory, personal proxy—not a direct measure of creativity.

## Signal handling

- Compare both activity measurements against the same user's 30-second calm baseline using the same processing conventions.
- Use only 8–12 Hz alpha power; do not add secondary-band claims.
- Filter into short overlapping windows. Reject clipping, unusually high amplitude, and abrupt movement-like changes before scoring.
- Compute alpha power per usable channel and use the median of clean channels; do not blindly average all four channels.
- Free drawing can create movement and eye-motion artifact. When feasible, score a brief still, quiet period immediately after drawing; otherwise lower confidence or return an inconclusive result.
- Do not turn low-quality data into a confident recommendation.
- Keep the EEG/signal service and UI independently runnable. A fake state generator must support end-to-end UI work without live hardware.

## Result language

Use:

- “Drawing was your stronger creative-reset activity today.”
- “When you feel stuck, try a 90-second free draw before returning to the problem.”
- “Today’s signals were too similar to pick a clear winner. Try another short session when you are settled and still.”

Avoid:

- “We detected creativity.”
- “Drawing made you more creative.”
- “Your alpha waves prove you are in open mode.”
- “Eureka induced hypnagogia.”

## Build priorities

1. Build the complete mocked flow: welcome → baseline → imagery → drawing → comparison → recommendation/inconclusive result.
2. Add a fake EEG state generator and signal-quality states.
3. Render an honest two-activity comparison and personalized recommendation.
4. Integrate the real headset, artifact gating, and threshold tuning.

Do not add a backend, authentication, cloud sync, persistent user profiling, focus/productivity mode, or additional exercises unless explicitly requested.

## Reference document

The complete product specification is [`EUREKA_MVP.md`](EUREKA_MVP.md). The required simulation-first and final-five-hour Muse protocol is [`DATA_COLLECTION_PLAN.md`](DATA_COLLECTION_PLAN.md). Keep interface copy, implementation decisions, data collection, and demos aligned with them.
