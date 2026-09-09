# Product

Brand: **Jump Back In** (jumpbackin.show). Internal name: episode-finder.

## Register

product

## Users

Someone who watched a TV series a while ago, got partway through, and cannot
remember where. They arrive maybe three times a year, usually on a phone or a
laptop on the couch, right before pressing play. They are not logged in, will
not make an account, and will leave the moment the answer is on screen. The
job: find the episode to resume from without being told anything they have
not seen yet.

Nothing they answer leaves the browser. There is no history of them anywhere;
the whole product exists because no viewing history exists.

## Product Purpose

A static site that walks the viewer forward through a season one remembered
moment at a time ("Hank has taken up collecting minerals" · I clearly
remember this / Not sure / No) and reports the episode to start from, with a
one-episode fallback for mid-episode stops. Precomputed probes from Wikipedia
episode summaries, audited so that nothing shown reveals a turning point.
Success is a result the viewer believes, reached in under a minute, with at
most minor spoilers, and the site says so up front. The full design record lives in docs/ (PROPOSAL.md, FLOW.md,
adr/) and the vocabulary in CONTEXT.md.

## Brand Personality

Warm, curious, conversational. It feels like a friend walking you backwards
through your own memory: interested in what you remember, unbothered by what
you don't, never quizzing you. It speaks as "we", in full sentences, and says what it is doing ("We'll only
show you moments from episodes you've seen, or at most one past where you
stopped"). It is honest about uncertainty ("you weren't sure
from around here on") rather than confident by default.

## Anti-references

- A generic SaaS or AI tool: cream backgrounds, gradient text, glass cards,
  hero metrics, "AI-powered" anything. This is a small, specific utility and
  should look like one.
- A quiz or a test: no scores, no percentages, no reveal animations. The
  viewer is not being graded; their memory is being consulted.
- A streaming service: no poster walls, no cinematic dark gradients. It is
  not the app you watch on; it is the thing you open right before.

## Design Principles

- **Recall, not recognition of the interface.** Every screen has one job and
  one primary action. The probe card is the product; everything else steps
  back so the sentence on the card can do its work.
- **Say what you're doing.** The walk narrates its own rules in plain
  language at the moments they matter (first card, keep-going card, result).
  No hidden mechanics, no surprise.
- **Undershoot is honest, precision is earned.** Results are phrased as
  advice with a fallback, never as a verdict. Hazy memory is named as hazy.
- **Ask, don't grade.** Three answers, worded so the high bar is the primary
  one and "not sure" is a respectable answer. Nothing ever tells the viewer
  they got something wrong.
- **Nothing leaves the browser, and the page says so.** The privacy property
  is a feature; it appears in the footer of every screen.

## Accessibility & Inclusion

WCAG 2.2 AA as the floor: 4.5:1 body contrast, visible focus, full keyboard
operation of the walk (1/2/3 or y/u/n answer keys, tab order), and a
reduced-motion alternative for every transition. Light and dark follow the
system. The walk must be usable one-handed on a phone: answer buttons within
thumb reach, no hover-only affordances.
