'use client'

import { useActionState, useState } from 'react'
import { Plus, Loader2, Swords } from 'lucide-react'
import { createDuel, type ActionResult } from '@/lib/actions'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog'
import { Label } from '@/components/ui/label'
import { Input } from '@/components/ui/input'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'

const MODES = ['Aim', '1v1 Arena', 'Retake', 'Pistol Only', 'AWP Only']
const MAPS = ['Dust II', 'Mirage', 'Inferno', 'Nuke', 'Ancient', 'Anubis']
const REGIONS = ['EU West', 'EU North', 'NA East', 'NA West']
const STAKES = [50, 100, 250, 500, 1000]

export function CreateDuelDialog({ balance }: { balance: number }) {
  const [open, setOpen] = useState(false)
  const [mode, setMode] = useState(MODES[0])
  const [map, setMap] = useState(MAPS[0])
  const [region, setRegion] = useState(REGIONS[0])
  const [stake, setStake] = useState(100)
  const [state, formAction, pending] = useActionState<ActionResult, FormData>(createDuel, {})

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger
        render={
          <Button size="lg" className="h-10">
            <Plus className="size-4" /> Create duel
          </Button>
        }
      />
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 text-lg">
            <Swords className="size-5 text-primary" /> Create a duel
          </DialogTitle>
          <DialogDescription>
            Set the rules and stake. Your credits are escrowed until a winner is decided.
          </DialogDescription>
        </DialogHeader>

        <form action={formAction} className="grid gap-4">
          <input type="hidden" name="mode" value={mode} />
          <input type="hidden" name="map" value={map} />
          <input type="hidden" name="region" value={region} />

          <div className="grid gap-2">
            <Label>Mode</Label>
            <Select value={mode} onValueChange={setMode}>
              <SelectTrigger className="w-full">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {MODES.map((m) => (
                  <SelectItem key={m} value={m}>
                    {m}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div className="grid gap-2">
              <Label>Map</Label>
              <Select value={map} onValueChange={setMap}>
                <SelectTrigger className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {MAPS.map((m) => (
                    <SelectItem key={m} value={m}>
                      {m}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="grid gap-2">
              <Label>Region</Label>
              <Select value={region} onValueChange={setRegion}>
                <SelectTrigger className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {REGIONS.map((r) => (
                    <SelectItem key={r} value={r}>
                      {r}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>

          <div className="grid gap-2">
            <Label htmlFor="stake">Stake (credits)</Label>
            <Input
              id="stake"
              name="stake"
              type="number"
              min={1}
              max={balance}
              value={stake}
              onChange={(e) => setStake(Number(e.target.value))}
            />
            <div className="flex flex-wrap gap-1.5">
              {STAKES.map((s) => (
                <button
                  key={s}
                  type="button"
                  onClick={() => setStake(s)}
                  disabled={s > balance}
                  className="rounded-md border border-border px-2.5 py-1 text-xs font-medium tabular-nums transition-colors hover:border-primary/50 disabled:opacity-40"
                >
                  {s}
                </button>
              ))}
            </div>
            <p className="text-xs text-muted-foreground">
              Balance: <span className="tabular-nums text-foreground">{balance.toLocaleString()}</span> CR
            </p>
          </div>

          {state?.error && (
            <p className="rounded-md bg-destructive/10 px-3 py-2 text-sm text-destructive">
              {state.error}
            </p>
          )}

          <Button type="submit" size="lg" disabled={pending} className="h-10">
            {pending ? (
              <>
                <Loader2 className="size-4 animate-spin" /> Creating…
              </>
            ) : (
              <>Stake {stake.toLocaleString()} CR & create</>
            )}
          </Button>
        </form>
      </DialogContent>
    </Dialog>
  )
}
