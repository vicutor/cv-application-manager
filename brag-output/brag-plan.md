# Brag Plan: CV Application Manager

## What is this app?
A local-first tool that imports job postings and generates tailored CVs and cover letters through a 7-stage Claude+LaTeX pipeline where every single claim has to trace back to a real, cited fact in your profile — if the model embellishes or can't prove something, the app reverts or fails the generation instead of quietly "fixing" it.

## The angle
Every other AI résumé tool exists to make you sound more impressive than you are. This one is built with the opposite instinct: it is structurally incapable of lying for you. The joke (and the flex) is the same thing — show the pipeline actually catching an AI-embellished bullet and reverting it back to the boring, true version, live on screen. Funny because it's a superpower nobody asked for, impressive because it's real engineering (deterministic fact-check, deterministic revert, hard-fail rather than "retry and hope").

## Hook (first 2-3 seconds)
"Every AI résumé tool wants you to sound like a superhero." — plain, confident type on a clean white field. Sets up the twist before the product ever appears.

## Key moments (the middle)
- The real "Generate CV" flow: button press → the actual 7-stage step list (analyzing → matching → drafting → fact-check → render) ticking from spinner to green check, one by one — this is the app's real UI pattern (`.step-item` / `.step-icon`), not an invented diagram.
- The honesty catch: a drafted bullet appears reading like typical CV puffery ("Singlehandedly scaled infrastructure to serve millions"), gets a red fact-check flag, and snaps back to the real sourced line ("Reduced infra costs 12%, per Q3 report") with a green check. This is the app's actual `fact_checking` → deterministic revert behavior, dramatized as one visible before/after beat.
- One quiet stat/line reinforcing it's not a gimmick: "Every claim traces to a real fact. No retries. No fixing it later — reverted, every time."

## Outro / punchline
CV Application Manager wordmark, then: "The CV generator that won't cover for you." Local-first, honest, done.

