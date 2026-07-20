import Link from 'next/link'
import Image from 'next/image'
import { Crosshair, Wallet, Swords, ShieldCheck, Zap, Trophy } from 'lucide-react'
import { getSession } from '@/lib/session'
import { Button } from '@/components/ui/button'
import { SiteHeader } from '@/components/site-header'
import { SiteFooter } from '@/components/site-footer'
import { SteamLoginButton } from '@/components/steam-login-button'

export default async function HomePage() {
  const session = await getSession()

  return (
    <div className="flex min-h-dvh flex-col">
      <SiteHeader />

      <main className="flex-1">
        {/* Hero */}
        <section className="relative overflow-hidden">
          <div className="absolute inset-0">
            <Image
              src="/hero-duel.png"
              alt=""
              fill
              priority
              className="object-cover opacity-40"
            />
            <div className="absolute inset-0 bg-gradient-to-t from-background via-background/85 to-background/40" />
          </div>

          <div className="relative mx-auto flex max-w-6xl flex-col items-start gap-6 px-4 py-24 md:py-32">
            <span className="inline-flex items-center gap-2 rounded-full border border-primary/30 bg-primary/10 px-3 py-1 text-xs font-medium text-primary">
              <Zap className="size-3.5" /> Skill-based CS2 duels
            </span>
            <h1 className="max-w-2xl text-balance text-4xl font-bold leading-[1.05] tracking-tight md:text-6xl">
              Put your aim on the line.{' '}
              <span className="text-primary">Duel for stakes.</span>
            </h1>
            <p className="max-w-xl text-pretty text-base leading-relaxed text-muted-foreground md:text-lg">
              Sign in through Steam, load your wallet and challenge anyone to a Counter-Strike 2
              1v1. Aim maps, arenas, retakes and pistol rounds — winner takes the pot.
            </p>
            <div className="flex flex-wrap items-center gap-3">
              {session ? (
                <Button size="lg" className="h-11 px-6 text-base" render={<Link href="/lobby" />}>
                  <Swords className="size-4" /> Enter the lobby
                </Button>
              ) : (
                <SteamLoginButton className="h-11 px-6 text-base" />
              )}
              <Button
                variant="outline"
                size="lg"
                className="h-11 px-6 text-base"
                render={<Link href="/#how" />}
              >
                How it works
              </Button>
            </div>

            <dl className="mt-6 grid grid-cols-3 gap-6 border-t border-border/60 pt-6">
              {[
                { k: '2.4M+', v: 'Duels played' },
                { k: '<15s', v: 'Avg. match found' },
                { k: '99.9%', v: 'Instant payouts' },
              ].map((s) => (
                <div key={s.v}>
                  <dt className="text-2xl font-bold tabular-nums md:text-3xl">{s.k}</dt>
                  <dd className="text-xs text-muted-foreground md:text-sm">{s.v}</dd>
                </div>
              ))}
            </dl>
          </div>
        </section>

        {/* Features */}
        <section id="how" className="mx-auto max-w-6xl scroll-mt-20 px-4 py-16 md:py-24">
          <div className="mb-12 max-w-2xl">
            <h2 className="text-balance text-3xl font-bold tracking-tight md:text-4xl">
              Four steps from queue to payout
            </h2>
            <p className="mt-3 text-pretty text-muted-foreground">
              Everything runs off your Steam identity and a single credits wallet. No lobbies to
              babysit, no manual payouts.
            </p>
          </div>

          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {[
              {
                icon: Crosshair,
                title: '1. Sign in with Steam',
                body: 'Authenticate through Steam OpenID. Your profile and rank travel with you.',
              },
              {
                icon: Wallet,
                title: '2. Load your wallet',
                body: 'Top up credits into a secure balance. Stake exactly what you want per duel.',
              },
              {
                icon: Swords,
                title: '3. Create or join a duel',
                body: 'Pick a mode, map and stake. Get matched with a player in seconds.',
              },
              {
                icon: Trophy,
                title: '4. Win the pot',
                body: 'Results settle automatically. The winner takes the combined stake instantly.',
              },
            ].map((f) => (
              <div
                key={f.title}
                className="rounded-xl border border-border bg-card p-5 transition-colors hover:border-primary/40"
              >
                <span className="mb-4 flex size-10 items-center justify-center rounded-lg bg-primary/10 text-primary">
                  <f.icon className="size-5" />
                </span>
                <h3 className="mb-1.5 font-semibold">{f.title}</h3>
                <p className="text-sm leading-relaxed text-muted-foreground">{f.body}</p>
              </div>
            ))}
          </div>
        </section>

        {/* Fair play */}
        <section id="fair" className="border-y border-border/60 bg-card/40">
          <div className="mx-auto grid max-w-6xl items-center gap-10 px-4 py-16 md:grid-cols-2 md:py-24">
            <div>
              <span className="inline-flex items-center gap-2 rounded-full border border-border bg-background px-3 py-1 text-xs font-medium text-muted-foreground">
                <ShieldCheck className="size-3.5 text-primary" /> Anti-cheat & escrow
              </span>
              <h2 className="mt-4 text-balance text-3xl font-bold tracking-tight md:text-4xl">
                Every credit held in escrow until the round is decided
              </h2>
              <p className="mt-3 text-pretty leading-relaxed text-muted-foreground">
                Stakes from both players are locked the moment a duel goes live. Match results are
                validated before the pot is released, so nobody can rage-quit with your credits.
              </p>
              <ul className="mt-6 space-y-3">
                {[
                  'VAC-secured servers and demo review on flagged games',
                  'Both stakes escrowed — released only to the verified winner',
                  'Full match history and transaction log in your wallet',
                ].map((point) => (
                  <li key={point} className="flex items-start gap-2 text-sm">
                    <ShieldCheck className="mt-0.5 size-4 shrink-0 text-primary" />
                    <span className="text-muted-foreground">{point}</span>
                  </li>
                ))}
              </ul>
            </div>
            <div className="rounded-xl border border-border bg-background p-6">
              <div className="flex items-center justify-between border-b border-border/60 pb-4">
                <span className="text-sm font-medium text-muted-foreground">Live pot</span>
                <span className="flex items-center gap-1.5 text-sm font-semibold text-primary">
                  <span className="size-2 animate-pulse rounded-full bg-primary" /> Escrowed
                </span>
              </div>
              <div className="py-6 text-center">
                <p className="text-xs uppercase tracking-widest text-muted-foreground">
                  Total prize
                </p>
                <p className="mt-1 text-5xl font-bold tabular-nums text-primary">1,000</p>
                <p className="text-sm text-muted-foreground">credits</p>
              </div>
              <div className="grid grid-cols-2 gap-3 text-center text-sm">
                <div className="rounded-lg bg-muted/50 p-3">
                  <p className="font-semibold">sh1ft_</p>
                  <p className="text-muted-foreground">staked 500</p>
                </div>
                <div className="rounded-lg bg-muted/50 p-3">
                  <p className="font-semibold">You</p>
                  <p className="text-muted-foreground">staked 500</p>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* CTA */}
        <section className="mx-auto max-w-6xl px-4 py-20 text-center md:py-28">
          <h2 className="mx-auto max-w-2xl text-balance text-3xl font-bold tracking-tight md:text-5xl">
            Ready to prove it? The lobby is waiting.
          </h2>
          <p className="mx-auto mt-4 max-w-lg text-pretty text-muted-foreground">
            Join thousands of players settling the age-old question: who&apos;s actually better.
          </p>
          <div className="mt-8 flex justify-center">
            {session ? (
              <Button size="lg" className="h-11 px-6 text-base" render={<Link href="/lobby" />}>
                <Swords className="size-4" /> Find a duel
              </Button>
            ) : (
              <SteamLoginButton
                className="h-11 px-6 text-base"
                label="Sign in through Steam to play"
              />
            )}
          </div>
        </section>
      </main>

      <SiteFooter />
    </div>
  )
}
