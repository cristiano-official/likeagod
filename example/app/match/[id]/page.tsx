import Link from 'next/link'
import { notFound } from 'next/navigation'
import { ArrowLeft, MapPin, Globe, Coins, Trophy, Swords, Loader2 } from 'lucide-react'
import { getSession } from '@/lib/session'
import { getDuel } from '@/lib/store'
import { SiteHeader } from '@/components/site-header'
import { SiteFooter } from '@/components/site-footer'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar'
import { MatchControls } from '@/components/match-controls'

export default async function MatchPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params
  const duel = getDuel(id)
  if (!duel) notFound()

  const session = await getSession()
  const pot = duel.stake * 2
  const isParticipant =
    session?.steamId === duel.creator.steamId || session?.steamId === duel.opponent?.steamId

  const opponentName = duel.opponent?.name ?? 'Waiting…'
  const winnerName =
    duel.winnerSteamId === duel.creator.steamId
      ? duel.creator.name
      : duel.winnerSteamId === duel.opponent?.steamId
        ? duel.opponent?.name
        : null

  return (
    <div className="flex min-h-dvh flex-col">
      <SiteHeader />

      <main className="mx-auto w-full max-w-4xl flex-1 px-4 py-8">
        <Button variant="ghost" size="sm" className="mb-4" render={<Link href="/lobby" />}>
          <ArrowLeft className="size-4" /> Back to lobby
        </Button>

        <div className="overflow-hidden rounded-xl border border-border bg-card">
          {/* Status bar */}
          <div className="flex items-center justify-between border-b border-border/60 px-5 py-3">
            <div className="flex items-center gap-2">
              {duel.status === 'live' && (
                <Badge>
                  <span className="mr-1 size-1.5 animate-pulse rounded-full bg-primary-foreground" />
                  Live
                </Badge>
              )}
              {duel.status === 'open' && <Badge variant="outline" className="text-primary">Open</Badge>}
              {duel.status === 'finished' && (
                <Badge variant="secondary">
                  <Trophy className="size-3.5" /> Finished
                </Badge>
              )}
              <span className="font-mono text-xs text-muted-foreground">
                {duel.mode} · #{duel.id.slice(-5)}
              </span>
            </div>
            <div className="flex items-center gap-4 text-xs text-muted-foreground">
              <span className="flex items-center gap-1.5">
                <MapPin className="size-3.5" /> {duel.map}
              </span>
              <span className="hidden items-center gap-1.5 sm:flex">
                <Globe className="size-3.5" /> {duel.region}
              </span>
            </div>
          </div>

          {/* Versus */}
          <div className="grid grid-cols-[1fr_auto_1fr] items-center gap-4 px-5 py-10">
            <PlayerColumn
              name={duel.creator.name}
              avatar={duel.creator.avatar}
              score={duel.scoreCreator}
              isWinner={duel.winnerSteamId === duel.creator.steamId}
              finished={duel.status === 'finished'}
            />

            <div className="flex flex-col items-center gap-2">
              <span className="flex size-12 items-center justify-center rounded-full bg-primary/10 text-primary">
                <Swords className="size-6" />
              </span>
              <span className="font-mono text-xs font-semibold text-muted-foreground">VS</span>
            </div>

            {duel.opponent ? (
              <PlayerColumn
                name={duel.opponent.name}
                avatar={duel.opponent.avatar}
                score={duel.scoreOpponent}
                isWinner={duel.winnerSteamId === duel.opponent.steamId}
                finished={duel.status === 'finished'}
              />
            ) : (
              <div className="flex flex-col items-center gap-2 text-center opacity-60">
                <span className="flex size-16 items-center justify-center rounded-full border-2 border-dashed border-border">
                  <Loader2 className="size-6 animate-spin text-muted-foreground" />
                </span>
                <p className="text-sm font-medium">Waiting for challenger</p>
              </div>
            )}
          </div>

          {/* Pot */}
          <div className="flex items-center justify-center gap-2 border-t border-border/60 bg-muted/30 py-5">
            <Coins className="size-5 text-primary" />
            <span className="text-sm text-muted-foreground">Prize pool</span>
            <span className="text-2xl font-bold tabular-nums text-primary">
              {pot.toLocaleString()} CR
            </span>
          </div>
        </div>

        {/* Result / actions */}
        <div className="mt-6 space-y-4">
          {duel.status === 'finished' && winnerName && (
            <div className="flex items-center justify-center gap-2 rounded-xl border border-primary/30 bg-primary/5 px-4 py-4 text-center">
              <Trophy className="size-5 text-primary" />
              <p className="font-semibold">
                <span className="text-primary">{winnerName}</span> won {pot.toLocaleString()} CR
              </p>
            </div>
          )}

          {duel.status === 'open' && (
            <div className="rounded-xl border border-dashed border-border py-8 text-center text-sm text-muted-foreground">
              This duel is waiting for an opponent. Share it or head back to the lobby.
            </div>
          )}

          {duel.status === 'live' && duel.opponent && isParticipant && (
            <MatchControls
              matchId={duel.id}
              creatorName={duel.creator.name}
              opponentName={opponentName}
            />
          )}

          {duel.status === 'live' && !isParticipant && (
            <div className="rounded-xl border border-border bg-card py-8 text-center text-sm text-muted-foreground">
              You&apos;re spectating this match.
            </div>
          )}
        </div>
      </main>

      <SiteFooter />
    </div>
  )
}

function PlayerColumn({
  name,
  avatar,
  score,
  isWinner,
  finished,
}: {
  name: string
  avatar: string
  score: number
  isWinner: boolean
  finished: boolean
}) {
  return (
    <div className="flex flex-col items-center gap-3 text-center">
      <Avatar
        className={`size-16 border-2 ${isWinner ? 'border-primary' : 'border-border'}`}
      >
        <AvatarImage src={avatar || undefined} alt={name} />
        <AvatarFallback className="text-lg">{name.slice(0, 2).toUpperCase()}</AvatarFallback>
      </Avatar>
      <div>
        <p className="max-w-[9rem] truncate font-semibold">{name}</p>
        {finished && (
          <p className={`text-3xl font-bold tabular-nums ${isWinner ? 'text-primary' : 'text-muted-foreground'}`}>
            {score}
          </p>
        )}
      </div>
      {finished && isWinner && (
        <Badge>
          <Trophy className="size-3.5" /> Winner
        </Badge>
      )}
    </div>
  )
}
