---
name: linked-in-post
description: "Repackage a source document into ready-to-post LinkedIn content — a long-form newsletter article plus a short summary post that links to it. Works on any document you reference and generates its own visuals; independent of the learn skill, though learn can trigger it. Triggers on: 'make a LinkedIn article', 'turn this into a LinkedIn post', 'create a summary post for X', 'publish X to LinkedIn'."
argument-hint: "[topic or path to source content]"
user-invocable: true
---

# LinkedIn Post: Source Document → LinkedIn Article + Post

Turn a finished piece of content into two ready-to-paste LinkedIn assets:

1. A **newsletter article** (`linkedin-article.md`) — the long-form issue.
2. A **summary post** (`linkedin-post.md`) — a short feed teaser that links to the article.

A short native post is what the feed rewards with reach; the article is the durable, subscribable home for the full content — the post exists to drive people to the article.

This skill is **independent**: it repackages whatever source content you point it at. It does not research or write the topic from scratch, and it does not assume the content came from any particular skill or lives at any particular path. The `learn` skill can trigger it and hand over a reference, but you can invoke it directly on any document.

## Input: a reference to the source content

You are given a **reference to the source content** — usually a path to a markdown/text document (for example, a `learn` topic document), or the content pasted inline.

1. Resolve the reference: if it is a path, read that file; if the user names a topic without a path, search the working directory for a matching document and confirm the match; if content is given inline, use it directly.
2. If no source content can be found, ask the user for the document path (or the content) and stop — this skill repackages existing content, it does not generate the topic.

## Output location

Write every output **next to the source document** — in the same directory as the referenced file:

- `linkedin-article.md`
- `linkedin-post.md`
- `images/` — the visuals you generate for the article

If the content was provided inline (no source path), create `./output/linkedin/{slug}/` using a short slug from the topic and write there.

## Step 1: Generate the visuals

Create the article's images **directly from the content** — do not rely on any existing presentation, deck, or PPTX.

- Pick 3–6 ideas that benefit from a visual (an architecture, a flow, a comparison, a before/after).
- Generate each as a standalone diagram or image using whatever image/diagram capability is available in this session — e.g., an image-generation or diagramming skill, or by emitting diagram source (such as Mermaid) and rendering it to PNG/SVG. Save them into the `images/` folder next to the article and note each filename.
- If no image/diagram capability is available, **do not block**: write the article with clearly labeled placeholders describing what each visual should show, and tell the user.

## Step 2: Write the newsletter article

Articles support **real rich text**, so write clean Markdown. Reframe the source's terse points into flowing, plain-English prose — aim for a **3–5 minute read (~600–1,200 words)** across **4–7 sections**. Lead with *why this matters now*, place your generated visuals where they reinforce the text, and close with key takeaways + a subscribe CTA. **No hashtags in articles.**

Write this skeleton into `linkedin-article.md`:

```
<!--
HOW TO POST AS A LINKEDIN NEWSLETTER ISSUE
1. Home feed -> "Write article" -> select your newsletter.
2. Cover image: upload images/{cover}.png.
3. Title: paste the line after "TITLE:".
4. Body: copy everything below "--- ARTICLE BODY ---". Apply Heading 2 to "## " lines and bold/italic with the toolbar (LinkedIn ignores Markdown). At each 〔🖼 …〕 marker, insert the named image from images/.
5. Delete this comment block and every marker before publishing.
-->

TITLE: {curiosity + benefit title}

--- ARTICLE BODY ---

*{one-sentence standfirst that hooks the reader and previews the payoff}*

{2–4 sentence opening: why this matters right now}

## {plain-English section heading}

{2–4 sentences expanding the idea into a real explanation}

〔🖼 images/{name}.png — {what the visual shows}〕

## {next section}

{prose…}

## Key takeaways

- {takeaway 1}
- {takeaway 2}
- {takeaway 3}

***Enjoyed this? Subscribe to {Newsletter name} for one clear idea every week.***

*Written by {Author}, {role}.*
```

## Step 3: Write the summary post

The feed has no rich text, so use **Unicode bold/italic** for emphasis. The first **2 lines** must hook above the "…see more" fold. Keep lines short and scannable, end with **3–6 hashtags**, and aim for **800–1,500 characters**. Keep links **out of the body** (LinkedIn throttles them) — put the article link in a ready-to-paste **first comment** instead.

Write this skeleton into `linkedin-post.md`:

```
{𝗨𝗻𝗶𝗰𝗼𝗱𝗲-𝗯𝗼𝗹𝗱 hook line 1 — the surprising or useful truth}
{hook line 2 that earns the "…see more" tap}

{2–4 short lines previewing the value}

𝗜𝗻𝘀𝗶𝗱𝗲 𝘁𝗵𝗲 𝗳𝘂𝗹𝗹 𝗶𝘀𝘀𝘂𝗲:
◈ {point 1}
◈ {point 2}
◈ {point 3}

{one-line takeaway}

♻️ Repost if this was useful. Full breakdown in the comments 👇

#Hashtag1 #Hashtag2 #Hashtag3
```

Then give the user the **first comment** text (containing the article link) ready to paste.

## Step 4: Personalize and report

Fill `{Author}`, `{role}`, and `{Newsletter name}` from what you know about the user; if genuinely unknown, leave the placeholder and ask them to fill it once — don't invent a newsletter name. Report both output file locations, which visuals were generated (or that placeholders were used because no image tool was available), and the one-line publish flow: write the article -> select your newsletter -> paste it, then publish the teaser post and put the article link in its first comment.
