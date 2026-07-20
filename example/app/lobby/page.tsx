import { Swords, Radio } from 'lucide-react'
import { getSession } from '@/lib/session'
import { listDuels } from '@/lib/store'
import { SiteHeader } from '@/components/site-header'
import { SiteFooter } from '@/components/site-footer'
import { DuelCard } from '@/components/duel-card'
import { CreateDuelDialog } from '@/components/create-duel-dialog'
import { SteamLoginButton } from '@/components/steam-login-button'

export default async function LobbyPage() {
  const session = await getSession()
  const duels = listDuels()
  const open = duels.filter((d) => d.status === 'open')
  const live = duels.filter((d) => d.status === 'live')

  return (
    <div className="flex min-h-dvh flex-col">
      <SiteHeader />

      <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-8">
        <div className="flex flex-col gap-4 border-b border-border/60 pb-6 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <h1 className="flex items-center gap-2 text-2xl font-bold tracking-tight md:text-3xl">
              <Swords className="size-6 text-primary" /> Duel lobby
            </h1>
            <p className="mt-1 text-sm text-muted-foreground">
              {open.length} open · {live.length} live right now
            </p>
          </div>
          {session ? (
            <CreateDuelDialog balance={session.balance} />
          ) : (
            <SteamLoginButton label="Sign in to create a duel" />
          )}
        </div>

        {!session && (
          <div className="mt-6 rounded-xl border border-primary/30 bg-primary/5 px-4 py-3 text-sm text-muted-foreground">
            You&apos;re browsing as a guest. Sign in through Steam to create or accept duels.
          </div>
        )}

        {live.length > 0 && (
          <section className="mt-8">
            <h2 className="mb-4 flex items-center gap-2 text-sm font-semibold uppercase tracking-widest text-muted-foreground">
              <Radio className="size-4 text-primary" /> Live matches
            </h2>
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {live.map((duel) => (
                <DuelCard
                  key={duel.id}
                  duel={duel}
                  currentSteamId={session?.steamId ?? null}
                  signedIn={!!session}
                />
              ))}
            </div>
          </section>
        )}

        <section className="mt-8">
          <h2 className="mb-4 text-sm font-semibold uppercase tracking-widest text-muted-foreground">
            Open challenges
          </h2>
          {open.length === 0 ? (
            <div className="rounded-xl border border-dashed border-border py-16 text-center">
              <Swords className="mx-auto mb-3 size-8 text-muted-foreground" />
              <p className="font-medium">No open duels yet</p>
              <p className="text-sm text-muted-foreground">Be the first to post a challenge.</p>
            </div>
          ) : (
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {open.map((duel) => (
                <DuelCard
                  key={duel.id}
                  duel={duel}
                  currentSteamId={session?.steamId ?? null}
                  signedIn={!!session}
                />
              ))}
            </div>
          )}
        </section>
      </main>

      <SiteFooter />
    </div>
  )
}
