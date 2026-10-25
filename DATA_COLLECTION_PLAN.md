# Eureka — Minimal Data Collection Plan

## Decision

For the MVP, run **one simulated experiment suite** and **one real Muse
validation protocol**. The real protocol is repeated across people or sessions;
it is not a separate study for every activity or product claim.

The goal is not to prove that either exercise makes people creative. The goal
is to determine whether the simulation's assumptions about clean signal,
artifacts, relative activity scores, and an inconclusive state hold up against
real Muse 2 recordings.

## The only product flow to test

```text
30 s calm, eyes-open baseline
  → 90 s guided open monitoring / mental imagery
  → 90 s free drawing
  → 20–30 s still, quiet post-drawing window
  → compare and recommend, or return “inconclusive”
```

The quiet post-drawing window is the preferred score window for drawing. It
does not need to appear as a separate user-facing exercise; it can simply say,
“Pause and notice what you made.”

## Experiment S — simulation suite (crucial for the POC)

This is the only experiment required to build the product before real hardware
data is collected. Simulations drive the UI, recommendation algorithm, demo,
and automated checks.

Generate the same session flow above with a user-specific baseline and four
deterministic scenarios:

| Scenario | Expected result | Why it is required |
| --- | --- | --- |
| Imagery stronger | Recommend imagery | Proves the comparison is not hard-coded for drawing. |
| Drawing stronger | Recommend drawing | Supports the intended demo result. |
| Responses too close | Inconclusive | Prevents a false winner when the difference is trivial. |
| Drawing contaminated by motion/noise | Low-confidence or inconclusive | Verifies artifact gating and honest failure handling. |

Each simulated fixture should include baseline drift, ordinary window-to-window
noise, and signal-quality flags. The contaminated-drawing fixture should
include a brief quiet post-drawing window so the algorithm can demonstrate the
difference between movement noise and a scorable interval.

### What simulations must produce

- Segment markers for baseline, imagery, drawing, and post-drawing stillness.
- 8–12 Hz alpha-power values against the same user's median eyes-open baseline.
- Clean/noisy flags and a confidence value for each activity.
- One expected result for automated testing: imagery, drawing, or inconclusive.
- A deterministic replayable session for the demo.

Do not use simulations to set scientific thresholds or claim that the model
detects creativity. Use them to verify product behavior under known inputs.

Generated fixtures and their expected labels live in `data/simulated/`. Run
`./.venv/bin/python scripts/generate_simulated_eeg.py` to regenerate them from
the quieter real AF7/TP10 recordings, then
`./.venv/bin/python scripts/score_simulated_eeg.py --verify` to confirm that
the raw-signal artifact gate and scoring rule reach the expected result.

`./.venv/bin/python scripts/build_replay_visualizer.py` packages the same
per-window results for `visualizations/eureka-replay.html`; it never maintains
a separate chart-only score or recommendation path.

## Experiment M — real Muse validation (crucial in the final five hours)

Run the exact MVP flow with real Muse 2 data. This is **one protocol**, repeated
with several people or repeated sessions—not a twelve-activity ranking study.

### Per-participant preflight (not a product experiment)

1. Verify sensor contact and streaming.
2. Record 30 seconds eyes open, still.
3. Record 30 seconds eyes closed, still.
4. Confirm that eyes-closed alpha is visibly higher than eyes-open alpha.
5. Do one 10-second blink/motion check to establish what obvious artifact looks
   like for that recording.

The eyes-closed recording is a pipeline sanity check only. It is not compared
with the eyes-open activities and must never trigger the app's recommendation.

### Real validation trial

1. Mark and record the 30-second eyes-open baseline.
2. Mark and record 90 seconds of guided open monitoring / mental imagery.
3. Mark and record 90 seconds of free drawing. No talking.
4. Mark and record 20–30 seconds of still, quiet post-drawing observation.
5. Run the same scoring pipeline used by the simulations.
6. Save the result as imagery, drawing, or inconclusive, plus signal-quality
   notes and percentage of clean windows.

### Minimum and recommended repetitions

