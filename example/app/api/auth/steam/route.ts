import { NextResponse } from 'next/server'
import { buildSteamAuthUrl } from '@/lib/steam'

function getBaseUrl(req: Request): string {
  const url = new URL(req.url)
  const host = req.headers.get('x-forwarded-host') ?? req.headers.get('host') ?? url.host
  const proto = req.headers.get('x-forwarded-proto') ?? (host.includes('localhost') ? 'http' : 'https')
  return `${proto}://${host}`
}

export async function GET(req: Request) {
  const base = getBaseUrl(req)
  const returnTo = `${base}/api/auth/steam/callback`
  const authUrl = buildSteamAuthUrl(base, returnTo)
  return NextResponse.redirect(authUrl)
}
