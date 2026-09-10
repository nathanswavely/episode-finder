# Monetization

Status: decided 2026-09-08. No display ads. Affiliate "watch" links on the
result screen and a tip link in the footer, when and if traffic warrants
either. Revisit only if the site passes ~50k visits/month.

## Display ads: no

- Revenue: ~$1–3 per thousand pageviews for a low-engagement utility, and a
  visit here is one pageview (single-page app). At 1,000 visits/month that is
  $1–3/month. The domain costs more.
- Approval: ad networks reject thin sites; this one is three screens by design.
- The promise: "nothing you answer leaves your browser" becomes false when an
  ad network's script loads; EU visitors would need a consent banner.
- The design: the probe card is the product. An ad beside it is the generic
  tool look PRODUCT.md rules out.
- Hosting: GitHub Pages' terms bar sites "primarily directed at facilitating
  commercial transactions". Ads on a utility are a grey area; moving to a host
  without that clause (Cloudflare Pages, free) is a precondition for any
  monetisation, ads or not.
- Original plan noted ad support might trip TMDB's terms. TMDB is gone
  (ADR-0004), so that constraint no longer applies. It was never the binding
  one.

## Affiliate watch links: yes, when useful

The result screen is the one moment a viewer is about to press play. A
"Watch on <service>" link there is useful regardless of revenue.

- Apple TV+: **not available.** Apple Services Performance Partners is open
  only to partners with content on Apple's stores, and by invitation. Checked
  2026-09-09. Apple TV links stay plain.
- Prime Video (The Boys, Fallout, Reacher): Amazon Associates pays a bounty on
  Prime and channel sign-ups from a link.
- Netflix, Max, Disney+, Paramount+, Peacock: no affiliate programme. Plain
  links, still worth having.
- Where a show streams changes by region and over time. Keep a small,
  hand-maintained `watch` map per show (US only to start) in the shipped show
  JSON; no provider API (TMDB's is off the table; JustWatch has no public one).
- Copy stays honest: mark affiliate links as such in the footer line.

## Tip link: live

Buy Me a Coffee (buymeacoffee.com/nathanswavely) in the footer as "Buy us a
coffee". A plain link: no script, no tracking. Live 2026-09-09.

Also on the request form's thank-you page (Tally gDlO9J, added 2026-09-10):
"Adding a show costs us a few dollars in model time and an evening of
checking. If you'd like to cover that, you can buy us a coffee." That is the
one moment a visitor is asking us to spend money, so it is the honest place
for the ask. Paid show requests were considered and rejected: nobody pays to
request a show.

## The rule from the original plan still holds

"If the grilling surfaces a version that only works with recurring cost or a
backend, that is a signal to stop." Nothing above needs a backend or a
recurring cost. Ads would have needed a new host, a consent banner and a
broken promise to earn less than the domain.
