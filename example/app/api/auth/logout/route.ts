import { NextResponse } from 'next/server'
import { clearSession } from '@/lib/session'

function getBaseUrl(req: Request): string {
  const url = new URL(req.url)
  const host = req.headers.get('x-forwarded-host') ?? req.headers.get('host') ?? url.host
  const proto = req.headers.get('x-forwarded-proto') ?? (host.includes('localhost') ? 'http' : 'https')
  return `${proto}://${host}`
}

export async function GET(req: Request) {
  await clearSession()
  return NextResponse.redirect(`${getBaseUrl(req)}/`)
}
