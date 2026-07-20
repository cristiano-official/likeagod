import { NextResponse } from 'next/server'
import { verifySteamCallback, fetchSteamProfile } from '@/lib/steam'
import { getSession, setSession } from '@/lib/session'

function getBaseUrl(req: Request): string {
  const url = new URL(req.url)
  const host = req.headers.get('x-forwarded-host') ?? req.headers.get('host') ?? url.host
  const proto = req.headers.get('x-forwarded-proto') ?? (host.includes('localhost') ? 'http' : 'https')
  return `${proto}://${host}`
}

export async function GET(req: Request) {
  const base = getBaseUrl(req)
  const { searchParams } = new URL(req.url)

  const steamId = await verifySteamCallback(searchParams)
  if (!steamId) {
    return NextResponse.redirect(`${base}/?error=steam_auth_failed`)
  }

  const profile = await fetchSteamProfile(steamId)
  const existing = await getSession()

  await setSession({
    steamId: profile.steamId,
    personaName: profile.personaName,
    avatar: profile.avatar,
    profileUrl: profile.profileUrl,
    // Keep prior balance if the same player signs in again, otherwise
    // grant a starter balance of virtual credits for the demo.
    balance: existing?.steamId === profile.steamId ? existing.balance : 1000,
    createdAt: existing?.steamId === profile.steamId ? existing.createdAt : Date.now(),
  })

  return NextResponse.redirect(`${base}/lobby`)
}
