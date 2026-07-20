import { cookies } from 'next/headers'
import crypto from 'crypto'

const COOKIE_NAME = 'duelzone_session'
const SECRET = process.env.SESSION_SECRET || 'dev-only-secret-change-me-in-production'

export type Session = {
  steamId: string
  personaName: string
  avatar: string
  profileUrl: string
  balance: number // virtual credits (real money integration comes later)
  createdAt: number
}

function sign(payload: string): string {
  return crypto.createHmac('sha256', SECRET).update(payload).digest('base64url')
}

function serialize(session: Session): string {
  const payload = Buffer.from(JSON.stringify(session)).toString('base64url')
  return `${payload}.${sign(payload)}`
}

function deserialize(value: string): Session | null {
  const [payload, signature] = value.split('.')
  if (!payload || !signature) return null
  if (sign(payload) !== signature) return null
  try {
    return JSON.parse(Buffer.from(payload, 'base64url').toString()) as Session
  } catch {
    return null
  }
}

export async function getSession(): Promise<Session | null> {
  const store = await cookies()
  const raw = store.get(COOKIE_NAME)?.value
  if (!raw) return null
  return deserialize(raw)
}

export async function setSession(session: Session): Promise<void> {
  const store = await cookies()
  store.set(COOKIE_NAME, serialize(session), {
    httpOnly: true,
    secure: process.env.NODE_ENV === 'production',
    sameSite: 'lax',
    path: '/',
    maxAge: 60 * 60 * 24 * 30,
  })
}

export async function clearSession(): Promise<void> {
  const store = await cookies()
  store.delete(COOKIE_NAME)
}
