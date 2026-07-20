import Link from 'next/link'
import { redirect } from 'next/navigation'
import {
  Wallet,
  ArrowUpRight,
  ArrowDownLeft,
  ExternalLink,
  Trophy,
  Swords,
} from 'lucide-react'
import { getSession } from '@/lib/session'
import { listDuels } from '@/lib/store'
import { SiteHeader } from '@/components/site-header'
import { SiteFooter } from '@/components/site-footer'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { TopUpForm } from '@/components/top-up-form'

export default async function WalletPage() {
  const session = await getSession()
  if (!session) redirect('/')

  const all = listDuels()
  const myDuels = all.filter(
    (d) =>
      d.creator.steamId === session.steamId || d.opponent?.steamId === session.steamId,
  )
  const wins = myDuels.filter((d) => d.winnerSteamId === session.steamId).length
  const played = myDuels.filter((d) => d.status === 'finished').length
  const winRate = played > 0 ? Math.round((wins / played) * 100) : 0

  return (
    <div className="flex min-h-dvh flex-col">
      <SiteHeader />

      <main className="mx-auto w-full max-w-5xl flex-1 px-4 py-8">
        {/* Profile header */}
        <div className="flex flex-col gap-4 border-b border-border/60 pb-6 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-center gap-4">
            <Avatar className="size-14 border border-border">
              <AvatarImage src={session.avatar || undefined} alt={session.personaName} />
              <AvatarFallback className="text-lg">
                {session.personaName.slice(0, 2).toUpperCase()}
              </AvatarFallback>
            </Avatar>
            <div>
              <h1 className="text-xl font-bold tracking-tight">{session.personaName}</h1>
              <a
                href={session.profileUrl}
                target="_blank"
                rel="noreferrer"
                className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground"
              >
                Steam profile <ExternalLink className="size-3" />
              </a>
            </div>
          </div>
          <Button render={<Link href="/lobby" />}>
            <Swords className="size-4" /> Find a duel
          </Button>
        </div>

        {/* Stats */}
        <div className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <StatCard label="Balance" value={`${session.balance.toLocaleString()} CR`} icon={Wallet} highlight />
          <StatCard label="Duels played" value={String(played)} icon={Swords} />
          <StatCard label="Wins" value={String(wins)} icon={Trophy} />
          <StatCard label="Win rate" value={`${winRate}%`} icon={ArrowUpRight} />
        </div>

        <div className="mt-6 grid gap-6 lg:grid-cols-[1fr_360px]">
          {/* Match history */}
          <Card>
            <CardHeader className="border-b">
              <CardTitle>Match history</CardTitle>
              <CardDescription>Your recent duels and settlements</CardDescription>
            </CardHeader>
            <CardContent className="p-0">
              {myDuels.length === 0 ? (
                <div className="py-16 text-center text-sm text-muted-foreground">
                  No duels yet. Head to the lobby to start one.
                </div>
              ) : (
                <ul className="divide-y divide-border/60">
                  {myDuels.map((d) => {
                    const won = d.winnerSteamId === session.steamId
                    const finished = d.status === 'finished'
                    return (
                      <li key={d.id}>
                        <Link
                          href={`/match/${d.id}`}
                          className="flex items-center justify-between gap-3 px-4 py-3 transition-colors hover:bg-muted/40"
                        >
                          <div className="flex items-center gap-3">
                            <span
                              className={`flex size-9 items-center justify-center rounded-lg ${
                                finished
                                  ? won
                                    ? 'bg-primary/10 text-primary'
                                    : 'bg-destructive/10 text-destructive'
                                  : 'bg-muted text-muted-foreground'
                              }`}
                            >
                              {finished ? (
                                won ? (
                                  <ArrowUpRight className="size-4" />
                                ) : (
                                  <ArrowDownLeft className="size-4" />
                                )
                              ) : (
                                <Swords className="size-4" />
                              )}
                            </span>
                            <div>
                              <p className="text-sm font-medium">
                                {d.mode} · {d.map}
                              </p>
                              <p className="text-xs text-muted-foreground">
                                {finished ? (won ? 'Won' : 'Lost') : d.status === 'live' ? 'In progress' : 'Open'}
                              </p>
                            </div>
                          </div>
                          <div className="text-right">
                            <p
                              className={`text-sm font-semibold tabular-nums ${
                                finished ? (won ? 'text-primary' : 'text-destructive') : 'text-muted-foreground'
                              }`}
                            >
                              {finished ? (won ? `+${(d.stake).toLocaleString()}` : `-${d.stake.toLocaleString()}`) : `${d.stake.toLocaleString()}`}
                              {' '}CR
                            </p>
                            <p className="text-xs text-muted-foreground">
                              pot {(d.stake * 2).toLocaleString()}
                            </p>
                          </div>
                        </Link>
                      </li>
                    )
                  })}
                </ul>
              )}
            </CardContent>
          </Card>

          {/* Top up */}
          <Card className="h-fit">
            <CardHeader className="border-b">
              <CardTitle className="flex items-center gap-2">
                <Wallet className="size-4 text-primary" /> Add credits
              </CardTitle>
              <CardDescription>Top up your balance to stake on duels</CardDescription>
            </CardHeader>
            <CardContent>
              <TopUpForm />
            </CardContent>
          </Card>
        </div>
      </main>

      <SiteFooter />
    </div>
  )
}

function StatCard({
  label,
  value,
  icon: Icon,
  highlight,
}: {
  label: string
  value: string
  icon: React.ComponentType<{ className?: string }>
  highlight?: boolean
}) {
  return (
    <div
      className={`rounded-xl border p-4 ${
        highlight ? 'border-primary/30 bg-primary/5' : 'border-border bg-card'
      }`}
    >
      <div className="flex items-center justify-between">
        <span className="text-xs uppercase tracking-widest text-muted-foreground">{label}</span>
        <Icon className={`size-4 ${highlight ? 'text-primary' : 'text-muted-foreground'}`} />
      </div>
      <p
        className={`mt-2 text-2xl font-bold tabular-nums ${highlight ? 'text-primary' : ''}`}
      >
        {value}
      </p>
    </div>
  )
}
