import type { WorkSample } from '@/lib/portfolio-content'
import { portfolioContent as defaultPortfolioContent } from '@/lib/portfolio-content'

function SectionHeading({
  eyebrow,
  title,
  description,
}: {
  eyebrow: string
  title: string
  description?: string
}) {
  return (
    <div className="mx-auto max-w-3xl text-center">
      <p className="text-sm font-semibold uppercase tracking-[0.25em] text-studio-accent">{eyebrow}</p>
      <h2 className="mt-3 text-3xl font-bold tracking-tight md:text-5xl">{title}</h2>
      {description ? <p className="mt-4 text-base text-studio-muted md:text-lg">{description}</p> : null}
    </div>
  )
}

function WorkSampleCard({ sample }: { sample: WorkSample }) {
  return (
    <article className="rounded-3xl border border-studio-line bg-white p-6 shadow-sm">
      <div className="flex min-h-40 items-center justify-center rounded-2xl bg-studio-soft text-center text-sm font-medium text-studio-muted">
        Video sample preview
      </div>
      <h3 className="mt-5 text-xl font-semibold">{sample.title}</h3>
      <dl className="mt-4 grid gap-3 text-sm">
        <div className="flex justify-between gap-4">
          <dt className="text-studio-muted">Languages</dt>
          <dd className="font-medium">
            {sample.sourceLanguage} → {sample.targetLanguage}
          </dd>
        </div>
        <div className="flex justify-between gap-4">
          <dt className="text-studio-muted">Type</dt>
          <dd className="font-medium">{sample.videoType}</dd>
        </div>
        <div className="flex justify-between gap-4">
          <dt className="text-studio-muted">Runtime</dt>
          <dd className="font-medium">{sample.runtime}</dd>
        </div>
        <div className="flex justify-between gap-4">
          <dt className="text-studio-muted">Turnaround</dt>
          <dd className="font-medium">{sample.turnaround}</dd>
        </div>
      </dl>
      <p className="mt-4 text-sm text-studio-muted">{sample.note}</p>
      <div className="mt-4 flex flex-wrap gap-2">
        {sample.services.map((service) => (
          <span key={service} className="rounded-full bg-studio-soft px-3 py-1 text-xs font-medium text-studio-muted">
            {service}
          </span>
        ))}
      </div>
    </article>
  )
}

type PortfolioPageProps = {
  content?: typeof defaultPortfolioContent
}

