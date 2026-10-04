# Known issues & limitations

Meta changes the Ad Library frequently. This file records what could not be fully verified and
how the app degrades. Last verified against the live site: **2026-10-04** (country US, English UI).

## Scraping

| Area | Status | Fallback / notes |
|---|---|---|
| Primary data source | Structured JSON embedded in the page and returned by `/api/graphql/` pagination | If Meta stops shipping these, every ad is still parsed from the DOM (`source = dom`) with a warning per ad in the scan log. |
| Platform icons (DOM fallback only) | Icons are CSS sprite masks with no labels. Facebook's own icon is not a sprite, so it can't be detected from the DOM. | Mapping in `config/selectors.yaml → platform_sprites` is best-effort and sprite offsets change on Meta deploys. Platforms from JSON are exact. |
| Placements | Meta now lists up to 6 placements (adds Threads, WhatsApp). | Winner Score platform ratio is `min(n / 4, 1.0)` so the spec's 4-platform scale still tops out at 100%. |
| Localized UI | Anchors cover EN/ES/FR/DE/PT text, but only English was tested live. | The scraper forces `--lang=en-US`; JSON dates are timestamps and locale-independent. |
| Carousel filter | The Ad Library has no carousel media filter. | `--media carousel` searches all media and keeps only ads parsed as carousel. |
| Collated ads | "N ads use this creative and text" groups render as one card; only the representative ad is returned. | The group size is stored as `variation_count`. Other ads in the group aren't stored separately. |
| Dynamic product ads (DPA) | Copy may contain unrendered placeholders such as `{{product.name}}`. | Parser falls back to the first card's text when the top-level text is a template. |
| Media URLs | fbcdn URLs are signed and expire (`oe=` parameter). | Thumbnails/images are downloaded during the scan. Videos are only downloaded if `download_videos: true`. |
| Login wall / captcha | Not bypassed, by design. | Scan stops with status `blocked` plus suggestions (wait, visible mode, undetected driver, slower pacing). The `blocked` path is verified only against synthetic markers, since the live site didn't block during testing. |
| Keyword search breadth | Keyword search matches ad text, so it includes affiliates, resellers and unrelated pages. | Use `--exact-page` to keep only matching page names, or scan by Page ID for precision. |

## Storage

Each ad stores a PNG card screenshot (~60–150 KB) plus up to `max_media_per_ad` original images.
Expect roughly 0.5 MB per ad. Lower `max_media_per_ad`, or set `download_media: false`.
