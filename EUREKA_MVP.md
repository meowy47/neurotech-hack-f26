# Eureka MVP — Live Creative-Reset Coach

## Product statement

Eureka is an EEG-informed creative-reset coach for people who feel stuck after long periods of focused work. In one short live session, it establishes a calm personal baseline, guides the user through two open-mode activities, compares their EEG response, and recommends the activity that was the stronger creative-reset option for that user today.

The user does not leave with an abstract brainwave graph. They leave knowing which short reset to try when they next need fresh possibilities.

## The problem

Someone can spend hours locked into a task without making a meaningful leap. Good ideas often surface after stepping away—while walking, doodling, relaxing, or letting attention loosen. People may know that breaks help, but they do not know which kind of reset works best for them at a given moment.

Eureka makes that experimentation intentional. Instead of telling everyone to meditate, draw, or take a walk, it runs a small experiment on the individual and turns it into a practical next-time recommendation.

## What Eureka is—and is not

### It is

- A short live experience that compares two creative-reset activities.
- Personalized: the comparison is against the user's own calm baseline.
- EEG-informed: it uses an exploratory EEG profile associated with divergent thinking to inform its recommendation.
- Actionable: its main output is a simple activity recommendation for the next creative block.

### It is not

- A way to measure creativity, originality, or insight directly.
- A promise of more ideas, better ideas, or a breakthrough on demand.
- A system for inducing hypnagogia or replicating sleep onset while awake.
- A general focus/productivity coach or a multi-mode neurofeedback platform.
- A diagnostic, therapeutic, or medical product.

Hypnagogia can remain in the opening story: many people recognize the feeling of an idea arriving after they stop forcing a problem. It must not be presented as the state Eureka creates or detects.

## MVP goal

Deliver one credible and memorable result:

> “Of the two creative resets you tried today, this was the stronger one for your EEG profile. Try it first the next time you feel stuck.”

The MVP should prove that the experience is understandable, enjoyable, and personally useful—not that a universal creativity biomarker has been solved.

For this version, adaptation happens **after both activities**: the session uses the comparison to choose a personalized next-time reset. It does not yet change an activity while it is underway.

## Core user and use case

**Primary user:** a student, maker, designer, founder, or knowledge worker who has spent a long time concentrating and feels mentally narrow or blocked.

**Moment of use:** a short break between focused work sessions, ideally no more than five minutes.

**User job:** “Help me choose a quick reset that makes me feel more open to possibilities when I return to my work.”

## MVP session flow

```text
Open Eureka
  → 30-second calm baseline
  → 90-second open-mode meditation / mental imagery
  → 90-second free drawing
  → compare each activity with the personal baseline
  → show today's stronger creative-reset activity
  → save a next-time recommendation
```

### Welcome

**Headline:** “Find your best creative reset.”

**Supporting copy:** “In four minutes, Eureka compares two open-mode exercises with your personal baseline and recommends one to try when you feel stuck.”

**Primary action:** “Start session”

### Calm baseline: 30 seconds

**Headline:** “Settle into your baseline.”

**Instruction:** “Sit comfortably. Keep your eyes softly open, your face relaxed, and your body still. There is nothing to solve.”

Use a simple countdown and a signal-quality indicator. Do not describe the baseline as a creativity score.

### Open mode: 90 seconds

This activity can be framed as open-monitoring meditation with mental imagery.

**Headline:** “Open the frame.”

**Instruction:** “Let thoughts come and go without following them. Imagine a place you have never visited. Notice its textures, sounds, and strange details. There is no right answer.”

The user stays still and quiet. This offers the cleanest active comparison window of the two exercises.

### Free drawing: 90 seconds

**Headline:** “Draw without a plan.”

**Instruction:** “Fill the space with lines, shapes, or fragments. Do not erase or judge it. Keep moving until the timer ends.”

Input is typed only when the application needs a label or reflection. The MVP does not record speech, because speech can create muscle artifacts in EEG data.

### Comparing your session

**Headline:** “Your creative-reset comparison”

Show the two activities and their relative session result. Prefer an intuitive bar, ring, or two-column comparison over raw frequency charts. If a score is shown, label it as a relative response to the user's baseline.

