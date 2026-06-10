# LinkedIn Output Templates

This file defines the exact format for the two LinkedIn artifacts the `learn` skill produces
from a finished `{Topic}.md` (the substance) and `{Topic}.pptx` (the visuals):

1. A **newsletter article** → `./output/learn/{Topic}-linkedin-article.md`
2. A **summary post** → `./output/learn/{Topic}-linkedin-post.md`

LinkedIn treats these two surfaces very differently, and getting the formatting right is what
makes them "paste-and-go" for the user. The single most important rule:

> **Articles support real rich text** (Heading 1/2, bold, italic, bullet/numbered lists, inline
> images, links, quotes). **Feed posts support none of that.** So write the article in clean
> Markdown, and write the post with Unicode bold/italic so emphasis survives in the feed.

Write each artifact's content **directly** into its output file (the fenced skeletons below are
just to show structure — don't wrap the real file in a code fence).

---

## PART A — Newsletter Article → `{Topic}-linkedin-article.md`

A newsletter issue is a long-form article. Reframe the deck's terse bullets into flowing,
plain-English prose — the document is a skeleton, the article is the narrative a reader actually
enjoys. Aim for a **3–5 minute read (~600–1,200 words)** and **4–7 sections** (curate; drop the
least interesting parts of the doc). Lead with *why this matters now*, not a dictionary definition.

Use this skeleton:

```
<!--
HOW TO POST THIS AS A LINKEDIN NEWSLETTER ISSUE
1. Home feed -> "Write article" -> select your newsletter.
2. Cover image: upload ./images/{Topic}-slide-01.png (the title slide).
3. Title: paste the line after "TITLE:" below.
4. Body: copy everything below the "--- ARTICLE BODY ---" line.
   - For each line that starts with "## " -> select it and click Heading 2 in the toolbar.
   - For **bold** / *italic* -> apply with the toolbar (LinkedIn does not parse Markdown).
   - At every brace-and-frame slide marker -> click the image button and insert the named PNG.
5. Delete this comment block and every slide marker before publishing.
6. Publish, then post {Topic}-linkedin-post.md and paste the article link as its first comment.
-->

TITLE: {Compelling, curiosity + benefit title — e.g., "Stop confusing AI agents with chatbots"}

--- ARTICLE BODY ---

*{One-sentence standfirst that hooks the reader and previews the payoff.}*

{Opening: 2–4 short sentences. Why this topic matters right now; a relatable framing.}

## {Plain-English section heading — not the terse doc heading}

{2–4 sentences of prose that EXPAND the slide bullets into a real explanation.}

〔🖼 SLIDE 04 — "System Overview" → insert ./images/{Topic}-slide-04.png〕

- {Optional supporting bullet, only when a list genuinely helps}
- {Optional supporting bullet}

## {Next section}

{Prose...}

## Key takeaways

- {Crisp takeaway 1}
- {Crisp takeaway 2}
- {Crisp takeaway 3}

***Enjoyed this? Subscribe to {Newsletter name} for one clear idea every week — and connect with me to learn together.***

*Written by {Author}, {role}.*
```

### Article rules

- **Reframe, don't copy.** Slide bullets are shorthand; turn them into sentences with connective
  tissue and concrete examples. If a reader couldn't follow it without the slides, expand it.
- **Images:** place **3–6** slide images where they reinforce the text — the architecture image
  near the architecture section, the comparison-table slide near the comparison, etc. Reference
  the **real exported filenames** the export step produced (`{Topic}-slide-01.png`, `-02`, …).
  Don't dump every slide; choose the ones that add visual value.
- **No image was exported?** Keep the `〔🖼 …〕` markers anyway and note in the how-to-post block
  that the user should export slides manually. Never block the article on missing images.
- **No hashtags inside articles** — hashtags belong on the feed post.
- End with **Key takeaways** + a subscribe CTA so the issue compounds the user's brand.

---

## PART B — Summary Post → `{Topic}-linkedin-post.md`

This is the short **feed post** that teases the article and drives clicks. It is where reach
happens, so it must earn the "…see more" tap and survive LinkedIn's plain-text feed.

Apply these principles (the same ones strong LinkedIn writers use):

- **Hook first.** The opening **2 lines** must create curiosity *above the fold* (~210 chars
  show before "…see more"). No throat-clearing.
- **Unicode formatting**, because the feed has no real bold/italic: use 𝗯𝗼𝗹𝗱 for the hook and
  section labels, *𝘪𝘵𝘢𝘭𝘪𝘤* sparingly, and bold digits (𝟭. 𝟮. 𝟯.) for lists. Bold *key phrases*,
  not whole sentences.
- **Scannable.** Short lines, one idea each, single blank line between them (LinkedIn collapses
  multiple blanks). Use ◈ or ↳ for bullets.
- **No link in the body.** LinkedIn throttles posts with outbound links, so put the newsletter
  link in the **first comment** instead. Provide that comment text ready to paste.
- **3–6 hashtags** on the final line, mixing broad (#AI) and specific (#RAG) tags.
- **800–1,500 characters** total — a teaser, not the whole article.
- End with a light CTA (subscribe / repost / "full breakdown in comments").

Use this skeleton:

```
{𝗨𝗻𝗶𝗰𝗼𝗱𝗲-𝗯𝗼𝗹𝗱 hook line 1 — the surprising or useful truth}
{hook line 2 that compels the "…see more" tap}

{2–4 short lines previewing the value — what the reader will learn and why it matters.}

𝗜𝗻𝘀𝗶𝗱𝗲 𝘁𝗵𝗲 𝗳𝘂𝗹𝗹 𝗶𝘀𝘀𝘂𝗲:
◈ {point 1}
◈ {point 2}
◈ {point 3}

{One-line takeaway.}

♻️ Repost if this was useful. Full breakdown in the comments 👇

#Hashtag1 #Hashtag2 #Hashtag3 #Hashtag4
```

Immediately below the post, include the ready-to-paste first comment:

```
FIRST COMMENT (paste right after you publish the post):
Full article here 👉 {paste your newsletter issue URL}
```

---

## Personalization

Fill `{Author}`, `{role}`, and `{Newsletter name}` from what you know about the user (the
conversation, their profile, prior issues). If you genuinely don't know, leave the placeholder
and tell the user to fill it in once — don't invent a newsletter name.