## User flow worth showing
1. Entry: user clicks "Generate CV" on a job posting already in the system.
2. Key action: the pipeline runs — visible stage-by-stage (this is the app's real generation-events step list UI).
3. Result: a bullet the model oversold gets caught and reverted to the real fact before the CV is ever rendered.
This is the centerpiece — Scenes 3 and 4 show the product actually doing this, not a landing-page claim about it.

## Tone
- Preset: default
- Creative direction (user-specified, freeform): "podkręć, niech się fajnie dzieje i ładnie" (jazz it up, make it happen nicely, make it look good) + "trochę śmiesznie" (a little funny). Mapped to `default`: playful and clean, humor comes from the product's own obsessive honesty, not from mocking the user or the format.
- Interpretation: warm, first-person-plural voice in the narration; comfortable pacing (not chaotic); confident, generously-spaced typography using the app's own restrained palette but treated with more visual polish/whitespace than the literal dev-tool UI; crossfade/slide transitions, nothing aggressive.

## Format: landscape — 1920x1080
## Duration: ~19-21s target (voiceover present — see Audio direction; scene durations below are a starting point and must flex to match the generated narration's actual length per audio.md)

## Visual identity (from the project)
- Background: `#ffffff` (site/app body bg)
- Secondary panel tint: `#f6f6f8` (`--bg-subtle`)
- Text: `#1a1a1e` (primary body/heading text)
- Muted text: `#666666` (`--muted`, used for labels/timestamps)
- Border: `#d0d0d5` (`--border`)
- Accent / link: `#0b5fff` (the app's actual link color — use as the primary CTA/accent)
- Success: `#1e6b30` on `#e6f6ea` (bg), border `#8fd19e` (the app's real "succeeded"/"applied" state color)
- Failure: `#8a1f1f` on `#fdeaea` (bg), border `#f0a3a3` (the app's real "failed"/error state color)
- Display font: system sans (`-apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif` — the app's actual stack); a clean system/Inter fallback is fine
- Body font: same system sans stack, lighter weight
- Strongest visual element: the real step-list pattern (spinner → green check / red X per pipeline stage) and the success/failure badge colors — these are the app's actual UI language, not invented; lean into them with more breathing room and confident scale than the literal cramped table view

## Share copy (draft)
Built a CV generator with an AI that's structurally not allowed to lie about you. Every bullet traces to a real fact — try to embellish one, and it just reverts to the boring, true version.

## Audio direction
- Role: warm voiceover-led narration with a light, low, laid-back music bed underneath (ducked during speech) and a small set of tasteful SFX on the pipeline/reveal beats
- Voice: enabled (`--voice`). See Voiceover script below.
- Music: `happy-beats-business-moves-vol-9-by-ende-dot-app.mp3` (mid-energy, laid-back — chosen over vol-1 specifically because narration runs through nearly the whole video and needs a bed that won't fight it)
- Music treatment: starts at 0 under the silent hook beat at ~0.3, ducks to ~0.13 the moment narration begins and stays ducked through the whole voiced portion, returns toward ~0.25 only in any narration-free tail at the very end (outro card lingering after the last line)
- Music cue guidance: no bundled cue preset for vol-9 is currently copied into this project's assets — run `npx hyperframes beats` on the composition once the music is wired in (any-track method), or note "unavailable; continue without beat/cue sync" if that's not feasible. Beat/cue sync is a nice-to-have here, not load-bearing, because the voiceover is what actually sets the pace.
- Audio-reactive treatment: subtle at most; if used, let the wordmark/outro glow breathe slightly with RMS — never on the step-list or the fact-check catch moment, where visual clarity matters more than ambience
- SFX posture: sparse, matched to real actions — a soft tick/click per pipeline stage turning green, one clearly distinct "gotcha, reverted" cue (something that reads like a soft rewind/undo, not an error buzzer — this should feel clever, not like a failure) at the honesty-catch moment, one clean payoff cue on the outro wordmark
- Audio-coupled moments: each pipeline stage tick (Scene 3), the embellished-bullet-snaps-back moment (Scene 4, the comedic beat — needs its own distinct sound), the outro wordmark landing (Scene 5)
- Restraint rule: never let SFX or music compete with the voiceover; duck music hard under every spoken line; the revert cue is the one moment allowed a little personality, everything else stays clean and quiet

## Voiceover script
Natural, conversational, first-person-plural where it fits. Roughly matched to the 5 scenes below — Hyperframes should adjust scene timing to the actual generated audio length, not force the audio into these durations.

1. "Every AI résumé tool wants you to sound like a superhero."
2. "This one's not allowed to. Meet the CV Application Manager."
3. "Click generate, and it runs your whole career through a seven-step audit — every line traced back to something you actually did."
4. "Try to oversell yourself, and it just... reverts you. Back to the boring, true version."
5. "Honest CVs, generated in minutes. Nothing made up. Not even a little."

Generate with:
```bash
npx hyperframes tts "<script above>" --voice af_heart --output composition/assets/voiceover.wav
```
(or split per-scene into separate calls if that gives cleaner per-scene timing control — Hyperframes' choice.)

## Storyboard

### Scene 1 — Hook — ~2.5s (flex to VO line 1)
Clean white field, `#1a1a1e` text: "Every AI résumé tool wants you to sound like a superhero." Plain, confident, no product branding yet.
Sequential/interaction: none
Audio intent: sets up the twist, deadpan-adjacent but warm
Audio-coupled idea: voiceover line 1 carries the scene; no SFX needed here beyond a very soft entrance
Music: bed audible at low-moderate volume before narration starts, ducks as soon as VO line 1 begins
Transition mood: clean → Scene 2

### Scene 2 — Reveal — ~2s (flex to VO line 2)
"This one's not allowed to." lands, then the CV Application Manager wordmark/name draws in (`#1a1a1e` on white, `#0b5fff` accent underline or similar small accent touch).
Sequential/interaction: none
Audio intent: the punchline landing, then a clean product reveal
Audio-coupled idea: voiceover line 2; a soft, single drop/click as the wordmark settles
Music: ducked under VO
Transition mood: clean slide → Scene 3

### Scene 3 — Generate CV / pipeline flow — ~5s (flex to VO line 3)
Recreate the app's real step-list UI: a "Generate CV" button gets pressed (simulated click), then stage labels tick down one by one with the app's real spinner→check pattern: **analyzing → matching → drafting → fact-check → render**. Each stage settles on a green check before the next begins.
Sequential/interaction: yes — 5 stages tick in sequence, each held long enough to read the short label (~0.8s floor) even though the visual tempo is brisk; do not compress faster than that floor.
Audio intent: busy-but-controlled, "real system doing real work"
Audio-coupled idea: voiceover line 3 runs under this; a soft tick/click SFX on each stage turning green (thin out if it starts to clash with the VO)
Music: ducked under VO
Transition mood: clean slide → Scene 4

### Scene 4 — The honesty catch — ~5s (flex to VO line 4)
A drafted CV bullet appears in the app's real card/text style: "Singlehandedly scaled infrastructure to serve millions." A fact-check badge flags it (`#8a1f1f` / `#fdeaea`, the app's real failure-state color). The line then visibly snaps/reverts to the real sourced text: "Reduced infra costs 12%, per Q3 report," landing on the app's real success-state green (`#1e6b30` / `#e6f6ea`).
Sequential/interaction: yes — one clear two-step beat (flag, then revert), not a list; both the embellished and the real line need a full readable hold (sentence-length ≈0.3s/word floor) before the transition.
Audio intent: this is the comedic beat — give it a distinct, slightly playful "gotcha, reverted" character
Audio-coupled idea: voiceover line 4 ("Try to oversell yourself, and it just... reverts you") should land its pause right as the revert animation happens; one distinct SFX cue (rewind/undo character, not an error buzzer) exactly at the revert
Music: ducked under VO, may lift very slightly right after this beat if it helps the transition
Transition mood: clean → Scene 5

### Scene 5 — Outro — ~3s (flex to VO line 5 + a short hold after)
CV Application Manager wordmark at full confidence, then: "The CV generator that won't cover for you." Voiceover line 5 plays under/around this. Brief hold after narration ends before cut.
Sequential/interaction: none
Audio intent: warm, confident close
Audio-coupled idea: voiceover line 5; one clean payoff SFX on the wordmark's final settle; music may lift slightly in the narration-free tail before ending
Music: lifts modestly in the last narration-free beat, then fades
Transition mood: clean hold → end

**Music mood for this video:** warm / laid-back upbeat, voiceover-led (default tone)
**Audio summary:** A ducked, low music bed runs under a five-line conversational voiceover for nearly the entire video; SFX are sparse and only mark real actions — the pipeline stage ticks, the one signature "gotcha, reverted" cue at the comedic core of the video, and a single clean payoff on the outro wordmark.
