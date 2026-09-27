---
name: linked-in-post
description: "Repackage a source document into ready-to-post LinkedIn content: a beginner-friendly, 2–4-minute newsletter article (paste-ready HTML you open in a browser and copy → LinkedIn keeps the formatting), a ready-to-paste newsletter announcement, and an auto-generated cover image. Works on any document you reference; independent of the learn skill, though learn can trigger it. Triggers on: 'make a LinkedIn article', 'turn this into a LinkedIn post', 'create a summary post for X', 'publish X to LinkedIn'."
argument-hint: "[topic or path to source content]"
user-invocable: true
---

# LinkedIn Post: Source Document → Paste-Ready LinkedIn Article + Announcement

Turn a finished document into ready-to-publish LinkedIn assets:

1. A **short, beginner-friendly newsletter article** — `{DocName}-LinkedIn-Article.md` (readable source) + `{DocName}-LinkedIn-Article.html` (the **paste-ready** file).
2. A **newsletter announcement** (`{DocName}-LinkedIn-Announcement.md`) — the short post text you paste into LinkedIn's publish box; publishing the newsletter attaches the article automatically, so it *is* your feed post (no separate post, no link in the comments).
3. A **cover image** (`images/cover.png`) — always generated, sized for LinkedIn.

This skill is **independent** — it repackages whatever source content you point it at. `learn` can trigger it and hand over a reference, but you can also run it directly on any document.

## How LinkedIn paste works — the proven method

LinkedIn's article editor is a Quill rich-text editor. **It applies formatting only when the clipboard carries rich text (`text/html`)** — exactly like pasting from Google Docs. This was verified end-to-end:

