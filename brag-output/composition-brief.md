# Hyperframes Composition Brief: CV Application Manager

## Objective
Create a short, voiced launch-style brag video for CV Application Manager — a local-first job-application tracker whose CV/cover-letter generation pipeline refuses to let an AI embellish or fabricate a claim.

## Output
- Composition directory: `brag-output/composition/`
- Rendered video: `brag-output/brag.mp4`
- Format: landscape — 1920x1080
- Duration: ~19-21s target — **voiceover is present, so final scene timing must flex to match the generated narration audio's actual duration** (check the WAV length after TTS generation and set `data-duration` accordingly; do not force the audio into pre-set scene lengths)

## Source Material
- Project root: `/Users/wiktor/Projects/cv-application-manager`
- Primary files read: `README.md`, `docs/pipeline_overview.md` (full 7-stage pipeline spec), `frontend/src/index.css` (real visual identity), `frontend/src/pages/JobDetailPage.tsx` (real step-list / generation-row UI pattern)
- Product name: CV Application Manager
- Tagline / strongest claim: "Every claim in every generated document traces back to a real, cited fact... built to make things up *never*, not 'rarely.'" — dramatized in the video as the fact-check-and-revert moment.
- Key UI or visual moment to recreate: the real generation step-list pattern (`.step-item` / `.step-icon`: spinner while running, green check on success, red on failure) ticking through pipeline stages after "Generate CV" is pressed; and a CV bullet getting fact-checked and reverted from an embellished draft to its real sourced text.
- Copy that must appear verbatim (English — the app's UI and docs are in English):
  - "Every AI résumé tool wants you to sound like a superhero." (hook line, written for this video)
  - "This one's not allowed to." (written for this video)
  - "Generate CV" (real button label)
  - Stage labels: "analyzing", "matching", "drafting", "fact-check", "render" (compressed/short-form of the real pipeline stages: analyzing, matching, drafting, fact_checking, ats_checking, style, rendering — see docs/pipeline_overview.md; 5 labels chosen for on-screen pacing, not all 7)
  - Example embellished bullet: "Singlehandedly scaled infrastructure to serve millions." (illustrative, written for this video, in the voice of typical CV puffery)
  - Example real/reverted bullet: "Reduced infra costs 12%, per Q3 report." (illustrative, written for this video, in the deliberately modest, cited-fact style the real pipeline produces)
  - "The CV generator that won't cover for you." (outro line, written for this video)

## Creative Direction
- Tone preset: default
- Creative direction: user asked to "podkręcić, niech się fajnie dzieje i ładnie" (jazz it up, make it happen nicely, make it look good) and "trochę śmiesznie" (a little funny). The humor comes from the product's own obsessive honesty (an AI résumé tool that refuses to let you exaggerate), not from mocking the user, the format, or generic gag devices.
- Interpretation: warm, first-person-plural narration voice; comfortable, confident pacing (not chaotic, not deadpan-slow); generous whitespace and confident type scale — more polished than the literal cramped dev-tool table view, but staying inside the app's real palette; clean crossfade/slide transitions.
- Angle: Every other AI résumé tool exists to inflate you. This one is structurally incapable of lying for you — show that live: the pipeline catching and reverting an embellished bullet, not just claiming honesty in text.
- Hook: "Every AI résumé tool wants you to sound like a superhero." → "This one's not allowed to."
- Outro / punchline: CV Application Manager wordmark → "The CV generator that won't cover for you."
- Avoid:
  - Generic SaaS language — use only the real product behavior and the copy listed above
  - Abstract filler visuals — the step-list flow and the embellish→revert catch must be real recreated UI moments, not diagrams
  - Mocking tone toward the user or toward job-seekers generally — the joke is the product's own strictness, told affectionately

## Visual Identity
- Background: `#ffffff`, secondary panel tint `#f6f6f8`
- Text: `#1a1a1e` primary, `#666666` muted/labels
- Border: `#d0d0d5`
- Accent/CTA: `#0b5fff` (the app's real link/accent blue)
- Success state: `#1e6b30` text on `#e6f6ea` bg, `#8fd19e` border (real "succeeded"/"applied" badge colors)
- Failure state: `#8a1f1f` text on `#fdeaea` bg, `#f0a3a3` border (real error-state colors)
- Display font: system sans (`-apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif`) — Inter or a clean system stack as fallback
- Body font: same family, lighter weight
- Visual references from the project: the spinner→check/✗ step-list pattern; the success/failure badge treatment; the plain, confident, no-nonsense dev-tool aesthetic — elevate with more space and scale, don't redesign the brand away from it

## Storyboard
Use the storyboard in `brag-output/brag-plan.md` as the creative contract. Scene durations there are starting points — flex all of them to match the generated voiceover audio's real timing.

Scene summary:
1. Hook — ~2.5s (flex) — "Every AI résumé tool wants you to sound like a superhero."
2. Reveal — ~2s (flex) — "This one's not allowed to." → CV Application Manager wordmark.
3. Generate CV / pipeline flow — ~5s (flex) — button press → real step-list ticking through analyzing/matching/drafting/fact-check/render.
4. The honesty catch — ~5s (flex) — embellished bullet flagged (red/fail state) → reverts to real sourced bullet (green/success state). This is the comedic + credibility core of the video.
5. Outro — ~3s (flex) — wordmark + "The CV generator that won't cover for you."

## Audio
- Audio role: voiceover-led narration with a low, ducked music bed and sparse motion-matched SFX
- Voiceover: **enabled**. Generate via Kokoro:
  ```bash
  npx hyperframes tts "<script>" --voice af_heart --output composition/assets/voiceover.wav
  ```
  Script (5 lines, one per scene, see brag-plan.md "Voiceover script" for the exact text and rationale). Generate as one file or per-scene, whichever gives cleaner per-scene timing — your choice. After generating, read the actual WAV duration(s) and set scene/clip `data-duration` values to match; do not hardcode the plan's approximate scene lengths over the real audio length.
  Wire on its own track; music ducks to ~0.12-0.15 for the duration of the voiceover and returns to a slightly higher level only in any narration-free tail (e.g. the very end of the outro hold).
- Audio arc: near-continuous ducked bed under voice, silence-free; two SFX moments carry personality — the revert "gotcha" cue in Scene 4, and one clean payoff cue on the Scene 5 wordmark landing; everything else (stage ticks) stays quiet and sparse so it never competes with the narration.
- Music: `happy-beats-business-moves-vol-9-by-ende-dot-app.mp3` (mid-energy, laid-back — picked over vol-1 specifically because narration runs through nearly the whole video). Copy it into `composition/assets/music/` before building.
- Music treatment: start ~0.25-0.3 before narration begins (under the silent hook beat, if any leads the first VO line), duck to ~0.12-0.15 the instant voiceover starts and hold there through all 5 lines, lift toward ~0.25 only in a narration-free tail at the very end, then fade.
- Music cue guidance: no bundled cue preset exists for vol-9 in this project yet. After wiring the music in, run `npx hyperframes beats <composition-dir>` (no-Python method) to get a beat grid if you want to nudge the Scene 5 wordmark landing toward a beat; if that command is unavailable in this environment, write "unavailable; continue without beat/cue sync" and rely on the voiceover's own pacing instead — beat sync is a nice-to-have here, not load-bearing.
- Audio-reactive treatment: subtle at most — if implemented, only a slight RMS-driven glow on the wordmark in Scenes 2 and 5; never on the step-list or the fact-check catch, where clarity matters more than ambience. Skip entirely and note it if extraction is unavailable.
- Audio-coupled moments:
  - Scene 3 — each pipeline stage turning green — soft, quiet tick/click, thinned out if it starts to compete with the VO
  - Scene 4 — the bullet snapping from embellished/flagged to real/reverted — one distinct SFX with a playful "rewind/undo" character (not an error buzzer — this should read as clever, not as failure), timed to land with the VO's pause ("...reverts you")
  - Scene 5 — wordmark's final settle — one clean, understated payoff cue
- SFX selection guidance: read `~/.claude/skills/hyperframes-creative`'s sfx-analysis reference (or `hyperframes-cli`'s pointer to it) before choosing exact files; prefer low/medium high-frequency-risk files since this is a warm, voice-led piece, not a chaotic one. For the Scene 4 revert cue, look outside the standard "error" family (error_005/006 read as a fail-buzzer, which undercuts the joke) — a soft switch/glitch-lite or a reversed-feeling interface cue reads better as "clever gotcha."
- Exact SFX choice: Hyperframes should pick filenames, timestamps, density, and volume based on the implemented animation and the generated voiceover's real timing.
- Audio files: copy the chosen music and any Hyperframes-selected SFX into `brag-output/composition/assets/`; the voiceover WAV also lives there once generated.

## Hyperframes Instructions
Load the composition-building Hyperframes domain skills — `hyperframes-core` (composition contract + `data-*` timing), `hyperframes-animation` (motion), `hyperframes-creative` (design spec, beats, audio-reactive, voiceover-aware pacing), `hyperframes-keyframes` (seek-safe keyframes), and `hyperframes-cli` (lint/check/render). `/brag` is its own workflow: do not enter the `hyperframes` entry-point intent interview and do not route into its generic promo / launch-video workflow. Prefer native Hyperframes conventions over anything in `/brag`.

Requirements:
- Generate the voiceover FIRST (or early), read its real duration, and let it set scene pacing — this is a voiced video, so do not hardcode scene lengths independent of the narration audio.
- Show at least one real UI, copy, or visual element from the source project (the step-list pipeline flow, and the fact-check/revert behavior).
- Keep all text readable in the final render — respect reading-time floors even where the voiceover is faster; if VO and on-screen text pacing conflict, prioritize on-screen readability and let VO overlap slightly rather than rush text off-screen.
- Keep the video within 15-25 seconds.
- Include the planned music/SFX/voiceover layers.
- Treat `/brag` audio notes as guidance, not a fixed cue sheet; choose exact SFX after the visual animation and the real voiceover timing both exist.
- Duck music under voiceover per the treatment above; this is a hard requirement, not optional polish.
- Use SFX to support motion and interaction, with real restraint — this is a narration-led piece, most of the sonic personality should come from the voice and the one signature revert cue, not from a dense SFX layer.
- Use local asset paths only (relative to `composition/`), never absolute `/Users/...` paths.
- Run `npx hyperframes check` before render — it is brag's single gate.