**Supporting copy:** “These signals are an exploratory, personal proxy—not a direct measure of creativity.”

### Recommendation

**Example result:** “Drawing was your stronger creative-reset activity today.”

**Next-time recommendation:** “When you feel stuck, try a 90-second free-draw before returning to the problem.”

**Secondary action:** “Save recommendation” or “Try another session.”

## Measurement approach and language

The app should measure an individualized, exploratory EEG response associated with divergent thinking. It does not detect a discrete “creative state.”

### Recommended framing

- Compare each activity with the user's calm baseline.
- Use 8–12 Hz alpha power as the sole exploratory signal. Alpha has been associated with divergent ideation in some research contexts.
- Do not add secondary-band claims to the MVP.
- Keep comparisons within the same session whenever possible.
- Use wording such as “stronger creative-reset response today” or “stronger association with your divergent-thinking EEG profile.”

### Avoid

- “We detected creativity.”
- “This activity made you more creative.”
- “Your clean alpha waves prove you are in open mode.”
- “Eureka induces hypnagogia.”
- “This guarantees an aha moment.”

### Signal-quality caveat

Free drawing creates movement and eye-motion artifacts. For the most defensible prototype, reserve a brief still, quiet interval immediately after each exercise for scoring, or mark the drawing result as lower confidence when the signal is noisy. The app should never transform low-quality data into a confident-sounding personal conclusion.

## Recommendation logic for the prototype

1. Record a 30-second calm baseline.
2. Record the meditation/imagery window, subject to basic signal-quality checks.
3. Run the drawing activity and, if possible, score a short quiet post-drawing window to reduce motion artifacts.
4. Compute each activity's relative response against the baseline using the same processing and time-window conventions.
5. Choose the higher-confidence result.
6. Present a recommendation only when the difference and signal quality meet a defined threshold; otherwise say the session was inconclusive and invite a repeat.

**Inconclusive-state copy:** “Today’s signals were too similar to pick a clear winner. Try another short session when you are settled and still.”

The ranking is session-level in the MVP. Future sessions may aggregate results, but do not imply durable personalization until enough sessions exist.

## Data captured in the MVP

| Data | Purpose | User-facing output |
| --- | --- | --- |
| Calm baseline EEG | Personal reference point | Not scored as good or bad |
| Open-mode session EEG | First activity comparison | Relative response |
| Drawing / post-drawing EEG | Second activity comparison | Relative response and confidence |
| Signal-quality flags | Avoid misleading results | Retry or low-confidence state |
| Optional typed reflection | Help user remember the session | Personal note, not EEG evidence |

Do not capture spoken ideas in the MVP.

## Demo narrative

1. Start with the familiar experience: “Have you ever forced a problem all day, then thought of something useful only after you stopped trying?”
2. Explain that Eureka does not promise to manufacture breakthroughs. It helps people discover their own most useful reset.
3. Put on the EEG device and take the 30-second baseline.
4. Complete mental imagery/open monitoring and free drawing.
5. Show a simple comparison rather than raw neuroscience instrumentation.
6. Land on the recommendation: “Drawing was your stronger creative-reset activity today. Next time you are stuck, draw for 90 seconds first.”
7. Close with the differentiator: “Most neurofeedback apps display a score. Eureka turns a short session into a practical decision about what to do next.”

## Non-goals for this MVP

- Focus mode or attention training.
- More than two activities.
- Real-time adaptation during an activity.
- Spoken transcription or voice-driven idea capture.
- A broad activity marketplace or long task bank.
- Claims about clinical outcomes, sleep, diagnosis, or treatment.
- Claims that the result is a validated measure of creativity.

## Success criteria

The MVP succeeds if a first-time user can:

1. Complete the session without coaching from the team.
2. Explain what Eureka compared and why the recommendation is personal.
3. State the activity they should try during their next creative block.
4. Understand that the result is a helpful experiment, not proof that one activity universally makes people creative.

## Later, not now

After validating the two-activity experience, future work could add repeated-session aggregation, a broader library of carefully controlled activities, context-aware recommendations, and gentler within-session adaptation. Those are deliberately outside the final MVP so the core comparison remains clear and credible.
