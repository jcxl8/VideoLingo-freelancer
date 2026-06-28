export type ServiceItem = {
  title: string
  description: string
  deliverables: string[]
}

export type WorkSample = {
  title: string
  sourceLanguage: string
  targetLanguage: string
  videoType: string
  runtime: string
  services: string[]
  deliveryFormat: string
  turnaround: string
  note: string
}

export type WorkflowStep = {
  title: string
  description: string
}

export const portfolioContent = {
  nav: [
    { label: 'Services', href: '#services' },
    { label: 'Portfolio', href: '#portfolio' },
    { label: 'Workflow', href: '#workflow' },
    { label: 'Local AI Stack', href: '#local-ai-stack' },
    { label: 'About', href: '#about' },
    { label: 'Contact', href: '#contact' },
    { label: '中文', href: '/zh-CN' },
  ],
  hero: {
    eyebrow: 'AI-assisted video localization freelancer',
    title: 'Turn your videos into publish-ready multilingual content',
    description:
      'I help creators, educators, and teams localize videos with translated subtitles, subtitle burn-in, optional dubbing, and format-aware delivery for YouTube, courses, shorts, and social platforms.',
    primaryCta: 'Request a Quote',
    secondaryCta: 'View Work Samples',
  },
  trustStrip: [
    'Subtitle translation',
    'Bilingual review',
    'Hard-sub rendering',
    'Optional dubbing',
    '9:16 vertical adaptation',
    'Local AI-assisted workflow',
  ],
  services: [
    {
      title: 'Subtitle Translation',
      description: 'Translate source subtitles or ASR transcripts into natural, readable target-language subtitles.',
      deliverables: ['Translated SRT', 'Bilingual review file', 'Terminology notes'],
    },
    {
      title: 'Hard-Sub Video Rendering',
      description: 'Burn reviewed subtitles into videos for platforms that need ready-to-upload files.',
      deliverables: ['Rendered MP4', 'Landscape version', 'Vertical version when requested'],
    },
    {
      title: 'Bilingual Subtitle Review',
      description: 'Review timing, line breaks, ambiguity, and subtitle readability before publishing.',
      deliverables: ['Proofread SRT', 'Issue notes', 'Selective retranslation suggestions'],
    },
    {
      title: 'AI-Assisted Dubbing',
      description: 'Create dubbed versions when the selected TTS backend and content type are suitable.',
      deliverables: ['Dubbed preview', 'Aligned subtitles', 'Delivery notes'],
    },
    {
      title: 'Vertical Video Localization',
      description: 'Adapt subtitle layout and burned-in output for shorts, reels, and 9:16 social video.',
      deliverables: ['Portrait subtitle layout', 'Vertical MP4', 'Preview check'],
    },
    {
      title: 'Workflow Automation for Repeat Projects',
      description: 'Use a repeatable local workflow for creators or teams that publish localized videos regularly.',
      deliverables: ['Reusable settings', 'Agent-friendly run notes', 'Project history'],
    },
  ] satisfies ServiceItem[],
  workSamples: [
    {
      title: 'Creator Education Demo',
      sourceLanguage: 'English',
      targetLanguage: 'Chinese',
      videoType: 'YouTube explainer',
      runtime: '8–12 minutes',
      services: ['Subtitle translation', 'Bilingual review', 'Hard-sub rendering'],
      deliveryFormat: 'SRT + MP4',
      turnaround: '2–3 business days',
      note: 'Demo case for terminology consistency and readable subtitle pacing.',
    },
    {
      title: 'Short-Form Social Demo',
      sourceLanguage: 'Chinese',
      targetLanguage: 'English',
      videoType: '9:16 short video',
      runtime: '30–90 seconds',
      services: ['ASR cleanup', 'Translation', 'Vertical hard-sub rendering'],
      deliveryFormat: 'Vertical MP4 + SRT',
      turnaround: '1–2 business days',
      note: 'Demo case for portrait subtitle placement and concise English adaptation.',
    },
    {
      title: 'Course Lesson Demo',
      sourceLanguage: 'English',
      targetLanguage: 'Chinese',
      videoType: 'Online course lesson',
      runtime: '15–25 minutes',
      services: ['Subtitle translation', 'Proofreading', 'Delivery package'],
      deliveryFormat: 'SRT + bilingual review notes',
      turnaround: '3–5 business days',
      note: 'Demo case for clarity, terminology, and learner-friendly subtitle rhythm.',
    },
  ] satisfies WorkSample[],
  workflow: [
    {
      title: 'Source review',
      description: 'Check video length, audio quality, source language, target language, deadline, and delivery format.',
    },
    {
      title: 'ASR transcription',
      description: 'Generate or import transcripts, with MLX Whisper on Apple Silicon when available.',
    },
    {
      title: 'Translation and terminology',
      description: 'Translate with context, terminology awareness, and review passes for subtitle readability.',
    },
    {
      title: 'Subtitle proofreading',
      description: 'Check timing, line breaks, bilingual consistency, and issues before rendering.',
    },
    {
      title: 'Render or dub',
      description: 'Create burned-in subtitle videos, optional dubbed versions, and layout-specific outputs.',
    },
    {
      title: 'Delivery package',
      description: 'Deliver publish-ready files with notes on scope, limitations, and reusable settings.',
    },
  ] satisfies WorkflowStep[],
  stack: {
    title: 'A local, quality-controlled workflow',
    description:
      'My production workflow is powered by VideoLingo-Freelancer, a customized local video translation stack built on transcription, translation review, subtitle QA, rendering, and resumable project history.',
    items: [
      'VideoLingo-Freelancer workflow foundation',
      'MLX Whisper on Apple Silicon for local transcription',
      'Whisper large-v3 model family for ASR',
      'Hy-MT2-7B as a tested local translation model option',
      'Subtitle QA, custom watermarking, project history, and resumable tasks',
      'Codex, Claude Code, and OpenClaw operation through the VideoLingo-Freelancer Skill',
    ],
    links: [
      {
        label: 'Application source',
        href: 'https://github.com/jcxl8/VideoLingo-freelancer',
      },
      {
        label: 'Agent Skill',
        href: 'https://github.com/jcxl8/videolingo-freelancer-skill',
      },
    ],
  },
  about:
    'I combine human translation judgment with a local AI-assisted production workflow, so video localization can be faster without losing subtitle readability, timing, or publishing quality.',
  contact: {
    title: 'Start a project',
    description:
      'Send a video link, target language, runtime, deadline, and desired output. I will reply with scope, turnaround, and next steps.',
    fields: ['Video link', 'Source language', 'Target language', 'Runtime', 'Deadline', 'Needed output'],
    email: 'https://github.com/jcxl8/VideoLingo-freelancer/issues/new?title=Video%20localization%20project',
  },
}
