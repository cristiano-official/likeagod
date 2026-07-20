'use client'

import { useTransition } from 'react'
import Link from 'next/link'
import { MapPin, Globe, Coins, Loader2, Swords } from 'lucide-react'
import { joinDuel } from '@/lib/actions'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar'
import type { Duel } from '@/lib/store'

export function DuelCard({
  duel,
  currentSteamId,
  signedIn,
}: {
  duel: Duel
  currentSteamId: string | null
  signedIn: boolean
}) {
  const [pending, startTransition] = useTransition()
  const isOwn = duel.creator.steamId === currentSteamId
  const isLive = duel.status === 'live'

  function handleJoin() {
    startTransition(async () => {
      await joinDuel(duel.id)
    })
  }

  return (
    <div className="flex flex-col gap-4 rounded-xl border border-border bg-card p-4 transition-colors hover:border-primary/40">
      <div className="flex items-center justify-between">
        <Badge variant={isLive ? 'default' : 'outline'} className={isLive ? '' : 'text-primary'}>
          {isLive ? (
            <>
              <span className="mr-1 size-1.5 animate-pulse rounded-full bg-primary-foreground" /> Live
            </>
          ) : (
            'Open'
          )}
        </Badge>
        <span className="font-mono text-xs text-muted-foreground">{duel.mode}</span>
      </div>

      <div className="flex items-center gap-3">
        <Avatar className="size-10 border border-border">
          <AvatarImage src={duel.creator.avatar || undefined} alt={duel.creator.name} />
          <AvatarFallback>{duel.creator.name.slice(0, 2).toUpperCase()}</AvatarFallback>
        </Avatar>
        <div className="min-w-0">
          <p className="truncate font-semibold">{duel.creator.name}</p>
          <p className="text-xs text-muted-foreground">
            {isOwn ? 'Your open duel' : 'is waiting for a challenger'}
          </p>
        </div>
      </div>

      <div className="grid grid-cols-3 gap-2 text-xs">
        <div className="flex items-center gap-1.5 text-muted-foreground">
          <MapPin className="size-3.5" /> {duel.map}
        </div>
        <div className="flex items-center gap-1.5 text-muted-foreground">
          <Globe className="size-3.5" /> {duel.region}
        </div>
        <div className="flex items-center gap-1.5 font-medium text-primary">
          <Coins className="size-3.5" /> {duel.stake.toLocaleString()}
        </div>
      </div>

      <div className="flex items-center justify-between border-t border-border/60 pt-3">
        <div>
          <p className="text-xs text-muted-foreground">Prize pool</p>
          <p className="font-bold tabular-nums text-primary">
            {(duel.stake * 2).toLocaleString()} CR
          </p>
        </div>
        {isLive ? (
          <Button variant="outline" size="sm" render={<Link href={`/match/${duel.id}`} />}>
            <Swords className="size-3.5" /> Watch
          </Button>
        ) : isOwn ? (
          <Button variant="outline" size="sm" render={<Link href={`/match/${duel.id}`} />}>
            View
          </Button>
        ) : (
          <Button size="sm" onClick={handleJoin} disabled={!signedIn || pending}>
            {pending ? (
              <>
                <Loader2 className="size-3.5 animate-spin" /> Joining
              </>
            ) : (
              <>Accept</>
            )}
          </Button>
        )}
      </div>
    </div>
  )
}
