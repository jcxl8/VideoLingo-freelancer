type HeroProps = {
  title?: string
  subtitle?: string
}

export default function Hero({
  title = 'VideoLingo-Freelancer',
  subtitle = 'Local video localization workflow',
}: HeroProps) {
  return (
    <section className="mx-auto max-w-5xl px-6 py-24 text-center">
      <h1 className="text-4xl font-bold tracking-tight md:text-6xl">{title}</h1>
      <p className="mx-auto mt-6 max-w-2xl text-lg text-studio-muted">{subtitle}</p>
    </section>
  )
}
