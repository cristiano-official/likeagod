'use client'

import { useActionState, useState } from 'react'
import { Loader2, Plus } from 'lucide-react'
import { topUp, type ActionResult } from '@/lib/actions'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'

const PRESETS = [250, 500, 1000, 2500]

export function TopUpForm() {
  const [amount, setAmount] = useState(500)
  const [state, formAction, pending] = useActionState<ActionResult, FormData>(topUp, {})

  return (
    <form action={formAction} className="grid gap-4">
      <div className="grid gap-2">
        <Label htmlFor="amount">Amount (credits)</Label>
        <Input
          id="amount"
          name="amount"
          type="number"
          min={1}
          value={amount}
          onChange={(e) => setAmount(Number(e.target.value))}
        />
        <div className="flex flex-wrap gap-1.5">
          {PRESETS.map((p) => (
            <button
              key={p}
              type="button"
              onClick={() => setAmount(p)}
              className="rounded-md border border-border px-2.5 py-1 text-xs font-medium tabular-nums transition-colors hover:border-primary/50"
            >
              +{p.toLocaleString()}
            </button>
          ))}
        </div>
      </div>

      {state?.error && <p className="text-sm text-destructive">{state.error}</p>}

      <Button type="submit" disabled={pending}>
        {pending ? (
          <>
            <Loader2 className="size-4 animate-spin" /> Processing…
          </>
        ) : (
          <>
            <Plus className="size-4" /> Add {amount.toLocaleString()} credits
          </>
        )}
      </Button>
      <p className="text-xs leading-relaxed text-muted-foreground">
        Demo top-up adds virtual credits instantly. Real-money deposits will run through a
        regulated payment provider once licensing is in place.
      </p>
    </form>
  )
}