- ✅ **Open the `.html` in a browser → Ctrl+A → Ctrl+C → paste into the article body.** The browser copies the *rendered* page as `text/html`, and LinkedIn maps every element: `<h2>`→Heading, `<h3>`→Subheading, `<strong>`→bold, `<em>`→italic, `<ul>/<ol>`→lists, `<blockquote>`→quote, `<a>`→link, and `<pre><code>`→**code block**.
- ❌ Copying the **HTML source from a text editor/IDE** pastes literal `<tags>` (that's `text/plain`).
- ❌ Pasting **plain markdown** converts only inline `**bold**`, `*italic*`, `[links](url)` — never headings/lists/code.

So the deliverable is an `.html` file, and the publish step is "open in a browser and copy." Two things are still done by hand (LinkedIn requires it): **uploading the cover image** and **uploading any inline images** (marked in the text).

## Input: a reference to the source content

You are given a reference to the source content — usually a path to a markdown/text document (e.g. a `learn` topic doc), or content pasted inline.

1. Resolve it: if it's a path, read that file; if the user names a topic without a path, search the working directory for a matching document and confirm; if content is inline, use it directly.
2. If no source content can be found, ask the user for the document path (or content) and stop — this skill repackages existing content, it does not research the topic.
3. **Optional art direction:** the user may also pass image instructions beyond the defaults — a visual style (e.g. "anime," "Pixar-style 3D"), specific elements to include or avoid, mood, palette/brand colors, composition, or which image(s) it applies to. Capture all of it — Step 3 folds it into the prompts.

## Output location

Derive a base name **`{DocName}`** from the source: the source document's file name **without its extension** (e.g. `AgentMarketplaces.md` → `{DocName}` = `AgentMarketplaces`). Prefix every output with it so the assets stay tied to their source.

Write everything **next to the source document** (same directory):

- `{DocName}-LinkedIn-Article.md` — readable article source
- `{DocName}-LinkedIn-Article.html` — the paste-ready article body
- `{DocName}-LinkedIn-Announcement.md` — the newsletter announcement post text
- `images/` — `cover.png` plus any inline visuals

If content was given inline (no source path), derive `{DocName}` from the title (PascalCase, e.g. "Agent marketplaces" → `AgentMarketplaces`), create `./output/linkedin/{slug}/`, and write the same `{DocName}-…` files there.

## Step 1: Write the article source — `{DocName}-LinkedIn-Article.md`

Reframe the source for someone with **no prior knowledge**: a **2–4-minute read (~300–450 words of readable text, including headings and the signature but excluding front matter and image markers)** in **2–3 short sections**. Answer **one beginner-sized question**, rather than compressing every section of the source. Lead with a relatable question or payoff, not an unexplained term. If the source covers several mechanisms, choose one and save the others for separate articles; do not sacrifice an essential explanation just to hit the word budget. No hashtags in articles. Include at most one `[📷 images/{name}.png — {what the visual shows}]` marker, only if it makes the explanation clearer, and reference the cover as `images/cover.png` — **Step 3 generates the actual image files to match these names.**

### Teach the idea from the beginning

- Establish the starting point in everyday language. The article must stand on its own even if the reader has never heard of the topic or read the source's earlier chapters.
- Pick one concrete example and follow it in order: the initial situation, what changes, and the result a reader can understand. Explain why it matters instead of listing features or related mechanisms.
- Introduce only one or two essential technical terms, define each immediately in plain language, and return to the same example. Avoid unexplained acronyms, equations, internal implementation details, and code unless one is needed to answer the question.
- Use plain-language headings and short paragraphs. Keep the explanation accurate; if an analogy simplifies the mechanics, make clear it is a mental model rather than a literal description.

### Voice: write it as your own story, from your own experience

Write the article as the **author's first-person account of figuring this out**, not a neutral explainer. The reader should feel that a real person is teaching them what they learned, not that an agent generated a summary.

- **Open from genuine curiosity.** Use real first person ("I", "my") to share a question or realization grounded in the source. Do not invent experiences, experiments, or timelines to make the hook sound personal.
- **Make the prologue welcoming.** The standfirst and opening should hook a newcomer with a relatable question, then give the minimum context needed to follow the answer. No textbook openers like "In this article we will..." or unexplained jargon.
- **Keep the experiential thread through the body.** Stay precise but approachable, returning to the same example and what finally made the idea click for the author.
- **Humor: optional and sparing.** At most one or two light, tasteful asides or analogies in the entire article, and zero is perfectly fine. Never force it; the piece should read as smart and human, not as a comedy set.
- **Close in their own voice.** End on one genuine personal takeaway or practical implication, not a glossary recap or generic upbeat conclusion.
- **Always finish with the fixed author signature.** After all article content, append this exact final paragraph and nothing after it: *Written by Lior Zivi, AI Engineer. I build practical AI systems and share what I learn along the way.* Keep it verbatim so every article reinforces the same author identity and personal brand.

Match the author's known newsletter voice using the fixed identity in Step 7, and keep the Step 2 humanizer rules in mind as you draft: no em dashes, varied sentence rhythm, concrete detail.

Use this marker syntax (the readable source):

````
---
title: {plain-language curiosity + benefit title — goes in LinkedIn's Title field}
cover: images/cover.png
---

*{one-sentence standfirst: a personal hook a newcomer can understand}*

{1–2 sentences establishing the question and the minimum starting context}

# {The starting point, in plain words}            (becomes LinkedIn "Heading")

{Introduce one concrete example and the one idea the reader needs first.}

# {What changes and why}

{Follow the same example step by step; define an essential term only when it helps.}

[📷 images/{name}.png — {one simple diagram, only if it clarifies the example}]

# {Why it matters}

{A practical implication and one genuine first-person takeaway.}

*Written by Lior Zivi, AI Engineer. I build practical AI systems and share what I learn along the way.*
````

Omit the optional image marker if the article is clearer without it. Count the readable words and reread the result as a newcomer before moving on: if it runs long, narrow the question; if a term is undefined, explain it or remove it.

## Step 2: Humanize the article — `{DocName}-LinkedIn-Article.md`

Run the **`humanizer`** skill (from the `remote-plugin-blader` plugin) on `{DocName}-LinkedIn-Article.md` so it reads as human-written rather than AI-generated, then save the humanized text back to `{DocName}-LinkedIn-Article.md`. This must run **before Step 4** — the paste-ready HTML is rendered from this file, so it needs to reflect the humanized text. Preserve the fixed final signature verbatim; if the humanizer changes, moves, or removes it, restore it as the article's final paragraph. If the `humanizer` skill isn't installed, apply its principles inline (cut AI tells and filler, vary sentence rhythm) and continue. Recheck the word count and beginner-friendly explanations after humanizing; do not let the edit reintroduce jargon or length.

## Step 3: Generate the cover image and inline visuals

Now that the article exists, create the images it references — **directly from the content**, no dependency on any deck/PPTX.

**Image generator — prefer the `ai-local-diffusion-invoker` skill (local, free, on-GPU).** Before generating raster visuals, check your available skills list for a skill named **`ai-local-diffusion-invoker`** (from the `local-ai` plugin; it may appear namespaced, e.g. `local-ai:ai-local-diffusion-invoker`). It generates images locally on the user's own NVIDIA GPU (FLUX text-to-image) — no cloud service, no paid API. **When it is available, you MUST use it for the cover image and for every conceptual / illustrative / photographic inline visual.** Invoke it with the prompt you write (see *Prompting & art direction* below), send its output into `images/`, and use the absolute path it returns (rename/resize it to the filename the article references). The model needs both dimensions as **multiples of 16**, so generate at a 16:9-friendly size like **1280 × 720** or **1344 × 768**, then resize to the target spec. Never put text, words, or labels inside the image (diffusion renders lettering poorly).

### Prompting & art direction

Every prompt must be **grounded in this specific article** — read its title, standfirst, and section headings first, then translate the *idea it argues* into a concrete visual metaphor. In each prompt name the **subject, composition, art style, color palette, mood, and lighting**, and end with an aspect hint (e.g. `16:9`).

- **Cover → beautiful, artistic, aspirational.** The cover is the most striking image: an artful, **symbolic** representation of *what the piece helps the reader achieve* — its goal or payoff — not a literal screenshot. Favor a strong central metaphor, depth, rich-but-tasteful color, and a sense of momentum or possibility; aim for editorial "hero art," evocative over utilitarian.
  - *e.g. (microservices migration):* `a luminous city of floating modular structures linked by glowing data bridges at dawn, order emerging from complexity, cinematic wide shot, warm hopeful palette, volumetric light, 16:9`
- **Inline visuals → clean, professional.** Conceptual inline images should look polished and businesslike: a restrained palette, one clear focal point, a modern editorial / tech-illustration feel. They support the argument, so keep them calm and legible rather than flashy.
  - *e.g. (a caching section):* `a minimalist professional illustration of a layered cache as stacked translucent panes with one highlighted fast path, muted corporate palette, soft even lighting, clean background, 16:9`

**User art direction (style — and any other prompt instructions).** The user can shape the imagery when they invoke this skill, and not only its *style*. Treat anything they say about the images as **art-direction overrides that take precedence** over the defaults, and fold it into the prompt(s) it targets. They may pass:

- a **visual style** — e.g. *"cover in an anime style,"* *"make the images Pixar-style 3D"* (`anime / cel-shaded`, `Pixar-style 3D render`, `watercolor`, `flat vector` / `isometric`, `cinematic photo`, `oil painting`, `low-poly`, `cyberpunk`, `minimalist line art`, …);
- **elements to include or avoid** — *"feature a robot mascot," "no people," "include a mountain skyline";*
- **mood / tone, color palette or brand colors, composition, or level of detail** — *"darker and moodier," "use our teal brand color," "top-down composition";*
- **which image(s)** the direction applies to.

Targeting: a direction with **no target** → the **cover** (plus conceptual inline visuals); **"all images" / "the visuals"** → every generated image; a **named image** → that one only. When a direction conflicts with a default (e.g. they want a playful cartoon cover), **follow the user.** Labeled diagrams stay Mermaid/SVG regardless. With **no** direction given, use the defaults above (artistic cover, professional inline).

### Files to produce

- **Cover image (always):** `images/cover.png` at **1920 × 1080 px** (16:9; LinkedIn's official article/newsletter cover spec), PNG/JPEG/WEBP — **not GIF**, < 5 MB; keep on-image text minimal (LinkedIn overlays UI on thumbnails). With the invoker: generate at 1280 × 720 (or 1344 × 768), then resize/pad to 1920 × 1080 and save as `images/cover.png`.
- **Inline visuals:** for each `[📷 images/{name}.png — …]` marker in the article (0–1 by default; never add visuals just to fill a quota):
  - **Accurate, labeled diagrams** (architecture, flow, comparison, before/after) need legible text that diffusion can't produce — emit **Mermaid/SVG** and render these, whether or not the invoker is available.
  - **Conceptual, illustrative, or photographic** visuals — generate with **`ai-local-diffusion-invoker`** when it's available (professional style by default, or the user's override); otherwise use whatever image capability you have.
  Keep the generated filenames matching the markers.
- **No image capability at all** (invoker absent *and* no raster/diagram tool)? Don't block: leave the inline `[📷 …]` markers as placeholders; for the cover, if a PNG can't be rendered, write `images/cover.svg` (1920 × 1080) and tell the user to export it to PNG.

## Step 4: Render the paste-ready HTML — `{DocName}-LinkedIn-Article.html`

Convert the source to an HTML **body** using EXACTLY this mapping (all verified to survive paste). This is the file the user copies from a browser.

| Markdown in source | HTML to emit | LinkedIn result |
|---|---|---|
| `# Heading` | `<h2>…</h2>` | Heading |
| `## Subheading` | `<h3>…</h3>` | Subheading |
| paragraph | `<p>…</p>` | Normal text |
| `**bold**` | `<strong>…</strong>` | Bold |
| `*italic*` | `<em>…</em>` | Italic |
| `` `inline code` `` | `<code>…</code>` | Inline code |
| fenced ` ``` ` block | `<pre><code>…</code></pre>` | Code block |
| `- item` | `<ul><li>…</li></ul>` | Bulleted list |
| `1. item` | `<ol><li>…</li></ol>` | Numbered list |
| `> quote` | `<blockquote>…</blockquote>` | Quote |
| `[text](url)` | `<a href="url">text</a>` | Link |
| `[📷 file — caption]` | `<p>[📷 file — caption]</p>` (literal text) | Upload reminder |

Rules:
- **Do NOT put the title in the body** — it goes in LinkedIn's separate Title field. Keep it in the `<head>`'s `<title>` tag; Step 7 copies it from there into LinkedIn. Do **not** emit `<h1>` (it does not map cleanly).
- **Use only these tags**: `h2, h3, p, strong, em, code, pre, ul, ol, li, blockquote, a, br`. No `class`, `style`, `div`, `span`, `<img>`, `<hr>`, tables, colors, or font-size — LinkedIn strips or breaks them.
- **No `<img>`**: keep each image as the literal `[📷 …]` marker so the user uploads it at that spot.
- End the `<body>` with this exact final paragraph: `<p><em>Written by Lior Zivi, AI Engineer. I build practical AI systems and share what I learn along the way.</em></p>`. Do not emit any article content after it.
- Wrap in a minimal document so a browser renders it cleanly:

```
<!doctype html>
<html><head><meta charset="utf-8"><title>{title}</title></head>
<body>
<p><em>I wondered why the same page sometimes loads faster the second time.</em></p>
<h2>The starting point</h2>
<p>The app asks for data and keeps a copy in a <strong>cache</strong>, a temporary place for recently used answers.</p>
<h2>What changes next time</h2>
<p>When the page opens again, the app checks that copy first instead of asking for the same data again.</p>
<h2>Why it matters</h2>
<p>Less waiting made caching much easier for me to understand.</p>
<p><em>Written by Lior Zivi, AI Engineer. I build practical AI systems and share what I learn along the way.</em></p>
</body></html>
```

## Step 5: Write the newsletter announcement — `{DocName}-LinkedIn-Announcement.md`

This is the text you paste into the **share box of LinkedIn's newsletter publish flow** (the "add your thoughts" field shown when you publish the article). Publishing the newsletter posts this text to the feed **with the article attached as a card**, so it *is* your feed post — you do **not** write a separate standalone post, and you do **not** put the article link in the body or in a first comment (the attached article already carries the click).

The feed has no rich text, so this stays plain text with **Unicode bold/italic** for emphasis. First 2 lines must hook above the "…see more" fold; short lines; **3–6 hashtags**; **800–1,500 chars**.

Write it to feel **personal**, not corporate: use **first person**, lead with your own angle — why this mattered to you, what surprised you, a genuine opinion or hot take — and keep the voice conversational, like *you* sharing something with your network rather than a press release. Avoid generic hype and AI-isms (the Step 6 humanizer pass reinforces this).

This announcement is the **most personal of the three assets**: it is *you* telling your network what you just learned and why it grabbed you. Lead from your own experience (what you noticed, what surprised you, what you went and dug into), and make the **first two lines fascinating and inviting** so people stop scrolling and want the full article. A single light, tasteful joke is welcome if it fits naturally.

Keep the announcement accessible to the same newcomer as the article: tease its one core question without introducing new jargon or promising a broader technical survey.

Do **not** add any "link in the comments" line: because this is the newsletter's own publish-flow post, LinkedIn attaches the full article to it automatically, so the click is already there.

```
{𝗨𝗻𝗶𝗰𝗼𝗱𝗲-𝗯𝗼𝗹𝗱 personal hook line 1 — first person, from your own experience: a surprising realization or relatable tension that stops the scroll}
{hook line 2 that earns the "…see more" tap}

{2–4 short lines previewing the value, in your own voice}

𝗜𝗻𝘀𝗶𝗱𝗲 𝘁𝗵𝗲 𝗳𝘂𝗹𝗹 𝗶𝘀𝘀𝘂𝗲:
◈ {point 1}
◈ {point 2}

{one-line personal takeaway — what you think, or what you'd do with this}

♻️ Repost if it's useful to someone in your network.

#Hashtag1 #Hashtag2 #Hashtag3
```

> Optional follow-up: to re-surface the piece later, you can write a *separate* feed post a day or two afterward — but give it a **different angle/hook** than this announcement, not the same words.

## Step 6: Humanize the announcement — `{DocName}-LinkedIn-Announcement.md`

Run the **`humanizer`** skill (from the `remote-plugin-blader` plugin) on `{DocName}-LinkedIn-Announcement.md` so it sounds like a human wrote it, then save the humanized text back. If the `humanizer` skill isn't installed, apply its principles inline and continue.

## Step 7: Use the fixed author identity and report the publish workflow

The article author is always **Lior Zivi, AI Engineer**. Do not replace this identity or ask for an author name or role. Fill `{Newsletter name}` from what you know; if unknown, leave that placeholder and ask once. Optionally open the HTML in the user's browser for them (e.g. `Start-Process msedge "file:///<abs-path>/{DocName}-LinkedIn-Article.html"`). Then report this exact flow:

**Article**
1. LinkedIn → Home → **Write article** → select your newsletter.
2. **Cover:** upload `images/cover.png` (1920 × 1080).
3. **Title:** copy the article title from the `<title>…</title>` tag in the `<head>` of `{DocName}-LinkedIn-Article.html`, and paste it into LinkedIn's Title field.
4. **Body:** open `{DocName}-LinkedIn-Article.html` **in a browser** — paste its `file:///…` path into the address bar (do NOT open it in a code editor). **Ctrl+A → Ctrl+C** on the rendered page, click the article body, **Ctrl+V**. Headings, subheadings, bold, italic, lists, quotes, code blocks, and links all carry over.
5. At each **`[📷 …]`** marker, click the image button and upload the named file from `images/`, then delete the marker text.

**Newsletter announcement** (same publish action — not a separate post)
6. When you click **Publish**, LinkedIn shows a share-to-feed box. Paste `{DocName}-LinkedIn-Announcement.md` there. Publishing posts it to your feed **with the article attached as a card** — so there's no separate feed post to write, and no link to drop in the comments.

Report: the title, cover path, all output file locations, the visuals generated (note the art style used — default or the user's override) or placeholders, and the steps above.
