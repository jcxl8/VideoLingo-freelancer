# Personal Video Localization Portfolio Website Design

Date: 2026-06-28

## 1. Decision

Build an English-first personal portfolio website for a freelance video localization specialist. The site should sell a service first and use the VideoLingo-Freelancer GitHub project as technical proof.

The approved direction is:

- Primary audience: potential clients in English-speaking countries.
- Primary goal: convert visitors into project inquiries.
- Primary language: English.
- Secondary language: Chinese, available through a `中文` link.
- Homepage strategy: service-first, with technical credibility as supporting evidence.
- Technical positioning: VideoLingo-Freelancer, MLX Whisper, Hy-MT2-7B, subtitle QA, and Agent Skill automation are trust signals, not the main sales message.

## 2. Positioning

The site should present the owner as a practical video localization freelancer who can turn source videos into publish-ready multilingual content.

Recommended headline:

> Turn your videos into publish-ready multilingual content.

Recommended subheadline:

> Subtitles, translation review, hard-sub rendering, dubbing, and vertical-video adaptation delivered through a local, quality-controlled workflow.

This wording keeps the promise concrete. It avoids making the homepage sound like a developer README while still leaving room to explain the underlying GitHub project.

## 3. Site Structure

Recommended top navigation:

```text
Home · Services · Portfolio · Workflow · Local AI Stack · About · Contact · 中文
```

### Home

Purpose: explain the offer in under 10 seconds and drive the visitor to request a quote or view work samples.

Sections:

1. Hero
   - Headline
   - Short service promise
   - Two calls to action: `Request a Quote` and `View Work Samples`
   - 3 selected portfolio thumbnails or demo samples
2. What I Deliver
   - Translated subtitles
   - Burned-in video
   - Bilingual subtitle review files
   - Optional dubbing
   - Landscape and 9:16 vertical versions
3. Selected Work
   - A compact portfolio grid
   - Each card should show source language, target language, video type, delivery format, and service type
4. Workflow
   - Source review
   - ASR transcription
   - Translation and terminology pass
   - Subtitle proofreading
   - Render or dub
   - Delivery package
5. Local AI Stack
   - Short credibility section linking to the GitHub project
   - Keep this readable for non-technical clients
6. Contact
   - Inquiry form or mail link
   - Ask for video length, source language, target language, deadline, desired output, and sample link

### Services

Purpose: clarify what can be ordered.

Recommended service cards:

- Subtitle Translation
- Hard-Sub Video Rendering
- Bilingual Subtitle Review
- AI-Assisted Dubbing
- Vertical Video Localization
- Workflow Automation for Repeat Projects

Each card should explain deliverables, ideal use cases, and what the client needs to provide.

### Portfolio

Purpose: demonstrate quality through examples.

Each portfolio item should use this data model:

```text
Title
Source language
Target language
Video type
Runtime
Services provided
Delivery format
Turnaround
Before / after preview link
Notes on translation or subtitle decisions
```

If real client samples cannot be shown, use public demo projects and label them clearly as demos.

### Workflow

Purpose: make the service feel reliable and manageable.

Recommended flow:

```text
Source review → ASR transcription → Translation → Proofreading → Render / dub → Delivery
```

The copy should emphasize checkpoints:

- audio quality and source constraints are reviewed first;
- subtitles are proofread before burn-in;
- quality gates prevent broken subtitle files from moving into rendering;
- portrait and landscape outputs are handled separately when needed.

### Local AI Stack

Purpose: provide technical credibility without overwhelming clients.

Mention:

- VideoLingo-Freelancer as the custom workflow foundation;
- MLX Whisper on Apple Silicon for local transcription;
- Whisper large-v3 as the default ASR model family;
- Hy-MT2-7B as the maintainer-tested local translation model recommendation;
- subtitle QA, custom watermarking, project history, and resumable tasks;
- Codex, Claude Code, and OpenClaw operation through the VideoLingo-Freelancer Skill.

Recommended GitHub links:

- Application source: `https://github.com/jcxl8/VideoLingo-freelancer`
- Agent Skill: `https://github.com/jcxl8/videolingo-freelancer-skill`

### About

Purpose: build trust through judgment, not biography filler.

Recommended angle:

> I combine human translation judgment with a local AI-assisted production workflow, so video localization can be faster without losing subtitle readability, timing, or publishing quality.

### Contact

Purpose: reduce friction for project inquiries.

Recommended fields:

- Name
- Email
- Company or channel
- Source video link
- Source language
- Target language
- Runtime
- Needed output: subtitles, burned-in video, dubbing, or all
- Deadline
- Notes

## 4. Visual Direction

Recommended style: clean service studio with technical proof.

Characteristics:

- white or warm off-white background;
- dark text with one confident accent color;
- video thumbnails as the strongest visual element;
- simple workflow diagrams;
- restrained GitHub badges or repository links;
- no heavy “AI dashboard” aesthetic on the homepage.

The site should feel like a premium freelance service, not a SaaS admin panel and not a raw open-source project page.

## 5. Homepage Copy Skeleton

Hero:

```text
Turn your videos into publish-ready multilingual content.

I help creators, educators, and teams localize videos with translated subtitles, subtitle burn-in, optional dubbing, and format-aware delivery for YouTube, courses, shorts, and social platforms.

[Request a Quote] [View Work Samples]
```

Trust strip:

```text
Subtitle translation · Bilingual review · Hard-sub rendering · Optional dubbing · 9:16 vertical adaptation · Local AI-assisted workflow
```

Technical proof:

```text
My production workflow is powered by VideoLingo-Freelancer, a customized local video translation stack built on transcription, translation review, subtitle QA, rendering, and resumable project history.
```

Contact prompt:

```text
Send a video link, target language, runtime, deadline, and desired output. I will reply with scope, turnaround, and next steps.
```

## 6. Implementation Notes

This design can be implemented either as:

1. a static portfolio site under the repository's existing documentation site;
2. a separate portfolio repository linked from the VideoLingo-Freelancer README;
3. a lightweight single-page site first, with portfolio detail pages added later.

Recommended first implementation: a lightweight English single-page portfolio, because the current goal is market validation and client inquiry generation. Add the Chinese page and deeper case studies after the core English page is usable.

## 7. Risks and Constraints

- The portfolio will feel weak without at least three credible work samples or demo projects.
- Technical claims should remain short and verifiable.
- If pricing is not stable, use inquiry-based quoting instead of publishing fixed prices.
- Do not expose private client videos, API keys, model caches, local paths, or generated intermediate files.
- If a sample is AI-generated or a demo, label it clearly.

## 8. Success Criteria

The first version is successful if a visitor can answer these questions within one minute:

1. What service is offered?
2. What deliverables can I request?
3. What kind of video examples has this person handled?
4. Why should I trust the workflow?
5. How do I start a project?

The site should be judged by clarity and inquiry quality, not by the amount of technical detail included.