export default function PortfolioPage({ content = defaultPortfolioContent }: PortfolioPageProps) {
  return (
    <main className="bg-studio-paper text-studio-ink">
      <header className="sticky top-0 z-20 border-b border-studio-line bg-studio-paper/90 backdrop-blur">
        <nav className="mx-auto flex max-w-7xl items-center justify-between px-6 py-4">
          <a className="text-sm font-bold tracking-tight" href="#">
            Video Localization Freelancer
          </a>
          <div className="hidden items-center gap-5 text-sm text-studio-muted md:flex">
            {content.nav.map((item) => (
              <a key={item.href} className="hover:text-studio-ink" href={item.href}>
                {item.label}
              </a>
            ))}
          </div>
        </nav>
      </header>

      <section className="mx-auto grid max-w-7xl gap-12 px-6 py-20 md:grid-cols-[1.05fr_0.95fr] md:items-center md:py-28">
        <div>
          <p className="text-sm font-semibold uppercase tracking-[0.25em] text-studio-accent">{content.hero.eyebrow}</p>
          <h1 className="mt-5 text-5xl font-bold tracking-tight md:text-7xl">{content.hero.title}</h1>
          <p className="mt-6 max-w-2xl text-lg text-studio-muted md:text-xl">{content.hero.description}</p>
          <div className="mt-8 flex flex-col gap-3 sm:flex-row">
            <a className="rounded-full bg-studio-ink px-6 py-3 text-center text-sm font-semibold text-white" href="#contact">
              {content.hero.primaryCta}
            </a>
            <a className="rounded-full border border-studio-line px-6 py-3 text-center text-sm font-semibold" href="#portfolio">
              {content.hero.secondaryCta}
            </a>
          </div>
        </div>
        <div className="rounded-[2rem] border border-studio-line bg-white p-4 shadow-xl">
          <div className="rounded-[1.5rem] bg-studio-soft p-5">
            <div className="aspect-video rounded-2xl bg-studio-ink text-white">
              <div className="flex h-full items-center justify-center px-8 text-center text-xl font-semibold">
                Before / After localized video preview
              </div>
            </div>
            <div className="mt-4 grid grid-cols-2 gap-3 text-sm">
              <div className="rounded-2xl bg-white p-4">
                <p className="text-studio-muted">Output</p>
                <p className="mt-1 font-semibold">SRT + MP4</p>
              </div>
              <div className="rounded-2xl bg-white p-4">
                <p className="text-studio-muted">Formats</p>
                <p className="mt-1 font-semibold">16:9 + 9:16</p>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section className="border-y border-studio-line bg-white">
        <div className="mx-auto flex max-w-7xl flex-wrap justify-center gap-3 px-6 py-5">
          {content.trustStrip.map((item) => (
            <span key={item} className="rounded-full bg-studio-soft px-4 py-2 text-sm font-medium text-studio-muted">
              {item}
            </span>
          ))}
        </div>
      </section>

      <section id="services" className="mx-auto max-w-7xl px-6 py-20">
        <SectionHeading
          eyebrow="Services"
          title="What I deliver"
          description="Concrete deliverables for creators, educators, and teams that need publish-ready localized video."
        />
        <div className="mt-12 grid gap-5 md:grid-cols-2 lg:grid-cols-3">
          {content.services.map((service) => (
            <article key={service.title} className="rounded-3xl border border-studio-line bg-white p-6 shadow-sm">
              <h3 className="text-xl font-semibold">{service.title}</h3>
              <p className="mt-3 text-sm text-studio-muted">{service.description}</p>
              <ul className="mt-5 space-y-2 text-sm">
                {service.deliverables.map((item) => (
                  <li key={item} className="flex gap-2">
                    <span className="text-studio-accent">•</span>
                    <span>{item}</span>
                  </li>
                ))}
              </ul>
            </article>
          ))}
        </div>
      </section>

      <section id="portfolio" className="bg-white px-6 py-20">
        <SectionHeading
          eyebrow="Selected work"
          title="Portfolio samples"
          description="Replace these demo cards with public client samples or clearly labeled demo projects as they become available."
        />
        <div className="mx-auto mt-12 grid max-w-7xl gap-6 md:grid-cols-3">
          {content.workSamples.map((sample) => (
            <WorkSampleCard key={sample.title} sample={sample} />
          ))}
        </div>
      </section>

      <section id="workflow" className="mx-auto max-w-7xl px-6 py-20">
        <SectionHeading eyebrow="Workflow" title="A controlled path from source video to delivery" />
        <div className="mt-12 grid gap-4 md:grid-cols-3">
          {content.workflow.map((step, index) => (
            <article key={step.title} className="rounded-3xl border border-studio-line bg-white p-6">
              <p className="text-sm font-semibold text-studio-accent">Step {index + 1}</p>
              <h3 className="mt-3 text-xl font-semibold">{step.title}</h3>
              <p className="mt-3 text-sm text-studio-muted">{step.description}</p>
            </article>
          ))}
        </div>
      </section>

      <section id="local-ai-stack" className="bg-studio-ink px-6 py-20 text-white">
        <div className="mx-auto grid max-w-7xl gap-10 md:grid-cols-[0.9fr_1.1fr] md:items-start">
          <div>
            <p className="text-sm font-semibold uppercase tracking-[0.25em] text-blue-300">Local AI Stack</p>
            <h2 className="mt-3 text-3xl font-bold tracking-tight md:text-5xl">{content.stack.title}</h2>
            <p className="mt-5 text-zinc-300">{content.stack.description}</p>
            <div className="mt-8 flex flex-wrap gap-3">
              {content.stack.links.map((link) => (
                <a
                  key={link.href}
                  className="rounded-full border border-white/20 px-5 py-3 text-sm font-semibold hover:bg-white hover:text-studio-ink"
                  href={link.href}
                >
                  {link.label}
                </a>
              ))}
            </div>
          </div>
          <ul className="grid gap-3">
            {content.stack.items.map((item) => (
              <li key={item} className="rounded-2xl bg-white/10 p-4 text-sm text-zinc-100">
                {item}
              </li>
            ))}
          </ul>
        </div>
      </section>

      <section id="about" className="mx-auto max-w-4xl px-6 py-20 text-center">
        <SectionHeading eyebrow="About" title="Human judgment, local workflow discipline" description={content.about} />
      </section>

      <section id="contact" className="px-6 pb-24">
        <div className="mx-auto max-w-4xl rounded-[2rem] bg-white p-8 shadow-xl md:p-12">
          <h2 className="text-3xl font-bold tracking-tight">{content.contact.title}</h2>
          <p className="mt-4 text-studio-muted">{content.contact.description}</p>
          <div className="mt-6 flex flex-wrap gap-2">
            {content.contact.fields.map((field) => (
              <span key={field} className="rounded-full bg-studio-soft px-3 py-1 text-xs font-medium text-studio-muted">
                {field}
              </span>
            ))}
          </div>
          <a className="mt-8 inline-flex rounded-full bg-studio-accent px-6 py-3 text-sm font-semibold text-white" href={content.contact.email}>
            Request a Quote
          </a>
        </div>
      </section>
    </main>
  )
}