| Level | Collection | Purpose |
| --- | --- | --- |
| Absolute minimum | One clean end-to-end real trial | Confirms streaming, markers, segmentation, and basic artifact handling. |
| Required hackathon target | Three participants, one trial each | Shows whether the simulated pipeline remains honest across people. |
| Only if time remains | A second trial per participant with activity order reversed | Checks whether the result is dominated by exercise order or settling over time. |

The production/demo flow remains imagery first, then drawing. Reversing order is
a validation control, not a proposed UX change.

## What to keep, merge, or cut from the original plan

| Original item | Decision | Where it belongs now |
| --- | --- | --- |
| Setup, pairing, marker/export dry run | Keep | Muse preflight; required before collecting anything. |
| Part A: sustained work, fatigue probes, break alert | Cut | Different product (focus/break-alert); not needed for this MVP or simulations. |
| B1 eyes-open fixation | Keep, shorten to 30 s | Product baseline in every simulated and real trial. |
| B2 eyes-closed rest | Keep only as 30 s Muse sanity check | Confirms basic alpha pipeline; not a product comparison. |
| B3 phone scrolling | Cut | Does not answer the two-exercise recommendation question. |
| Blink/jaw/talking artifact check | Keep, shorten | One 10-second Muse preflight check; no talking in scored trials. |
| C1 typed unusual uses | Cut | The MVP does not use this exercise. |
| C2 unusual uses with music | Cut | Adds a second manipulated variable and is outside scope. |
| C3 mental imagery + C4 open monitoring | Merge | One 90-second guided imagery/open-monitoring activity. |
| C5 creative sketching | Keep, rename | The 90-second free-drawing activity. |
| C6 rhythm tapping | Cut | Unnecessary and likely noisy for the Muse sensors. |
| F1–F6 focus activities | Cut | Focus mode is not in the final MVP. |
| 12-activity blocks and top-three ranking | Cut | Replace with the two-activity comparison. |
| Behavioral performance scores | Cut as a required metric | Optional one-question reflection only; this MVP does not claim more or better ideas. |
| Closing baseline / drift study | Optional only | Use if the signal looks unstable; otherwise start-of-trial baseline is enough. |
| Brain-vs-behavior correlation | Cut | Sample is too small and it does not validate the product claim. |
| Example traces and usable-data percentage | Keep | Use in the demo and to explain confidence/inconclusive results. |

## Minimal scoring and decision rule

Use one consistent 8–12 Hz alpha-power score for both activities:

1. Band-pass filter the recording, then divide it into short overlapping windows.
2. Reject windows with clipping, unusually high amplitude, or abrupt movement-like changes.
3. Calculate alpha power independently for every usable channel.
4. Compare each activity with the median eyes-open baseline.
5. Score imagery from its quiet active window.
6. Score drawing mainly from the quiet post-drawing interval; record the drawing-window clean-data rate separately.
7. Combine only clean channels using their median, never a blind all-channel average.
8. Recommend an activity only if both sides have enough clean windows and the difference exceeds a predeclared demo margin; otherwise return inconclusive.

Treat all thresholds as configurable demo defaults. Do not tune them until they
fit three people and then present them as a validated creativity classifier.

## Five-hour real-data schedule

| Time | Work |
| --- | --- |
| 0:00–0:30 | Fit check, streaming, markers, export/import, and one dry run. |
| 0:30–1:00 | First participant preflight and one validation trial; inspect the recording before continuing. |
| 1:00–2:30 | Two additional participant trials; fix contact or marker problems immediately. |
| 2:30–3:30 | Optional second trials with reversed order, if the first three are clean. |
| 3:30–4:15 | Compare clean-window rates and real signal behavior with the simulated fixtures; adjust artifact flags or confidence handling only. |
| 4:15–5:00 | Save one replayable real trace, retain deterministic simulation fallback, and rehearse the demo. |

## Success criteria

The collection is successful when:

1. The Muse stream, markers, and segmentation work end to end.
2. Eyes-closed alpha is higher than eyes-open alpha in the preflight recording.
3. The system correctly identifies or rejects drawing movement artifact.
4. Every real trial produces either an honest recommendation or an honest
   inconclusive result.
5. The same software can replay a deterministic simulated session if live
   hardware becomes unreliable.

Do not treat a three-person hackathon sample as evidence that one activity
works universally or that 8–12 Hz alpha power measures creativity.
