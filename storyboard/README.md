# Storyboard Maker

A ShotDeck-style deck builder for directors: pull cinematic reference stills by shot size, lens, lighting and mood, direct a screenplay scene through a chosen director's visual grammar, generate AI frames where no reference exists, and export a printable PDF storyboard with the full shot taxonomy for the crew.

Everything runs locally. Projects and images are stored in your browser (IndexedDB). API keys, when you add any, stay on the small Node server and never reach the browser.

## What works with zero keys

- **Screenplay import**: upload a PDF, `.fountain` or `.txt` (or paste text). Scenes, action, character cues, dialogue and parentheticals are parsed in the browser. Nothing is uploaded anywhere.
- **Director lens**: pick a director (Villeneuve, Kubrick, Fincher, Wong Kar-wai, Malick, Tarkovsky, Ozu, Bong Joon-ho, Wes Anderson, PTA, Nolan, Mani Ratnam, Lijo Jose Pellissery, Dileesh Pothan, Anurag Kashyap, Vetrimaaran, Ram Gopal Varma, Padmarajan, Bharathan, Greta Gerwig), write a custom grammar, or use neutral defaults. The lens drives the shot list, the reference search and the image prompts.
- **Auto shot list**: an offline rule engine lays out coverage per scene in that grammar (openers, masters, OTS, singles, inserts on props named in the action, peaks, closers) with shot size, angle, movement, lens mm, lighting, time of day, palette, duration.
- **Board**: drag to reorder, duplicate, delete, drop your own stills onto any card, multiple candidate frames per shot with one hero frame.
- **AI frames**: the default provider is **Pollinations** (FLUX), free with no key. One image per ~15 s on the anonymous tier; small watermark unless you register a free account and set `POLLINATIONS_TOKEN`.
- **PDF export**: A4/Letter landscape, 2/4/6 frames per page, taxonomy strip, action, dialogue, notes, credit line under reference stills.

## Optional keys (`storyboard/.env`)

Copy `.env.example` to `.env` and fill in what you have. Restart `npm run dev` after editing.

| Key | What it unlocks | Cost |
|---|---|---|
| `FRAMETHROWER_TOKEN` | Reference stills from [FrameThrower](https://framethrower.ai): 5,000+ films indexed per frame on shot type, lens, lighting, mood, colour. Search in plain language, browse by the chosen director, "more like this", copy a frame's metadata onto your shot. | Free $2 credit on signup, no card. Then $1 = 500 searches. |
| `CLOUDFLARE_ACCOUNT_ID` + `CLOUDFLARE_API_TOKEN` | FLUX.1 schnell on Cloudflare Workers AI | Free daily allowance on a free account ([pricing](https://developers.cloudflare.com/workers-ai/platform/pricing/)) |
| `GEMINI_API_KEY` | Gemini image model (`gemini-2.5-flash-image` by default, set `GEMINI_IMAGE_MODEL` to change). Supports reference images for character consistency. | Free-tier image quota varies by account; check AI Studio |
| `OPENAI_API_KEY` | `gpt-image-2`, best prompt adherence, any aspect ratio, reference images via edits | ~$0.03 to $0.08 per image |
| `ANTHROPIC_API_KEY` | Claude (`claude-opus-5`) writes the scene breakdown in the director lens instead of the rule engine | Per token |

**Why not ShotDeck or Film Vibes directly?** Neither offers a public API, and ShotDeck's Terms of Use forbid scraping and crawling. FrameThrower is the library built for this: it returns metadata and image URLs with credits and deep links, never raw files, and the frames remain the property of their rights holders. Reference stills in your PDF are for internal pre-production use; the credit line is printed by default.

## Run

```bash
cd storyboard
npm install
cp .env.example .env     # optional
npm run dev              # web on http://localhost:5173, api on :8787
```

Production: `npm run build && npm start` serves the built app and the API from one process on `PORT` (default 8787).

## Workflow

1. **New board**, name it, pick the aspect ratio in the top bar.
2. **Director tab**: choose the lens. Custom lets you type your own grammar ("long takes, handheld, 32mm, sodium light, slow").
3. **Script tab**: upload the screenplay PDF, tick the scenes, import with "Lay out shots in the lens" on. With an Anthropic key you can tick "Use Claude to direct".
4. **Board**: click a shot to edit its taxonomy on the right. Drop images on cards. Reorder by dragging.
5. **References tab** (FrameThrower): search from the shot, pull the director's own frames, attach candidates, copy metadata onto the shot.
6. **Generate tab**: the prompt is built from the shot plus the lens vocabulary. Pick a provider, optionally add reference images (Gemini/OpenAI), generate variations. First result becomes the hero frame.
7. **Export PDF** from the top bar. **JSON** exports the project structure (images stay in the browser).

## Tests

```bash
npm test          # vitest: parser, rule engine, prompt builder, taxonomy mapping, PDF layout math
npm run build     # tsc strict + vite
```

## Layout

```
server/            Express API: /api/frames/* (FrameThrower), /api/generate (providers), /api/shotlist (Claude), /api/img (image proxy)
src/types.ts       data model
src/taxonomy.ts    option lists + FrameThrower metadata mappers
src/directors.ts   director lens profiles
src/lib/screenplay.ts  PDF/Fountain/txt -> scenes
src/lib/shotlist.ts    offline rule engine
src/lib/prompt.ts      shot + lens -> image prompt / reference query
src/export/pdf.ts      jsPDF storyboard
src/store/             zustand + Dexie (IndexedDB)
src/components/        Board, Inspector, References, Generate, Script, Director, Settings
```
