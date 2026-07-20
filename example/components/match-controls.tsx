'use client'

import { useState, useTransition } from 'react'
import { useRouter } from 'next/navigation'
import { Loader2, Flag } from 'lucide-react'
import { resolveMatch } from '@/lib/actions'
import { Button } from '@/components/ui/button'

/**
 * Demo-only controls to settle a live match. In production, match outcomes would
 * arrive from the verified game server, not a manual button.
 */
export function MatchControls({
  matchId,
  creatorName,
  opponentName,
}: {
  matchId: string
  creatorName: string
  opponentName: string
}) {
  const router = useRouter()
  const [pending, startTransition] = useTransition()
  const [error, setError] = useState<string | null>(null)

  function resolve(winner: 'creator' | 'opponent') {
    setError(null)
    startTransition(async () => {
      const res = await resolveMatch(matchId, winner)
      if (res?.error) setError(res.error)
      else router.refresh()
    })
  }

  return (
    <div className="rounded-xl border border-dashed border-border bg-card/50 p-4">
      <p className="mb-3 flex items-center gap-2 text-sm font-medium text-muted-foreground">
        <Flag className="size-4 text-primary" /> Report result (demo)
      </p>
      <div className="flex flex-col gap-2 sm:flex-row">
        <Button
          variant="outline"
          className="flex-1"
          onClick={() => resolve('creator')}
          disabled={pending}
        >
          {pending ? <Loader2 className="size-4 animate-spin" /> : `${creatorName} won`}
        </Button>
        <Button
          variant="outline"
          className="flex-1"
          onClick={() => resolve('opponent')}
          disabled={pending}
        >
          {pending ? <Loader2 className="size-4 animate-spin" /> : `${opponentName} won`}
        </Button>
      </div>
      {error && <p className="mt-2 text-sm text-destructive">{error}</p>}
    </div>
  )
}
