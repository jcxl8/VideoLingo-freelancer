import type { ReactNode } from 'react'

type GitHubStatsProps = {
  stars?: ReactNode
  recentStargazers?: ReactNode
}

export default function GitHubStats({ stars, recentStargazers }: GitHubStatsProps) {
  return (
    <section className="mx-auto max-w-5xl px-6 py-12 text-center text-sm text-studio-muted">
      <p>
        GitHub proof: {stars || 'open-source workflow'} {recentStargazers ? <span>{recentStargazers}</span> : null}
      </p>
    </section>
  )
}
