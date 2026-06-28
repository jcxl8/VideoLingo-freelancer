type Feature = {
  title: string
  description: string
}

type FeaturesProps = {
  title?: string
  items?: Feature[]
}

export default function Features({ title = 'Features', items = [] }: FeaturesProps) {
  return (
    <section className="mx-auto max-w-6xl px-6 py-16">
      <h2 className="text-3xl font-bold tracking-tight">{title}</h2>
      <div className="mt-8 grid gap-4 md:grid-cols-3">
        {items.map((item) => (
          <article key={item.title} className="rounded-2xl border border-studio-line bg-white p-6">
            <h3 className="font-semibold">{item.title}</h3>
            <p className="mt-3 text-sm text-studio-muted">{item.description}</p>
          </article>
        ))}
      </div>
    </section>
  )
}
