---
name: linked-in-post
description: "Repackage a source document into ready-to-post LinkedIn content: a paste-ready newsletter article (an HTML file you open in a browser and copy → LinkedIn keeps the formatting), a short summary post, and an auto-generated cover image. Works on any document you reference; independent of the learn skill, though learn can trigger it. Triggers on: 'make a LinkedIn article', 'turn this into a LinkedIn post', 'create a summary post for X', 'publish X to LinkedIn'."
argument-hint: "[topic or path to source content]"
user-invocable: true
---

# LinkedIn Post: Source Document → Paste-Ready LinkedIn Article + Post

Turn a finished document into ready-to-publish LinkedIn assets:

1. A **newsletter article** — `{DocName}-LinkedIn-Article.md` (readable source) + `{DocName}-LinkedIn-Article.html` (the **paste-ready** file).
2. A **summary post** (`{DocName}-LinkedIn-FeedTeaser-Post.md`) — a short feed teaser that links to the article.
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

Derive a base name **`{DocName}`** from the source: the source document's file name **without its extension** (e.g. `AgentMarketplaces.md` → `{DocName}` = `AgentMarketplaces`). Prefix every output with it so the assets stay tied to their source.

Write everything **next to the source document** (same directory):

- `{DocName}-LinkedIn-Article.md` — readable article source
- `{DocName}-LinkedIn-Article.html` — the paste-ready article body
- `{DocName}-LinkedIn-FeedTeaser-Post.md` — the feed summary post
- `images/` — `cover.png` plus any inline visuals

If content was given inline (no source path), derive `{DocName}` from the title (PascalCase, e.g. "Agent marketplaces" → `AgentMarketplaces`), create `./output/linkedin/{slug}/`, and write the same `{DocName}-…` files there.

## Step 1: Write the article source — `{DocName}-LinkedIn-Article.md`

Reframe the source into flowing prose: a **3–5 minute read (~600–1,200 words)**, **4–7 sections**, leading with *why this matters now*. No hashtags in articles. As you write, drop a `[📷 images/{name}.png — {what the visual shows}]` marker wherever a visual belongs, and reference the cover as `images/cover.png` — **Step 3 generates the actual image files to match these names.** Use this marker syntax (the readable source):

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

## Step 2: Humanize the article — `{DocName}-LinkedIn-Article.md`

Run the **`humanizer`** skill (from the `remote-skills` plugin) on `{DocName}-LinkedIn-Article.md` so it reads as human-written rather than AI-generated, then save the humanized text back to `{DocName}-LinkedIn-Article.md`. This must run **before Step 4** — the paste-ready HTML is rendered from this file, so it needs to reflect the humanized text. If the `humanizer` skill isn't installed, apply its principles inline (cut AI tells and filler, vary sentence rhythm) and continue.

## Step 3: Generate the cover image and inline visuals

Now that the article exists, create the images it references — **directly from the content**, no dependency on any deck/PPTX.

- **Cover image (always):** `images/cover.png` at **1920 × 1080 px** (16:9; LinkedIn's official article/newsletter cover spec), PNG/JPEG/WEBP — **not GIF**, < 5 MB. Keep on-image text minimal (LinkedIn overlays UI on thumbnails).
- **Inline visuals:** for each `[📷 images/{name}.png — …]` marker in the article (3–6 is ideal; architecture, flow, comparison, before/after), generate the named file into `images/` using whatever image/diagram capability is available (an image/diagram skill, or emit Mermaid/SVG and render). Keep the filenames matching the markers.
- **No raster-image capability?** Don't block: leave the inline `[📷 …]` markers as placeholders; for the cover, if a PNG can't be rendered, write `images/cover.svg` (1920 × 1080) and tell the user to export it to PNG.

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

## Step 5: Write the summary post — `{DocName}-LinkedIn-FeedTeaser-Post.md`

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

## Step 6: Humanize the summary post — `{DocName}-LinkedIn-FeedTeaser-Post.md`

Run the **`humanizer`** skill (from the `remote-skills` plugin) on `{DocName}-LinkedIn-FeedTeaser-Post.md` so it sounds like a human wrote it, then save the humanized text back. If the `humanizer` skill isn't installed, apply its principles inline and continue.

## Step 7: Personalize and report the publish workflow

Fill `{Author}`, `{role}`, `{Newsletter name}` from what you know; if unknown, leave the placeholder and ask once. Optionally open the HTML in the user's browser for them (e.g. `Start-Process msedge "file:///<abs-path>/{DocName}-LinkedIn-Article.html"`). Then report this exact flow:

**Article**
1. LinkedIn → Home → **Write article** → select your newsletter.
2. **Cover:** upload `images/cover.png` (1920 × 1080).
3. **Title:** copy the article title from the `<title>…</title>` tag in the `<head>` of `{DocName}-LinkedIn-Article.html`, and paste it into LinkedIn's Title field.
4. **Body:** open `{DocName}-LinkedIn-Article.html` **in a browser** — paste its `file:///…` path into the address bar (do NOT open it in a code editor). **Ctrl+A → Ctrl+C** on the rendered page, click the article body, **Ctrl+V**. Headings, subheadings, bold, italic, lists, quotes, code blocks, and links all carry over.
5. At each **`[📷 …]`** marker, click the image button and upload the named file from `images/`, then delete the marker text.

**Feed post**
6. Paste `{DocName}-LinkedIn-FeedTeaser-Post.md` into a new feed post, publish, then paste the article link as the **first comment**.

Report: the title, cover path, both file locations, the visuals generated (or placeholders), and the steps above.
