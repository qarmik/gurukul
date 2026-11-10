# Gurukul

**A local workspace for practising Python and collecting evidence of what I can do.** I’m Rohit Kumar. I started Gurukul while building on my banking operations experience and working toward enterprise AI systems design.

## Why I started

A chat could explain Python, and AI could help me produce working code. Neither told me whether I could write it again from a blank file, diagnose an error myself, or still do it a few days later. I wanted a way to practise, return to the same skill after a delay, and keep enough evidence to review what I actually did.

## How it started and what it does

I started with a structured curriculum and one exercise on Python values and variables: write a small program, make a deliberate mistake, fix it, and explain what changed. The project grew from saving terminal runs into a local browser workspace where I can write and run code, keep the failed and repaired versions, and return for a later assessment.

**Guru can teach; Gurukul controls when help is allowed and what counts as evidence.** For example, once an assessment opens, the server rejects Ask Guru requests, even if someone bypasses the button. A successful run can be saved for review; it does not establish that I worked independently or passed the curriculum stage. The current implementation covers the first exercise. Broader curriculum coverage is planned.

## My role and the help I used

I set the learning goal, kept the first build to one Python exercise, and required tutoring to stop during assessment. I ran the one-request Mac trial myself: I asked a practice question, checked the browser reply, and captured the receipt at shutdown.

I used ChatGPT for design feedback and Codex to help write project code and run automated tests. Gurukul itself runs locally using Python, SQLite, and a browser. The default workspace makes no model calls; a separate opt-in live trial uses NousResearch Hermes and the OpenAI API.

## What you can verify

- **Software shipped — saved work and review.** The [disposable workflow report](https://github.com/qarmik/gurukul/blob/b38422a85f36dc23507ca6100560d100dd6d580a/docs/GURU-007-synthetic-workflow.json) shows a failed run and its repair being retained, with the assessment completed **for review** and no advancement awarded.
- **Software control — help blocked during assessment.** The [test report](https://github.com/qarmik/gurukul/blob/b38422a85f36dc23507ca6100560d100dd6d580a/docs/GURU-010.md#verification) shows the server rejecting a direct request before the tutor was called. This used disposable state and a stub, not a live provider.
- **Hands-on check — one live reply.** The [Mac trial closeout](https://github.com/qarmik/gurukul/blob/b38422a85f36dc23507ca6100560d100dd6d580a/docs/GURU-011-live-closeout.md) records one real provider response that passed validation and appeared in the browser, with no change to learner progress.

**Learner practice:** I’m working on reconstructing and varying small Python programs. **Independently demonstrated skill:** I’m not claiming an independent Python pass from these records. The [upskilling portfolio](https://github.com/qarmik/gurukul/blob/eb97d080ccca529e2b0afb92fd86131f8351dea8/docs/progress/summary.md) is still in preview; its text summary is available without installing anything.

[Developer guide: setup, design notes, and verification](docs/developer-guide.md)
