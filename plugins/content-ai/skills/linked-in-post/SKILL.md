---
name: linked-in-post
description: "Repackage a source document into ready-to-post LinkedIn content: a paste-ready newsletter article (an HTML file you open in a browser and copy → LinkedIn keeps the formatting), a short summary post, and an auto-generated cover image. Works on any document you reference; independent of the learn skill, though learn can trigger it. Triggers on: 'make a LinkedIn article', 'turn this into a LinkedIn post', 'create a summary post for X', 'publish X to LinkedIn'."
argument-hint: "[topic or path to source content]"
user-invocable: true
---

# LinkedIn Post: Source Document → Paste-Ready LinkedIn Article + Post

Turn a finished document into ready-to-publish LinkedIn assets:

1. A **newsletter article** — `linkedin-article.md` (readable source) + `linkedin-article.html` (the **paste-ready** file).
2. A **summary post** (`linkedin-post.md`) — a short feed teaser that links to the article.
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

## Output location

Write everything **next to the source document** (same directory):

- `linkedin-article.md` — readable article source
- `linkedin-article.html` — the paste-ready article body
- `linkedin-post.md` — the feed summary post
- `images/` — `cover.png` plus any inline visuals

If content was given inline (no source path), create `./output/linkedin/{slug}/` and write there.

## Step 1: Generate the cover image and inline visuals

Create images **directly from the content** — no dependency on any deck/PPTX.

- **Cover image (always):** `images/cover.png` at **1920 × 1080 px** (16:9; LinkedIn's official article/newsletter cover spec), PNG/JPEG/WEBP — **not GIF**, < 5 MB. Keep on-image text minimal (LinkedIn overlays UI on thumbnails).
- **Inline visuals:** pick 3–6 ideas worth a visual (architecture, flow, comparison, before/after); generate each into `images/` using whatever image/diagram capability is available (an image/diagram skill, or emit Mermaid/SVG and render). Note each filename.
- **No raster-image capability?** Don't block: keep inline `[📷 …]` markers as placeholders; for the cover, if a PNG can't be rendered, write `images/cover.svg` (1920 × 1080) and tell the user to export it to PNG.

## Step 2: Write the article source — `linkedin-article.md`

Reframe the source into flowing prose: a **3–5 minute read (~600–1,200 words)**, **4–7 sections**, leading with *why this matters now*. No hashtags in articles. Use this marker syntax (the readable source):

````
---
title: {curiosity + benefit title — goes in LinkedIn's Title field}
cover: images/cover.png
---

*{one-sentence standfirst}*

{2–4 sentence opening}

# {Section heading}            (becomes LinkedIn "Heading")

{prose with **bold**, *italic*, and `inline code` where useful}

[📷 images/{name}.png — {what the visual shows}]

## {Subheading}                (becomes LinkedIn "Subheading")

- {bullet}
- {bullet}

> {a quotable line}

```
{a code block, if relevant}
```

[{link text}]({url})

# Key takeaways

- {takeaway 1}
- {takeaway 2}

*Written by {Author}, {role}.*
````

## Step 3: Render the paste-ready HTML — `linkedin-article.html`

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
- **Do NOT put the title in the body** — it goes in LinkedIn's separate Title field (report it in Step 5). Do **not** emit `<h1>` (it does not map cleanly).
- **Use only these tags**: `h2, h3, p, strong, em, code, pre, ul, ol, li, blockquote, a, br`. No `class`, `style`, `div`, `span`, `<img>`, `<hr>`, tables, colors, or font-size — LinkedIn strips or breaks them.
- **No `<img>`**: keep each image as the literal `[📷 …]` marker so the user uploads it at that spot.
- Wrap in a minimal document so a browser renders it cleanly:

```
<!doctype html>
<html><head><meta charset="utf-8"><title>{title}</title></head>
<body>
<h2>Marketplaces, Plugins, and Skills</h2>
<p><em>Three nested ideas that make agent tooling click.</em></p>
<p>The marketplace is the <strong>distribution layer</strong>, the plugin is the <strong>install unit</strong>, and the skill is the <strong>portable atom</strong>.</p>
<h3>Marketplace</h3>
<ul><li>A git repo with a <strong>marketplace.json</strong> catalog</li><li>Lists plugins to install</li></ul>
<p>[📷 images/three-layers.png — diagram of the three layers]</p>
<blockquote>Get those three words straight and everything falls into place.</blockquote>
<pre><code>{ "name": "my-marketplace" }</code></pre>
<p>Read the <a href="https://example.com">full docs</a>.</p>
</body></html>
```

## Step 4: Write the summary post — `linkedin-post.md`

The **feed** has no rich text, so this stays plain text with **Unicode bold/italic** for emphasis. First 2 lines must hook above the "…see more" fold; short lines; **3–6 hashtags**; **800–1,500 chars**. Keep links **out of the body** (LinkedIn throttles them) — give the article link as a ready-to-paste **first comment**.

```
{𝗨𝗻𝗶𝗰𝗼𝗱𝗲-𝗯𝗼𝗹𝗱 hook line 1}
{hook line 2 that earns the "…see more" tap}

{2–4 short lines previewing the value}

𝗜𝗻𝘀𝗶𝗱𝗲 𝘁𝗵𝗲 𝗳𝘂𝗹𝗹 𝗶𝘀𝘀𝘂𝗲:
◈ {point 1}
◈ {point 2}

{one-line takeaway}

♻️ Repost if useful. Full breakdown in the comments 👇

#Hashtag1 #Hashtag2 #Hashtag3
```

Then give the **first comment** text (the article link) ready to paste.

## Step 5: Personalize and report the publish workflow

Fill `{Author}`, `{role}`, `{Newsletter name}` from what you know; if unknown, leave the placeholder and ask once. Optionally open the HTML in the user's browser for them (e.g. `Start-Process msedge "file:///<abs-path>/linkedin-article.html"`). Then report this exact flow:

**Article**
1. LinkedIn → Home → **Write article** → select your newsletter.
2. **Cover:** upload `images/cover.png` (1920 × 1080).
3. **Title:** paste `{title}` (reported here) into the Title field.
4. **Body:** open `linkedin-article.html` **in a browser** — paste its `file:///…` path into the address bar (do NOT open it in a code editor). **Ctrl+A → Ctrl+C** on the rendered page, click the article body, **Ctrl+V**. Headings, subheadings, bold, italic, lists, quotes, code blocks, and links all carry over.
5. At each **`[📷 …]`** marker, click the image button and upload the named file from `images/`, then delete the marker text.

**Feed post**
6. Paste `linkedin-post.md` into a new feed post, publish, then paste the article link as the **first comment**.

Report: the title, cover path, both file locations, the visuals generated (or placeholders), and the steps above.
