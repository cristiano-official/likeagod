import Link from 'next/link'
import { Crosshair } from 'lucide-react'

export function SiteFooter() {
  return (
    <footer className="border-t border-border/60 bg-background">
      <div className="mx-auto flex max-w-6xl flex-col gap-6 px-4 py-10 md:flex-row md:items-center md:justify-between">
        <div className="flex items-center gap-2">
          <span className="flex size-7 items-center justify-center rounded-md bg-primary text-primary-foreground">
            <Crosshair className="size-4" />
          </span>
          <span className="font-semibold tracking-tight">
            DUEL<span className="text-primary">ZONE</span>
          </span>
        </div>
        <nav className="flex flex-wrap gap-x-6 gap-y-2 text-sm text-muted-foreground">
          <Link href="/lobby" className="hover:text-foreground">Lobby</Link>
          <Link href="/wallet" className="hover:text-foreground">Wallet</Link>
          <Link href="/#how" className="hover:text-foreground">How it works</Link>
          <Link href="/#fair" className="hover:text-foreground">Fair play</Link>
        </nav>
        <p className="max-w-xs text-xs leading-relaxed text-muted-foreground">
          Not affiliated with Valve or Steam. Duels are skill-based. Play responsibly — 18+ only.
        </p>
      </div>
    </footer>
  )
}
