import Link from 'next/link'
import { Crosshair, Wallet } from 'lucide-react'
import { getSession } from '@/lib/session'
import { Button } from '@/components/ui/button'
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar'
import { SteamLoginButton } from '@/components/steam-login-button'

export async function SiteHeader() {
  const session = await getSession()

  return (
    <header className="sticky top-0 z-40 border-b border-border/60 bg-background/80 backdrop-blur-md">
      <div className="mx-auto flex h-16 max-w-6xl items-center justify-between gap-4 px-4">
        <Link href="/" className="flex items-center gap-2">
          <span className="flex size-8 items-center justify-center rounded-md bg-primary text-primary-foreground">
            <Crosshair className="size-5" />
          </span>
          <span className="text-lg font-semibold tracking-tight">
            DUEL<span className="text-primary">ZONE</span>
          </span>
        </Link>

        <nav className="hidden items-center gap-1 md:flex">
          <Button variant="ghost" size="sm" render={<Link href="/lobby" />}>
            Lobby
          </Button>
          <Button variant="ghost" size="sm" render={<Link href="/wallet" />}>
            Wallet
          </Button>
          <Button variant="ghost" size="sm" render={<Link href="/#how" />}>
            How it works
          </Button>
        </nav>

        <div className="flex items-center gap-2">
          {session ? (
            <>
              <Link
                href="/wallet"
                className="flex items-center gap-1.5 rounded-md border border-border bg-card px-3 py-1.5 text-sm font-medium tabular-nums transition-colors hover:border-primary/50"
              >
                <Wallet className="size-4 text-primary" />
                {session.balance.toLocaleString()}
                <span className="text-muted-foreground">CR</span>
              </Link>
              <Link href="/wallet" className="flex items-center gap-2">
                <Avatar className="size-8 border border-border">
                  <AvatarImage src={session.avatar || undefined} alt={session.personaName} />
                  <AvatarFallback>{session.personaName.slice(0, 2).toUpperCase()}</AvatarFallback>
                </Avatar>
              </Link>
              <Button variant="outline" size="sm" render={<Link href="/api/auth/logout" />}>
                Sign out
              </Button>
            </>
          ) : (
            <SteamLoginButton />
          )}
        </div>
      </div>
    </header>
  )
}
