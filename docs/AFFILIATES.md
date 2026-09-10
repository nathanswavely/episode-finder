# Affiliate sign-up instructions

Written 2026-09-10. Both programmes are Nathan's to join; the site side is
already wired. When a programme approves you, the only change here is
`data/watch.json`: replace that show's `url` with the tagged link and set
`"affiliate": true`. The result screen then adds `rel="sponsored"` and the
disclosure line under the button. Rebuild and push; nothing else moves.

The honest expectation: at current traffic neither pays out. The reason to
enrol is to have the link in place before a spike, not because of the spike.

## Peacock (The Office) via Impact

Status check first. Affiliate directories listed Peacock's programme as
**paused** in September 2026. Before spending time, confirm it is taking new
partners: sign in to Impact, open the marketplace, search "Peacock", and look
for an Apply button rather than "not accepting applications". If it is
closed, leave The Office on its plain link and check back in a quarter.

If it is open:

1. Create a free partner account at https://app.impact.com/ (choose
   "Partner", not "Brand"). Use nathan@swavelycreative.com and
   jumpbackin.show as the property.
2. Fill in the partner profile. Property type: website. Category: media or
   entertainment. Promotional method: content. Describe the site in one
   honest paragraph: a free utility that tells viewers which episode to resume
   a show from, with a "Watch on Peacock" button on the result screen for
   shows that stream there. Monthly visits: say the real number.
3. Add tax and payout details under Settings. Impact pays by PayPal or bank
   transfer once a balance clears their minimum.
4. In the marketplace, open the Peacock TV programme and apply. Approval is
   manual and can take a week or two. A three-screen utility may be declined
   for thin content; if so, the per-show pages in the SEO plan are the fix,
   and you can reapply after they exist.
5. Once approved, open the programme, choose "Create a link", paste the
   landing URL for The Office (`https://www.peacocktv.com/stream-tv/the-office`)
   and copy the tracking link Impact returns. It will point at a `prf.hn` or
   `imp.i` domain that redirects to Peacock.
6. Put that link in `data/watch.json` under `the-office` with
   `"affiliate": true`. Commit and push.

Terms to keep in mind: Peacock pays on paid sign-ups, not clicks, and the
free trial is gone, so a conversion means someone actually subscribed after
clicking. Impact reports conversions under Reports > Performance.

## Amazon Associates (Prime Video shows, and physical box sets)

Timing matters more than anything else here. The 180-day clock starts the
day you are approved, and you need three qualifying sales inside it or the
account is closed and you reapply. So do not sign up until a Prime Video show
is in the catalog and a link is ready to ship the same day.

1. Apply at https://affiliate-program.amazon.com/ with your Amazon account.
   List jumpbackin.show as the website. When it asks how you drive traffic,
   say organic search and direct; when it asks what you build links to, say
   Prime Video titles and TV box sets.
2. Pick a store ID (your tracking tag), for example `jumpbackin-20`. This
   suffix is what goes on every link.
3. Complete tax information (W-9 as a US individual or your LLC) and a payout
   method. Direct deposit avoids the gift-card-only minimum.
4. Once approved, build links with SiteStripe (the bar Amazon shows at the
   top of every product page when you are signed in as an associate) or by
   appending `?tag=jumpbackin-20` to a product or Prime Video URL.
5. Add the disclosure the operating agreement requires. It has to be visible
   near the links: "As an Amazon Associate we earn from qualifying purchases."
   Put it in the footer of `site/index.html` next to the CC BY-SA line, and
   keep the existing per-button disclosure.
6. Amazon also requires a privacy policy that says what the site collects.
   Ours collects nothing, which still needs saying. One paragraph on a
   `/privacy` page, linked from the footer, satisfies it.
7. Put the tagged link in `data/watch.json` for the Prime show with
   `"affiliate": true`. For non-Prime shows, a second link to the Blu-ray or
   DVD set is allowed by the schema if you add a `buy` entry; the site does
   not render one today, so that would be a small change in `watchButton()`.

What pays: a percentage on physical media, a smaller one on digital video,
and a fixed bounty on Prime and Prime Video Channel sign-ups that originate
from your link. Bounties are the only line that adds up at low traffic.

What gets accounts closed: links in email, links that hide the tag, missing
disclosure, and no sales in the first 180 days. Never put the tag on a link
you send to a friend to test; the three sales must be from strangers.

Sources checked 2026-09-10: Impact marketplace listings for Peacock TV; the
Amazon Associates Operating Agreement and its April 2026 update (the 180-day
qualification window and the content requirement).
